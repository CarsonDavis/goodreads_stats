from aws_cdk import (
    Stack,
    aws_lambda as _lambda,
    aws_apigateway as apigateway,
    aws_iam as iam,
    aws_logs as logs,
    Duration,
    CfnOutput,
    BundlingOptions,
)
from constructs import Construct


class ApiStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        storage_stack,
        deployment_env: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.storage_stack = storage_stack
        self.deployment_env = deployment_env

        # Shared Lambda layer for common dependencies
        lambda_layer = _lambda.LayerVersion(
            self,
            "SharedLayer",
            code=_lambda.Code.from_asset(
                "lambda_code/shared",
                bundling=BundlingOptions(
                    image=_lambda.Runtime.PYTHON_3_11.bundling_image,
                    command=[
                        "bash",
                        "-c",
                        "pip install -r requirements.txt -t /asset-output/python && find . -name 'genres' -type d -exec cp -r {} /asset-output/python/ \\; && echo 'Lambda layer bundling complete' && ls -la /asset-output/python/",
                    ],
                ),
            ),
            compatible_runtimes=[_lambda.Runtime.PYTHON_3_11],
            description="Shared dependencies for Goodreads Stats Lambda functions",
        )

        # Configuration
        BOOK_PROCESSOR_CONCURRENCY = 350
        CHUNK_SIZE = 350

        # Environment variables for all Lambda functions
        base_env = {
            "DATA_BUCKET": storage_stack.data_bucket.bucket_name,
            "ENVIRONMENT": deployment_env,
            "PYTHONPATH": "/opt:/var/runtime",
            "LOG_LEVEL": "INFO" if deployment_env == "prod" else "DEBUG",
            "CHUNK_SIZE": str(CHUNK_SIZE),
        }

        # BookProcessor Lambda role
        book_processor_role = iam.Role(
            self,
            "BookProcessorRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                )
            ],
        )
        storage_stack.data_bucket.grant_read_write(book_processor_role)

        # Orchestrator Lambda role
        orchestrator_role = iam.Role(
            self,
            "OrchestratorRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                )
            ],
        )
        storage_stack.data_bucket.grant_read_write(orchestrator_role)

        # Create log group for BookProcessor
        book_processor_log_group = logs.LogGroup(
            self,
            "BookProcessorLogGroup",
            log_group_name=f"/aws/lambda/BookProcessor-{deployment_env}",
            retention=(
                logs.RetentionDays.ONE_WEEK
                if deployment_env != "prod"
                else logs.RetentionDays.ONE_MONTH
            ),
        )

        # BookProcessor Lambda with reserved concurrency
        self.book_processor = _lambda.Function(
            self,
            "BookProcessor",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="lambda_function.lambda_handler",
            code=_lambda.Code.from_asset("lambda_code/book_processor"),
            timeout=Duration.seconds(300),  # 5-minute timeout
            memory_size=512,
            role=book_processor_role,
            environment=base_env,
            layers=[lambda_layer],
            log_group=book_processor_log_group,
            reserved_concurrent_executions=BOOK_PROCESSOR_CONCURRENCY,
        )

        # Orchestrator Lambda
        orchestrator_log_group = logs.LogGroup(
            self,
            "OrchestratorLogGroup",
            log_group_name=f"/aws/lambda/Orchestrator-{deployment_env}",
            retention=(
                logs.RetentionDays.ONE_WEEK
                if deployment_env != "prod"
                else logs.RetentionDays.ONE_MONTH
            ),
        )

        self.orchestrator = _lambda.Function(
            self,
            "Orchestrator",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="lambda_function.lambda_handler",
            code=_lambda.Code.from_asset("lambda_code/orchestrator"),
            timeout=Duration.minutes(15),  # 15-minute timeout
            memory_size=3008,  # Maximum memory (3GB)
            role=orchestrator_role,
            environment={
                **base_env,
                "BOOK_PROCESSOR_FUNCTION_NAME": self.book_processor.function_name,
            },
            layers=[lambda_layer],
            log_group=orchestrator_log_group,
        )

        # Grant orchestrator permission to invoke book processor
        self.book_processor.grant_invoke(self.orchestrator)

        # Upload Handler Lambda role
        upload_role = iam.Role(
            self,
            "UploadRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                )
            ],
        )
        storage_stack.data_bucket.grant_read_write(upload_role)

        # Create log group for Upload Handler
        upload_handler_log_group = logs.LogGroup(
            self,
            "UploadHandlerLogGroup",
            log_group_name=f"/aws/lambda/UploadHandler-{deployment_env}",
            retention=(
                logs.RetentionDays.ONE_WEEK
                if deployment_env != "prod"
                else logs.RetentionDays.ONE_MONTH
            ),
        )

        # Upload Handler Lambda - Add orchestrator function name to environment
        upload_env = {
            **base_env,
            "ORCHESTRATOR_FUNCTION_NAME": self.orchestrator.function_name,
        }

        self.upload_handler = _lambda.Function(
            self,
            "UploadHandler",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="lambda_function.lambda_handler",
            code=_lambda.Code.from_asset("lambda_code/upload_handler"),
            timeout=Duration.minutes(
                10
            ),  # Maximum Lambda timeout to wait for orchestrator completion
            memory_size=512,
            role=upload_role,
            environment=upload_env,
            layers=[lambda_layer],
            log_group=upload_handler_log_group,
        )

        # API Gateway
        domain_name = (
            f"goodreads-stats.codebycarson.com"
            if deployment_env == "prod"
            else f"dev.goodreads-stats.codebycarson.com"
        )

        self.api = apigateway.RestApi(
            self,
            "GoodreadsStatsApi",
            rest_api_name=f"Goodreads Stats API ({deployment_env})",
            description=f"API for Goodreads Stats processing - {deployment_env}",
            binary_media_types=[
                "multipart/form-data",
                "*/*",
            ],  # Enable binary media support
            default_cors_preflight_options=apigateway.CorsOptions(
                allow_origins=[
                    f"https://{domain_name}",
                    "http://localhost:8000",  # For local development
                ],
                allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
                allow_headers=[
                    "Content-Type",
                    "Authorization",
                    "X-Amz-Date",
                    "X-Api-Key",
                ],
                max_age=Duration.hours(1),
            ),
        )

        # Create request validator after API is created
        apigateway.RequestValidator(
            self,
            "RequestValidator",
            rest_api=self.api,
            validate_request_body=True,
            validate_request_parameters=True,
        )

        # API Gateway routes

        # POST /api/upload
        api_resource = self.api.root.add_resource("api")
        upload_integration = apigateway.LambdaIntegration(
            self.upload_handler,
            proxy=True,  # Enable proxy integration for binary data handling
        )

        upload_resource = api_resource.add_resource("upload")
        upload_resource.add_method("POST", upload_integration)

        # GET /api/data/{job_id} - returns dashboard JSON
        # This will be handled by a simple S3 proxy or direct S3 access
        # For now, we'll leave this as a placeholder for future implementation

        # Grant upload handler permission to invoke orchestrator
        self.orchestrator.grant_invoke(self.upload_handler)

        # Outputs
        CfnOutput(self, "ApiUrl", value=self.api.url, description="API Gateway URL")

        CfnOutput(
            self, "ApiId", value=self.api.rest_api_id, description="API Gateway ID"
        )

        CfnOutput(
            self,
            "UploadHandlerArn",
            value=self.upload_handler.function_arn,
            description="Upload Handler Lambda ARN",
        )

        CfnOutput(
            self,
            "OrchestratorArn",
            value=self.orchestrator.function_arn,
            description="Orchestrator Lambda ARN",
        )

        CfnOutput(
            self,
            "BookProcessorArn",
            value=self.book_processor.function_arn,
            description="Book Processor Lambda ARN",
        )
