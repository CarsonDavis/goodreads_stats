from aws_cdk import (
    Stack,
    aws_lambda as _lambda,
    aws_apigateway as apigateway,
    aws_iam as iam,
    aws_logs as logs,
    aws_sqs as sqs,
    aws_lambda_event_sources as lambda_event_sources,
    aws_events as events,
    aws_events_targets as targets,
    aws_s3 as s3,
    aws_s3_notifications as s3n,
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
                "lambda_code/shared",
                bundling=BundlingOptions(
                    image=_lambda.Runtime.PYTHON_3_11.bundling_image,
                    command=[
                        "bash", "-c", 
                        "pip install -r requirements.txt -t /asset-output/python && find . -name 'genres' -type d -exec cp -r {} /asset-output/python/ \\; && echo 'Lambda layer bundling complete' && ls -la /asset-output/python/"
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
        
        # BookProcessor Lambda role
        book_processor_role = iam.Role(
            self, "BookProcessorRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
            ]
        )
        storage_stack.data_bucket.grant_read_write(book_processor_role)
        
        # Aggregator Lambda role
        aggregator_role = iam.Role(
            self, "AggregatorRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
            ]
        )
        storage_stack.data_bucket.grant_read_write(aggregator_role)
        
        # SQS Queues for book processing
        # Dead Letter Queue
        book_processing_dlq = sqs.Queue(
            self, "BookProcessingDLQ",
            queue_name=f"goodreads-book-processing-dlq-{deployment_env}",
            retention_period=Duration.days(14)
        )
        
        # Main processing queue
        self.book_processing_queue = sqs.Queue(
            self, "BookProcessingQueue", 
            queue_name=f"goodreads-book-processing-{deployment_env}",
            visibility_timeout=Duration.minutes(2),  # 2x Lambda timeout
            dead_letter_queue=sqs.DeadLetterQueue(
                max_receive_count=3,
                queue=book_processing_dlq
            ),
            retention_period=Duration.days(1)  # Messages expire after 1 day
        )
        
        # Orchestrator Lambda role with SQS permissions
        orchestrator_role = iam.Role(
            self, "OrchestratorRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
            ]
        )
        storage_stack.data_bucket.grant_read_write(orchestrator_role)
        self.book_processing_queue.grant_send_messages(orchestrator_role)
        
        # Create log group for BookProcessor
        book_processor_log_group = logs.LogGroup(
            self, "BookProcessorLogGroup",
            log_group_name=f"/aws/lambda/BookProcessor-{deployment_env}",
            retention=logs.RetentionDays.ONE_WEEK if deployment_env != "prod" else logs.RetentionDays.ONE_MONTH
        )
        
        # BookProcessor Lambda - Processes individual books
        self.book_processor = _lambda.Function(
            self, "BookProcessor",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="lambda_function.lambda_handler",
            code=_lambda.Code.from_asset("lambda_code/book_processor"),
            timeout=Duration.seconds(60),  # Increased timeout for SQS processing
            memory_size=256,  # Lower memory for single book processing
            role=book_processor_role,
            environment=base_env,
            layers=[lambda_layer],
            log_group=book_processor_log_group
        )
        
        # Add SQS event source to BookProcessor
        self.book_processor.add_event_source(
            lambda_event_sources.SqsEventSource(
                self.book_processing_queue,
                batch_size=1,  # Process one book at a time
                max_batching_window=Duration.seconds(1)
            )
        )
        
        # Create log group for Aggregator
        aggregator_log_group = logs.LogGroup(
            self, "AggregatorLogGroup",
            log_group_name=f"/aws/lambda/Aggregator-{deployment_env}",
            retention=logs.RetentionDays.ONE_WEEK if deployment_env != "prod" else logs.RetentionDays.ONE_MONTH
        )
        
        # Aggregator Lambda - Combines results and creates final JSON
        self.aggregator = _lambda.Function(
            self, "Aggregator",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="lambda_function.lambda_handler",
            code=_lambda.Code.from_asset("lambda_code/aggregator"),
            timeout=Duration.minutes(5),  # 5-minute timeout for aggregation
            memory_size=512,  # Medium memory for aggregation
            role=aggregator_role,
            environment={
                **base_env,
                "S3_BUCKET_NAME": storage_stack.data_bucket.bucket_name
            },
            layers=[lambda_layer],
            log_group=aggregator_log_group
        )
        
        # S3 Event Notification for event-driven aggregation
        # Trigger aggregator when BookProcessor stores enriched results
        # Note: This will trigger for EVERY enriched book, aggregator will check if job is complete
        storage_stack.data_bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED,
            s3n.LambdaDestination(self.aggregator),
            s3.NotificationKeyFilter(
                prefix="processing/"
            )
        )
        
        # CloudWatch Events Rule for aggregator timeout safety (10-minute intervals)
        # Backup trigger in case S3 events miss any failed processing jobs
        aggregator_safety_rule = events.Rule(
            self, "AggregatorSafetyRule", 
            description="Safety trigger for aggregator to handle timeouts every 10 minutes",
            schedule=events.Schedule.expression("rate(10 minutes)")
        )
        
        # Add aggregator as target for safety trigger
        aggregator_safety_rule.add_target(
            targets.LambdaFunction(
                self.aggregator, 
                event=events.RuleTargetInput.from_object({"source": "safety_trigger"})
            )
        )
        
        # Grant Events permission to invoke aggregator
        self.aggregator.add_permission(
            "AllowCloudWatchEvents",
            principal=iam.ServicePrincipal("events.amazonaws.com"),
            source_arn=aggregator_safety_rule.rule_arn
        )
        
        # Create log group for Orchestrator  
        orchestrator_log_group = logs.LogGroup(
            self, "OrchestratorLogGroup",
            log_group_name=f"/aws/lambda/Orchestrator-{deployment_env}",
            retention=logs.RetentionDays.ONE_WEEK if deployment_env != "prod" else logs.RetentionDays.ONE_MONTH
        )
        
        # Orchestrator Lambda (refactored to use SQS)
        self.orchestrator = _lambda.Function(
            self, "Orchestrator",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="lambda_function.lambda_handler", 
            code=_lambda.Code.from_asset("lambda_code/orchestrator"),
            timeout=Duration.minutes(5),  # Time to process CSV and send SQS messages
            memory_size=512,  # Memory for CSV processing
            role=orchestrator_role,
            environment={
                **base_env,
                "BOOK_QUEUE_URL": self.book_processing_queue.queue_url
            },
            layers=[lambda_layer],
            log_group=orchestrator_log_group
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
        
        # Create log group for Upload Handler
        upload_handler_log_group = logs.LogGroup(
            self, "UploadHandlerLogGroup",
            log_group_name=f"/aws/lambda/UploadHandler-{deployment_env}",
            retention=logs.RetentionDays.ONE_WEEK if deployment_env != "prod" else logs.RetentionDays.ONE_MONTH
        )
        
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
            log_group=upload_handler_log_group
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
        
        # Create log group for Status Checker
        status_checker_log_group = logs.LogGroup(
            self, "StatusCheckerLogGroup",
            log_group_name=f"/aws/lambda/StatusChecker-{deployment_env}",
            retention=logs.RetentionDays.ONE_WEEK if deployment_env != "prod" else logs.RetentionDays.ONE_MONTH
        )
        
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
            log_group=status_checker_log_group
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
        _request_validator = apigateway.RequestValidator(
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
        
        CfnOutput(
            self, "BookProcessorArn",
            value=self.book_processor.function_arn,
            description="Book Processor Lambda ARN"
        )
        
        CfnOutput(
            self, "AggregatorArn",
            value=self.aggregator.function_arn,
            description="Aggregator Lambda ARN"
        )
        
        CfnOutput(
            self, "BookProcessingQueueUrl",
            value=self.book_processing_queue.queue_url,
            description="SQS Queue URL for book processing"
        )