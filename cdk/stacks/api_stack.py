from aws_cdk import (
    Stack,
    aws_lambda as _lambda,
    aws_apigateway as apigateway,
    aws_iam as iam,
    aws_logs as logs,
    Duration,
    CfnOutput,
    BundlingOptions
)
from constructs import Construct
import os

class ApiStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, storage_stack, deployment_env: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        self.storage_stack = storage_stack
        self.deployment_env = deployment_env
        
        
        # Shared Lambda layer for common dependencies
        lambda_layer = _lambda.LayerVersion(
            self, "SharedLayer",
            code=_lambda.Code.from_asset(
                "..",
                bundling=BundlingOptions(
                    image=_lambda.Runtime.PYTHON_3_11.bundling_image,
                    command=[
                        "bash", "-c",
                        "pip install -r cdk/lambda_code/shared/requirements.txt -t /asset-output/python && "
                        "cp -r genres /asset-output/python/"
                    ]
                )
            ),
            compatible_runtimes=[_lambda.Runtime.PYTHON_3_11],
            description="Shared dependencies for Goodreads Stats Lambda functions"
        )
        
        # Environment variables for all Lambda functions
        base_env = {
            "DATA_BUCKET": storage_stack.data_bucket.bucket_name,
            "ENVIRONMENT": deployment_env,
            "PYTHONPATH": "/opt:/var/runtime",
            "LOG_LEVEL": "INFO" if deployment_env == "prod" else "DEBUG"
        }
        
        # Orchestrator Lambda role with invoke permissions
        orchestrator_role = iam.Role(
            self, "OrchestratorRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
            ]
        )
        storage_stack.data_bucket.grant_read_write(orchestrator_role)
        
        # Orchestrator Lambda (main processing) - Define first so we can reference it
        self.orchestrator = _lambda.Function(
            self, "Orchestrator",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="lambda_function.lambda_handler", 
            code=_lambda.Code.from_asset("lambda_code/orchestrator"),
            timeout=Duration.minutes(15),  # Max Lambda timeout
            memory_size=1024,  # Higher memory for processing
            role=orchestrator_role,
            environment={
                **base_env,
                "MAX_CONCURRENT": "10",  # Concurrent book processing
                "API_TIMEOUT": "30"
            },
            layers=[lambda_layer],
            log_retention=logs.RetentionDays.ONE_WEEK if deployment_env != "prod" else logs.RetentionDays.ONE_MONTH
        )

        # Upload Handler Lambda role  
        upload_role = iam.Role(
            self, "UploadRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
            ]
        )
        storage_stack.data_bucket.grant_read_write(upload_role)
        
        # Upload Handler Lambda - Add orchestrator function name to environment
        upload_env = {
            **base_env,
            "ORCHESTRATOR_FUNCTION_NAME": self.orchestrator.function_name
        }
        
        self.upload_handler = _lambda.Function(
            self, "UploadHandler",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="lambda_function.lambda_handler",
            code=_lambda.Code.from_asset("lambda_code/upload_handler"),
            timeout=Duration.minutes(2),
            memory_size=512,
            role=upload_role,
            environment=upload_env,
            layers=[lambda_layer],
            log_retention=logs.RetentionDays.ONE_WEEK if deployment_env != "prod" else logs.RetentionDays.ONE_MONTH
        )
        
        # Status Checker Lambda role
        status_role = iam.Role(
            self, "StatusRole", 
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
            ]
        )
        storage_stack.data_bucket.grant_read_write(status_role)
        
        # Status Checker Lambda
        self.status_checker = _lambda.Function(
            self, "StatusChecker",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="lambda_function.lambda_handler",
            code=_lambda.Code.from_asset("lambda_code/status_checker"),
            timeout=Duration.seconds(30),
            memory_size=256,
            role=status_role,
            environment=base_env,
            layers=[lambda_layer],
            log_retention=logs.RetentionDays.ONE_WEEK if deployment_env != "prod" else logs.RetentionDays.ONE_MONTH
        )
        
        # API Gateway
        domain_name = f"goodreads-stats.codebycarson.com" if deployment_env == "prod" else f"dev.goodreads-stats.codebycarson.com"
        
        self.api = apigateway.RestApi(
            self, "GoodreadsStatsApi",
            rest_api_name=f"Goodreads Stats API ({deployment_env})",
            description=f"API for Goodreads Stats processing - {deployment_env}",
            binary_media_types=["multipart/form-data", "*/*"],  # Enable binary media support
            default_cors_preflight_options=apigateway.CorsOptions(
                allow_origins=[
                    f"https://{domain_name}",
                    "http://localhost:8000"  # For local development
                ],
                allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
                allow_headers=["Content-Type", "Authorization", "X-Amz-Date", "X-Api-Key"],
                max_age=Duration.hours(1)
            )
        )
        
        # Create request validator after API is created
        request_validator = apigateway.RequestValidator(
            self, "RequestValidator",
            rest_api=self.api,
            validate_request_body=True,
            validate_request_parameters=True
        )
        
        # API Gateway routes
        
        # POST /api/upload
        api_resource = self.api.root.add_resource("api")
        upload_integration = apigateway.LambdaIntegration(
            self.upload_handler,
            proxy=True  # Enable proxy integration for binary data handling
        )
        
        upload_resource = api_resource.add_resource("upload")
        upload_resource.add_method(
            "POST",
            upload_integration
        )
        
        # GET /api/status/{uuid}
        status_integration = apigateway.LambdaIntegration(self.status_checker)
        status_resource = api_resource.add_resource("status")
        status_uuid_resource = status_resource.add_resource("{uuid}")
        status_uuid_resource.add_method("GET", status_integration)
        
        # GET /api/data/{uuid} - returns dashboard JSON
        data_integration = apigateway.LambdaIntegration(self.status_checker)
        data_resource = api_resource.add_resource("data")
        data_uuid_resource = data_resource.add_resource("{uuid}")
        data_uuid_resource.add_method("GET", data_integration)
        
        # DELETE /api/data/{uuid} - deletes user data
        delete_integration = apigateway.LambdaIntegration(self.status_checker)
        data_uuid_resource.add_method("DELETE", delete_integration)
        
        # Grant upload handler permission to invoke orchestrator
        self.orchestrator.grant_invoke(self.upload_handler)
        
        # Outputs
        CfnOutput(
            self, "ApiUrl",
            value=self.api.url,
            description="API Gateway URL"
        )
        
        CfnOutput(
            self, "ApiId", 
            value=self.api.rest_api_id,
            description="API Gateway ID"
        )
        
        CfnOutput(
            self, "UploadHandlerArn",
            value=self.upload_handler.function_arn,
            description="Upload Handler Lambda ARN"
        )
        
        CfnOutput(
            self, "OrchestratorArn",
            value=self.orchestrator.function_arn,
            description="Orchestrator Lambda ARN"
        )
        
        CfnOutput(
            self, "StatusCheckerArn",
            value=self.status_checker.function_arn,
            description="Status Checker Lambda ARN"
        )