# Goodreads Stats - Infrastructure as Code & Deployment Guide

## Overview

The Goodreads Stats system uses **AWS CDK (Cloud Development Kit)** for infrastructure provisioning and **GitHub Actions** for automated deployment. The deployment strategy prioritizes simplicity, cost-effectiveness, and zero-downtime updates.

## Architecture Components

### Infrastructure Stack
```
AWS Cloud Infrastructure (via CDK)
├── API Gateway                    # REST API endpoints
├── Lambda Functions (3)           # Serverless processing
├── S3 Buckets (3)                 # Storage for uploads, data, and website
├── CloudFront Distribution        # CDN for static assets
├── IAM Roles & Policies           # Least-privilege access
└── CloudWatch Logs                # Monitoring and debugging
```

### Deployment Pipeline
```
GitHub Repository
├── Code Push (main branch)
├── GitHub Actions Workflow
├── CDK Deploy (Backend)
├── Frontend Build & Deploy
└── CloudFront Invalidation
```

---

## Directory Structure

```
goodreads_stats/
├── cdk/                          # Infrastructure as Code
│   ├── app.py                    # CDK application entry point
│   ├── requirements.txt          # CDK dependencies
│   ├── cdk.json                  # CDK configuration
│   ├── stacks/
│   │   ├── __init__.py
│   │   ├── api_stack.py          # API Gateway + Lambda functions
│   │   ├── storage_stack.py      # S3 buckets and policies
│   │   └── frontend_stack.py     # CloudFront + S3 website
│   └── lambda_code/              # Lambda function source code
│       ├── upload_handler/
│       │   ├── lambda_function.py
│       │   └── requirements.txt
│       ├── orchestrator/
│       │   ├── lambda_function.py
│       │   ├── requirements.txt
│       │   └── genres/           # Shared pipeline code
│       └── status_checker/
│           ├── lambda_function.py
│           └── requirements.txt
├── .github/
│   └── workflows/
│       └── deploy.yml            # GitHub Actions deployment
├── dashboard/                    # Frontend source code
│   ├── config.js.template        # Configuration template
│   └── ...                       # HTML, CSS, JS files
└── deployment/                   # Deployment scripts and configs
    ├── build-frontend.sh         # Frontend build script
    ├── deploy.sh                 # Manual deployment script
    └── env-config.json           # Environment-specific configs
```

---

## AWS CDK Implementation

### Main CDK Application (`cdk/app.py`)

```python
#!/usr/bin/env python3
import aws_cdk as cdk
from stacks.storage_stack import StorageStack
from stacks.api_stack import ApiStack
from stacks.frontend_stack import FrontendStack

app = cdk.App()

# Environment configuration
env = cdk.Environment(
    account="123456789012",  # Your AWS account ID
    region="us-east-1"       # Primary region
)

# Deploy stacks in dependency order
storage_stack = StorageStack(app, "GoodreadsStatsStorage", env=env)
api_stack = ApiStack(app, "GoodreadsStatsApi", 
                     storage_stack=storage_stack, env=env)
frontend_stack = FrontendStack(app, "GoodreadsStatsFrontend",
                               api_stack=api_stack, 
                               storage_stack=storage_stack, env=env)

# Tag all resources
cdk.Tags.of(app).add("Project", "GoodreadsStats")
cdk.Tags.of(app).add("Environment", "Production")

app.synth()
```

### Storage Stack (`cdk/stacks/storage_stack.py`)

```python
from aws_cdk import (
    Stack,
    aws_s3 as s3,
    aws_iam as iam,
    RemovalPolicy,
    CfnOutput
)
from constructs import Construct

class StorageStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        # S3 Bucket for CSV uploads (temporary storage)
        self.uploads_bucket = s3.Bucket(
            self, "UploadsBucket",
            bucket_name="goodreads-stats-uploads",
            versioned=False,
            public_read_access=False,
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="DeleteUploadsAfter7Days",
                    expiration=Duration.days(7)  # Auto-cleanup
                )
            ],
            removal_policy=RemovalPolicy.DESTROY  # For development
        )
        
        # S3 Bucket for dashboard data (permanent storage)
        self.data_bucket = s3.Bucket(
            self, "DataBucket", 
            bucket_name="goodreads-stats-data",
            versioned=True,
            public_read_access=True,  # Dashboard JSONs are public
            website_index_document="index.html",
            cors=[
                s3.CorsRule(
                    allowed_origins=["https://goodreads-stats.codebycarson.com"],
                    allowed_methods=[s3.HttpMethods.GET],
                    allowed_headers=["*"]
                )
            ],
            removal_policy=RemovalPolicy.RETAIN  # Keep user data
        )
        
        # S3 Bucket for website hosting
        self.website_bucket = s3.Bucket(
            self, "WebsiteBucket",
            bucket_name="goodreads-stats-website-prod",
            public_read_access=True,
            website_index_document="index.html",
            website_error_document="404.html",
            removal_policy=RemovalPolicy.RETAIN
        )
        
        # Outputs for other stacks
        CfnOutput(self, "UploadsBucketName", value=self.uploads_bucket.bucket_name)
        CfnOutput(self, "DataBucketName", value=self.data_bucket.bucket_name)
        CfnOutput(self, "WebsiteBucketName", value=self.website_bucket.bucket_name)
```

### API Stack (`cdk/stacks/api_stack.py`)

```python
from aws_cdk import (
    Stack,
    aws_lambda as _lambda,
    aws_apigateway as apigateway,
    aws_iam as iam,
    Duration,
    CfnOutput
)
from constructs import Construct

class ApiStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, storage_stack, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        # Lambda execution role
        lambda_role = iam.Role(
            self, "LambdaExecutionRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
            ]
        )
        
        # Grant S3 permissions
        storage_stack.uploads_bucket.grant_read_write(lambda_role)
        storage_stack.data_bucket.grant_read_write(lambda_role)
        
        # Upload Handler Lambda
        self.upload_handler = _lambda.Function(
            self, "UploadHandler",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="lambda_function.lambda_handler",
            code=_lambda.Code.from_asset("lambda_code/upload_handler"),
            timeout=Duration.minutes(1),
            memory_size=512,
            role=lambda_role,
            environment={
                "UPLOADS_BUCKET": storage_stack.uploads_bucket.bucket_name,
                "DATA_BUCKET": storage_stack.data_bucket.bucket_name
            }
        )
        
        # Orchestrator Lambda (main processing)
        self.orchestrator = _lambda.Function(
            self, "Orchestrator", 
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="lambda_function.lambda_handler",
            code=_lambda.Code.from_asset("lambda_code/orchestrator"),
            timeout=Duration.minutes(15),  # Max Lambda timeout
            memory_size=1024,  # Higher memory for processing
            role=lambda_role,
            environment={
                "UPLOADS_BUCKET": storage_stack.uploads_bucket.bucket_name,
                "DATA_BUCKET": storage_stack.data_bucket.bucket_name
            }
        )
        
        # Status Checker Lambda
        self.status_checker = _lambda.Function(
            self, "StatusChecker",
            runtime=_lambda.Runtime.PYTHON_3_11, 
            handler="lambda_function.lambda_handler",
            code=_lambda.Code.from_asset("lambda_code/status_checker"),
            timeout=Duration.seconds(30),
            memory_size=256,
            role=lambda_role,
            environment={
                "DATA_BUCKET": storage_stack.data_bucket.bucket_name
            }
        )
        
        # API Gateway
        self.api = apigateway.RestApi(
            self, "GoodreadsStatsApi",
            rest_api_name="Goodreads Stats API",
            description="API for Goodreads Stats processing",
            default_cors_preflight_options=apigateway.CorsOptions(
                allow_origins=["https://goodreads-stats.codebycarson.com"],
                allow_methods=["GET", "POST", "DELETE"],
                allow_headers=["Content-Type", "Authorization"]
            )
        )
        
        # API Routes
        upload_integration = apigateway.LambdaIntegration(self.upload_handler)
        self.api.root.add_resource("upload").add_method("POST", upload_integration)
        
        status_integration = apigateway.LambdaIntegration(self.status_checker)
        status_resource = self.api.root.add_resource("status")
        status_resource.add_resource("{uuid}").add_method("GET", status_integration)
        
        # Data endpoint (redirects to S3)
        data_resource = self.api.root.add_resource("data")
        data_resource.add_resource("{uuid}").add_method("GET", status_integration)
        
        # Outputs
        CfnOutput(self, "ApiUrl", value=self.api.url)
        CfnOutput(self, "ApiId", value=self.api.rest_api_id)
```

### Frontend Stack (`cdk/stacks/frontend_stack.py`)

```python
from aws_cdk import (
    Stack,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
    CfnOutput
)
from constructs import Construct

class FrontendStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, api_stack, storage_stack, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        # CloudFront Distribution
        self.distribution = cloudfront.Distribution(
            self, "Distribution",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3Origin(storage_stack.website_bucket),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED
            ),
            domain_names=["goodreads-stats.codebycarson.com"],
            certificate=None,  # Use default CloudFront certificate
            default_root_object="index.html",
            error_responses=[
                cloudfront.ErrorResponse(
                    http_status=404,
                    response_http_status=200,
                    response_page_path="/index.html"  # Fallback to upload page
                )
            ]
        )
        
        # Outputs
        CfnOutput(self, "DistributionId", value=self.distribution.distribution_id)
        CfnOutput(self, "DistributionDomain", value=self.distribution.distribution_domain_name)
```

---

## GitHub Actions Deployment

### Main Workflow (`.github/workflows/deploy.yml`)

```yaml
name: Deploy Goodreads Stats

on:
  push:
    branches: [main]
  workflow_dispatch:  # Manual trigger

env:
  AWS_REGION: us-east-1
  
jobs:
  deploy-infrastructure:
    runs-on: ubuntu-latest
    outputs:
      api-url: ${{ steps.deploy-cdk.outputs.api-url }}
      data-bucket: ${{ steps.deploy-cdk.outputs.data-bucket }}
      distribution-id: ${{ steps.deploy-cdk.outputs.distribution-id }}
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
        
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
          
      - name: Setup Node.js for CDK
        uses: actions/setup-node@v4
        with:
          node-version: '18'
          
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ${{ env.AWS_REGION }}
          
      - name: Install CDK dependencies
        working-directory: ./cdk
        run: |
          npm install -g aws-cdk
          pip install -r requirements.txt
          
      - name: Deploy CDK stacks
        id: deploy-cdk
        working-directory: ./cdk
        run: |
          cdk deploy --all --require-approval never --outputs-file outputs.json
          
          # Extract outputs
          API_URL=$(cat outputs.json | jq -r '.GoodreadsStatsApi.ApiUrl')
          DATA_BUCKET=$(cat outputs.json | jq -r '.GoodreadsStatsStorage.DataBucketName')
          DISTRIBUTION_ID=$(cat outputs.json | jq -r '.GoodreadsStatsFrontend.DistributionId')
          
          echo "api-url=$API_URL" >> $GITHUB_OUTPUT
          echo "data-bucket=$DATA_BUCKET" >> $GITHUB_OUTPUT
          echo "distribution-id=$DISTRIBUTION_ID" >> $GITHUB_OUTPUT

  deploy-frontend:
    needs: deploy-infrastructure
    runs-on: ubuntu-latest
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
        
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ${{ env.AWS_REGION }}
          
      - name: Build frontend configuration
        run: |
          # Create config.js from template
          cp dashboard/config.js.template dashboard/config.js
          
          # Inject production values
          sed -i "s|\${API_GATEWAY_URL}|${{ needs.deploy-infrastructure.outputs.api-url }}|g" dashboard/config.js
          sed -i "s|\${S3_DATA_BUCKET}|${{ needs.deploy-infrastructure.outputs.data-bucket }}|g" dashboard/config.js
          sed -i "s|\${ENVIRONMENT}|production|g" dashboard/config.js
          
      - name: Deploy to S3
        run: |
          aws s3 sync dashboard/ s3://goodreads-stats-website-prod/ \
            --delete \
            --cache-control "max-age=31536000" \
            --exclude "*.html" \
            --exclude "*.js"
            
          # HTML and JS files with shorter cache
          aws s3 sync dashboard/ s3://goodreads-stats-website-prod/ \
            --cache-control "max-age=300" \
            --include "*.html" \
            --include "*.js"
            
      - name: Invalidate CloudFront
        run: |
          aws cloudfront create-invalidation \
            --distribution-id ${{ needs.deploy-infrastructure.outputs.distribution-id }} \
            --paths "/goodreads-stats/*"
```

---

## Configuration Management

### Frontend Configuration Template (`dashboard/config.js.template`)

```javascript
// Configuration injected at deployment time
window.GOODREADS_CONFIG = {
    API_BASE_URL: "${API_GATEWAY_URL}",
    S3_DATA_BUCKET: "${S3_DATA_BUCKET}",
    ENVIRONMENT: "${ENVIRONMENT}",
    VERSION: "${BUILD_VERSION}"
};

// Environment detection function
function detectEnvironment() {
    // Production environment
    if (window.GOODREADS_CONFIG?.ENVIRONMENT === 'production') {
        return {
            mode: 'cloud',
            apiBase: window.GOODREADS_CONFIG.API_BASE_URL,
            dataBucket: window.GOODREADS_CONFIG.S3_DATA_BUCKET
        };
    }
    
    // Local development environments
    const host = window.location.host;
    
    if (host === 'localhost:8000') {
        return {
            mode: 'local-api',
            apiBase: 'http://localhost:8001',
            dataBucket: null
        };
    } else if (host.startsWith('localhost') || host.startsWith('127.0.0.1')) {
        return {
            mode: 'local-simple',
            apiBase: null,
            dataPath: '../dashboard_data/'
        };
    }
    
    throw new Error(`Unknown environment: ${host}`);
}

// Export for use in other modules
window.GOODREADS_ENV = detectEnvironment();
```

### Lambda Environment Variables

Each Lambda function receives environment-specific configuration:

```python
# In Lambda functions
import os

UPLOADS_BUCKET = os.environ['UPLOADS_BUCKET']
DATA_BUCKET = os.environ['DATA_BUCKET']
ENVIRONMENT = os.environ.get('ENVIRONMENT', 'production')

# Shared configuration
CONFIG = {
    'max_concurrent_requests': 15,
    'api_timeout': 30,
    'max_file_size': 50 * 1024 * 1024,  # 50MB
    'allowed_file_types': ['.csv']
}
```

---

## Deployment Commands

### Initial Setup

```bash
# 1. Setup CDK
cd cdk
npm install -g aws-cdk
pip install -r requirements.txt

# 2. Bootstrap CDK (one-time setup)
cdk bootstrap aws://ACCOUNT-ID/us-east-1

# 3. Deploy infrastructure
cdk deploy --all

# 4. Deploy frontend manually (first time)
./deployment/build-frontend.sh
aws s3 sync dashboard/ s3://goodreads-stats.codebycarson.com/
```

### Development Workflow

```bash
# Local development
python -m http.server 8000                    # Simple mode
python local_server.py                        # API mode

# Test CDK changes
cd cdk
cdk diff                                       # Preview changes
cdk deploy GoodreadsStatsApi                   # Deploy specific stack

# Manual production deployment
./deployment/deploy.sh                        # Full deployment script
```

### Emergency Procedures

```bash
# Rollback deployment
cdk deploy --previous-parameters

# Delete all resources (careful!)
cdk destroy --all

# View logs
aws logs tail /aws/lambda/GoodreadsStats-UploadHandler --follow

# Check API status
curl https://goodreads-stats.codebycarson.com/api/health
```

---

## Security & Access Control

### IAM Roles & Policies

**Lambda Execution Role:**
- CloudWatch Logs write access
- S3 read/write on specific buckets only
- No network access outside AWS

**GitHub Actions Role:**
- CDK deployment permissions
- S3 sync permissions  
- CloudFront invalidation permissions

### S3 Bucket Policies

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "PublicReadDashboardData",
      "Effect": "Allow", 
      "Principal": "*",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::goodreads-stats-data/*"
    },
    {
      "Sid": "RestrictUploads",
      "Effect": "Deny",
      "NotPrincipal": {
        "AWS": "arn:aws:iam::ACCOUNT:role/GoodreadsStatsLambdaRole"
      },
      "Action": "*",
      "Resource": "arn:aws:s3:::goodreads-stats-uploads/*"
    }
  ]
}
```

### CORS Configuration

```python
# API Gateway CORS
cors_options=apigateway.CorsOptions(
    allow_origins=["https://goodreads-stats.codebycarson.com"],
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-Amz-Date", "Authorization"],
    max_age=Duration.hours(1)
)

# S3 CORS
cors_rules=[
    s3.CorsRule(
        allowed_origins=["https://goodreads-stats.codebycarson.com"],
        allowed_methods=[s3.HttpMethods.GET],
        allowed_headers=["*"],
        max_age=3600
    )
]
```

---

## Monitoring & Observability

### CloudWatch Dashboards

```python
# In CDK stack
dashboard = cloudwatch.Dashboard(
    self, "GoodreadsStatsDashboard",
    dashboard_name="GoodreadsStats-Production"
)

# Lambda metrics
dashboard.add_widgets(
    cloudwatch.GraphWidget(
        title="Lambda Invocations",
        left=[
            upload_handler.metric_invocations(),
            orchestrator.metric_invocations(),
            status_checker.metric_invocations()
        ]
    ),
    cloudwatch.GraphWidget(
        title="Lambda Errors", 
        left=[
            upload_handler.metric_errors(),
            orchestrator.metric_errors(),
            status_checker.metric_errors()
        ]
    )
)
```

### Alerts

```python
# Error rate alarm
cloudwatch.Alarm(
    self, "HighErrorRate",
    metric=orchestrator.metric_errors(period=Duration.minutes(5)),
    threshold=5,
    evaluation_periods=2,
    alarm_description="High error rate in orchestrator function"
)
```

### Logging Strategy

```python
# In Lambda functions
import logging
import json

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    logger.info(f"Processing request: {json.dumps(event)}")
    
    try:
        # Process request
        result = process_books(event)
        logger.info(f"Successfully processed {len(result)} books")
        return result
        
    except Exception as e:
        logger.error(f"Processing failed: {str(e)}", exc_info=True)
        raise
```

---

## Cost Management

### Resource Tagging

```python
# In CDK stacks
cdk.Tags.of(self).add("Project", "GoodreadsStats")
cdk.Tags.of(self).add("Environment", "Production")
cdk.Tags.of(self).add("CostCenter", "PersonalProjects")
cdk.Tags.of(self).add("AutoShutdown", "false")
```

### Cost Optimization

**S3 Lifecycle Policies:**
```python
s3.LifecycleRule(
    id="DeleteTempFiles",
    prefix="uploads/",
    expiration=Duration.days(7)  # Auto-cleanup uploads
),
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
```

**Lambda Optimization:**
- Right-sized memory allocation (1024MB for processing, 256MB for status)
- Timeout optimization (15min max for processing, 30s for others)
- Dead letter queues for failed invocations

---

## Troubleshooting

### Common Issues

**1. CDK Deploy Failures:**
```bash
# Check CDK context
cdk context --clear
cdk bootstrap --force

# Check AWS credentials
aws sts get-caller-identity
```

**2. Lambda Timeout:**
```bash
# Check logs
aws logs tail /aws/lambda/GoodreadsStats-Orchestrator --follow

# Increase timeout in CDK
timeout=Duration.minutes(15)
```

**3. CORS Issues:**
```bash
# Test CORS headers
curl -H "Origin: https://goodreads-stats.codebycarson.com" \
     -H "Access-Control-Request-Method: POST" \
     -X OPTIONS \
     https://goodreads-stats.codebycarson.com/api/upload
```

**4. S3 Permissions:**
```bash
# Test S3 access
aws s3 ls s3://goodreads-stats-data/
aws s3 cp test.json s3://goodreads-stats-data/test.json
```

### Debug Commands

```bash
# CDK debugging
cdk ls                              # List stacks
cdk diff                           # Preview changes
cdk doctor                         # Diagnose issues

# AWS resource inspection  
aws apigateway get-rest-apis       # List APIs
aws lambda list-functions          # List functions
aws s3 ls --recursive s3://bucket  # List S3 contents

# CloudFormation debugging
aws cloudformation describe-stacks --stack-name GoodreadsStatsApi
aws cloudformation describe-stack-events --stack-name GoodreadsStatsApi
```

---

This infrastructure provides a fully automated, cost-effective deployment pipeline that scales from local development to production with zero manual configuration required after initial setup.