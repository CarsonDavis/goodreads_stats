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
    def __init__(self, scope: Construct, construct_id: str, api_stack, storage_stack, environment: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        self.api_stack = api_stack
        self.storage_stack = storage_stack
        self.environment = environment
        
        # Domain configuration
        if environment == "prod":
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
        
        # CloudFront Origin Access Identity for S3
        oai = cloudfront.OriginAccessIdentity(
            self, "OAI",
            comment=f"OAI for Goodreads Stats {environment}"
        )
        
        # Grant CloudFront access to website bucket
        storage_stack.website_bucket.grant_read(oai)
        
        # CloudFront distribution
        self.distribution = cloudfront.Distribution(
            self, "Distribution",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3Origin(
                    storage_stack.website_bucket,
                    origin_access_identity=oai
                ),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
                compress=True,
                allowed_methods=cloudfront.AllowedMethods.ALLOW_GET_HEAD_OPTIONS,
                cached_methods=cloudfront.CachedMethods.CACHE_GET_HEAD_OPTIONS
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
                    origin=origins.S3Origin(
                        storage_stack.website_bucket,
                        origin_access_identity=oai
                    ),
                    viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                    cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
                    compress=True
                ),
                "*.js": cloudfront.BehaviorOptions(
                    origin=origins.S3Origin(
                        storage_stack.website_bucket,
                        origin_access_identity=oai
                    ),
                    viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                    cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
                    compress=True
                )
            },
            domain_names=[domain_name],
            certificate=certificate,
            default_root_object="index.html",
            error_responses=[
                # Handle SPA routing
                cloudfront.ErrorResponse(
                    http_status=404,
                    response_http_status=200,
                    response_page_path="/index.html",
                    ttl=Duration.minutes(5)
                ),
                cloudfront.ErrorResponse(
                    http_status=403,
                    response_http_status=200,
                    response_page_path="/index.html",
                    ttl=Duration.minutes(5)
                )
            ],
            comment=f"Goodreads Stats distribution - {environment}",
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