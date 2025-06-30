from aws_cdk import (
    Stack,
    aws_s3 as s3,
    aws_iam as iam,
    aws_cloudfront as cloudfront,
    RemovalPolicy,
    Duration,
    CfnOutput
)
from constructs import Construct

class StorageStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, deployment_env: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        self.deployment_env = deployment_env
        
        # S3 Bucket for the goodreads-stats data
        # Using single bucket with prefixes as specified
        bucket_name = "goodreads-stats" if deployment_env == "prod" else f"goodreads-stats-{deployment_env}"
        
        self.data_bucket = s3.Bucket(
            self, "DataBucket",
            bucket_name=bucket_name,
            versioned=False,  # Keep it simple
            public_read_access=True,  # Dashboard JSONs need to be publicly readable
            block_public_access=s3.BlockPublicAccess(
                block_public_acls=False,
                block_public_policy=False,
                ignore_public_acls=False,
                restrict_public_buckets=False
            ),
            website_index_document="index.html",
            cors=[
                s3.CorsRule(
                    allowed_origins=[
                        "https://goodreads-stats.codebycarson.com",
                        "https://dev.goodreads-stats.codebycarson.com",
                        "http://localhost:8000"  # For local development
                    ],
                    allowed_methods=[s3.HttpMethods.GET, s3.HttpMethods.HEAD],
                    allowed_headers=["*"],
                    max_age=3600
                )
            ],
            lifecycle_rules=[
                # Automatically clean up temporary uploads after 7 days
                s3.LifecycleRule(
                    id="DeleteUploadsAfter7Days",
                    prefix="uploads/",
                    expiration=Duration.days(7)
                ),
                # Move old dashboard data to cheaper storage after 90 days
                s3.LifecycleRule(
                    id="ArchiveOldData",
                    prefix="data/",
                    transitions=[
                        s3.Transition(
                            storage_class=s3.StorageClass.INFREQUENT_ACCESS,
                            transition_after=Duration.days(90)
                        )
                    ]
                )
            ],
            removal_policy=RemovalPolicy.RETAIN if deployment_env == "prod" else RemovalPolicy.DESTROY
        )
        
        # Bucket policy to allow Lambda functions to access specific prefixes
        self.data_bucket.add_to_resource_policy(
            iam.PolicyStatement(
                sid="AllowLambdaAccess",
                effect=iam.Effect.ALLOW,
                principals=[iam.ServicePrincipal("lambda.amazonaws.com")],
                actions=[
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:DeleteObject"
                ],
                resources=[
                    f"{self.data_bucket.bucket_arn}/uploads/*",
                    f"{self.data_bucket.bucket_arn}/data/*",
                    f"{self.data_bucket.bucket_arn}/status/*"
                ]
            )
        )
        
        # Website bucket configuration  
        if deployment_env == "prod":
            # For production, we'll use CloudFront with OAI
            self.website_bucket = s3.Bucket(
                self, "WebsiteBucket",
                bucket_name="goodreads-stats-website-prod",
                public_read_access=False,  # No direct public access
                block_public_access=s3.BlockPublicAccess(
                    block_public_acls=True,
                    block_public_policy=False,  # Allow OAI policy
                    ignore_public_acls=True,
                    restrict_public_buckets=False  # Allow OAI access
                ),
                # No website configuration for OAI setup
                removal_policy=RemovalPolicy.RETAIN
            )
        else:
            # For dev, simpler setup
            self.website_bucket = s3.Bucket(
                self, "WebsiteBucket", 
                bucket_name=f"goodreads-stats-website-{deployment_env}",
                public_read_access=True,
                block_public_access=s3.BlockPublicAccess(
                    block_public_acls=False,
                    block_public_policy=False,
                    ignore_public_acls=False,
                    restrict_public_buckets=False
                ),
                website_index_document="index.html",
                website_error_document="404.html",
                removal_policy=RemovalPolicy.DESTROY
            )
        
        # CloudFront Origin Access Identity for production
        self.oai = None
        if deployment_env == "prod":
            self.oai = cloudfront.OriginAccessIdentity(
                self, "OAI",
                comment=f"OAI for Goodreads Stats {deployment_env}"
            )
            # Grant CloudFront access to website bucket
            self.website_bucket.grant_read(self.oai)
        
        # Outputs for other stacks
        CfnOutput(
            self, "DataBucketName",
            value=self.data_bucket.bucket_name,
            description="S3 bucket for dashboard data"
        )
        
        CfnOutput(
            self, "DataBucketArn", 
            value=self.data_bucket.bucket_arn,
            description="S3 bucket ARN for dashboard data"
        )
        
        CfnOutput(
            self, "WebsiteBucketName",
            value=self.website_bucket.bucket_name,
            description="S3 bucket for website hosting"
        )
        
        CfnOutput(
            self, "WebsiteBucketArn",
            value=self.website_bucket.bucket_arn, 
            description="S3 bucket ARN for website hosting"
        )