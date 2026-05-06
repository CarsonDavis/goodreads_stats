from aws_cdk import (
    Stack,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
    aws_iam as iam,
    aws_route53 as route53,
    aws_route53_targets as targets,
    aws_certificatemanager as acm,
    Duration,
    CfnOutput
)
from constructs import Construct

GITHUB_ORG = "CarsonDavis"
GITHUB_REPO = "goodreads_stats"


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

        # ── GitHub Actions deploy role (OIDC) ─────────────────────────
        # Replaces the long-lived github-actions-goodreads-stats IAM-user
        # access keys this repo used to ship deploys with. Trust is bound
        # to this repo via the OIDC `sub` claim; permissions are tight.
        oidc_provider = iam.OpenIdConnectProvider.from_open_id_connect_provider_arn(
            self,
            "GitHubOidc",
            f"arn:aws:iam::{self.account}:oidc-provider/token.actions.githubusercontent.com",
        )
        deploy_role = iam.Role(
            self,
            "GitHubActionsDeployRole",
            assumed_by=iam.FederatedPrincipal(
                oidc_provider.open_id_connect_provider_arn,
                conditions={
                    "StringEquals": {
                        "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
                    },
                    "StringLike": {
                        "token.actions.githubusercontent.com:sub": f"repo:{GITHUB_ORG}/{GITHUB_REPO}:*",
                    },
                },
                assume_role_action="sts:AssumeRoleWithWebIdentity",
            ),
            description="Role assumed by GitHub Actions for goodreads_stats deploys",
        )

        # Direct grants for the post-CDK steps in deploy.yml.
        # `aws s3 sync dashboard/ s3://<website-bucket>/ --delete` and
        # `aws s3 cp dashboard_data/... s3://<data-bucket>/data/...` both
        # need read/write/delete on the respective buckets.
        storage_stack.website_bucket.grant_read_write(deploy_role)
        storage_stack.website_bucket.grant_delete(deploy_role)
        storage_stack.data_bucket.grant_read_write(deploy_role)
        storage_stack.data_bucket.grant_delete(deploy_role)

        deploy_role.add_to_policy(
            iam.PolicyStatement(
                actions=["cloudfront:CreateInvalidation"],
                resources=[
                    f"arn:aws:cloudfront::{self.account}:distribution/{self.distribution.distribution_id}"
                ],
            )
        )

        # CDK deploy from CI: assume the bootstrap roles. Modern CDK
        # delegates all CloudFormation/IAM/asset-upload work to those.
        cdk_qualifier = "hnb659fds"
        cdk_role_arns = [
            f"arn:aws:iam::{self.account}:role/cdk-{cdk_qualifier}-{purpose}-{self.account}-{self.region}"
            for purpose in (
                "deploy-role",
                "file-publishing-role",
                "lookup-role",
            )
        ]
        deploy_role.add_to_policy(
            iam.PolicyStatement(
                actions=["sts:AssumeRole"],
                resources=cdk_role_arns,
            )
        )

        CfnOutput(
            self, "GitHubActionsDeployRoleArn",
            value=deploy_role.role_arn,
            description="ARN to set as the AWS_DEPLOY_ROLE_ARN repo secret"
        )