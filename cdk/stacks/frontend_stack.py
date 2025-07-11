from aws_cdk import (
    Stack,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
    aws_route53 as route53,
    aws_route53_targets as targets,
    aws_certificatemanager as acm,
    Duration,
    CfnOutput
)
from constructs import Construct

class FrontendStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, api_stack, storage_stack, deployment_env: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        self.api_stack = api_stack
        self.storage_stack = storage_stack
        self.deployment_env = deployment_env
        
        # Domain configuration
        if deployment_env == "prod":
            domain_name = "goodreads-stats.codebycarson.com"
            hosted_zone_name = "codebycarson.com"
        else:
            domain_name = f"dev.goodreads-stats.codebycarson.com"
            hosted_zone_name = "codebycarson.com"
        
        # Look up existing hosted zone
        hosted_zone = route53.HostedZone.from_lookup(
            self, "HostedZone",
            domain_name=hosted_zone_name
        )
        
        # SSL Certificate (must be in us-east-1 for CloudFront)
        certificate = acm.Certificate(
            self, "Certificate",
            domain_name=domain_name,
            validation=acm.CertificateValidation.from_dns(hosted_zone)
        )
        
        # Use OAI from storage stack (for production) or None (for dev)
        oai = storage_stack.oai
        
        # CloudFront function for URL rewrites
        rewrite_function = cloudfront.Function(
            self, "RewriteFunction",
            code=cloudfront.FunctionCode.from_file(file_path="cloudfront_function.js"),
            function_name=f"goodreads-stats-rewrite-{deployment_env}"
        )
        
        # CloudFront distribution
        # Configure origin based on environment
        if deployment_env == "prod" and oai:
            # Use S3 with OAI for production - force regular S3 endpoint, not website endpoint
            website_origin = origins.S3Origin(
                storage_stack.website_bucket,
                origin_access_identity=oai
            )
        else:
            # For dev, use S3 static website hosting  
            website_origin = origins.S3Origin(storage_stack.website_bucket)
        
        self.distribution = cloudfront.Distribution(
            self, "Distribution",
            default_behavior=cloudfront.BehaviorOptions(
                origin=website_origin,
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
                compress=True,
                allowed_methods=cloudfront.AllowedMethods.ALLOW_GET_HEAD_OPTIONS,
                cached_methods=cloudfront.CachedMethods.CACHE_GET_HEAD_OPTIONS,
                function_associations=[
                    cloudfront.FunctionAssociation(
                        function=rewrite_function,
                        event_type=cloudfront.FunctionEventType.VIEWER_REQUEST
                    )
                ]
            ),
            additional_behaviors={
                # API calls should not be cached
                "/api/*": cloudfront.BehaviorOptions(
                    origin=origins.RestApiOrigin(api_stack.api),
                    viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                    cache_policy=cloudfront.CachePolicy.CACHING_DISABLED,
                    origin_request_policy=cloudfront.OriginRequestPolicy.CORS_S3_ORIGIN,
                    allowed_methods=cloudfront.AllowedMethods.ALLOW_ALL,
                    compress=False
                ),
                # Static assets with longer cache
                "*.css": cloudfront.BehaviorOptions(
                    origin=website_origin,
                    viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                    cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
                    compress=True
                ),
                "*.js": cloudfront.BehaviorOptions(
                    origin=website_origin,
                    viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                    cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
                    compress=True
                )
            },
            domain_names=[domain_name],
            certificate=certificate,
            default_root_object="index.html",
            comment=f"Goodreads Stats distribution - {deployment_env}",
            price_class=cloudfront.PriceClass.PRICE_CLASS_100  # US, Canada, Europe
        )
        
        # Route53 record
        route53.ARecord(
            self, "AliasRecord",
            zone=hosted_zone,
            record_name=domain_name.replace(f".{hosted_zone_name}", ""),
            target=route53.RecordTarget.from_alias(
                targets.CloudFrontTarget(self.distribution)
            )
        )
        
        # Outputs
        CfnOutput(
            self, "DistributionId",
            value=self.distribution.distribution_id,
            description="CloudFront Distribution ID"
        )
        
        CfnOutput(
            self, "DistributionDomain",
            value=self.distribution.distribution_domain_name,
            description="CloudFront Distribution Domain"
        )
        
        CfnOutput(
            self, "WebsiteUrl",
            value=f"https://{domain_name}",
            description="Website URL"
        )
        
        CfnOutput(
            self, "ApiUrl",
            value=f"https://{domain_name}/api",
            description="API URL via CloudFront"
        )