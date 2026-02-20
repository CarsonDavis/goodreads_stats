# Goodreads Stats - Deployment Guide

This guide walks you through the complete deployment setup for the Goodreads Stats application, including AWS configuration, GitHub setup, and the automated CI/CD pipeline.

## Overview

The deployment uses **GitHub Actions** for CI/CD and **AWS CDK** for Infrastructure as Code. The system automatically deploys to different environments based on the git branch:

- **Production**: `main`/`master` branch → `goodreads-stats.codebycarson.com`
- **Development**: Other branches → `dev.goodreads-stats.codebycarson.com`

## Prerequisites

### Required Tools (CloudShell Approach)
- **Web browser** with access to AWS Console
- **Git** (for local development)
- **GitHub Account** with repository access

### Required Tools (Local Approach)
- **AWS CLI** (v2.0+)
- **Node.js** (v18+)
- **Python** (3.11+)
- **Git**
- **jq** (for JSON parsing in GitHub Actions)

### Required Accounts
- **AWS Account** with admin access
- **GitHub Account** with repository access
- **Domain** (`codebycarson.com`) managed in Route 53

---

## 1. AWS Setup

### 1.1 Open AWS CloudShell (Recommended)

**Use AWS CloudShell for secure, credential-free setup:**

1. **Log into AWS Console** with your personal AWS account
2. **Click the CloudShell icon** (terminal icon) in the top toolbar
3. **Wait for CloudShell to initialize** (~30 seconds)

**Alternative: Local AWS CLI Setup**
```bash
# Only if you prefer local setup
aws configure --profile personal
# Enter your AWS Access Key ID
# Enter your AWS Secret Access Key
# Default region: us-east-1
# Default output format: json
```

### 1.2 Verify AWS Account

**In CloudShell:**
```bash
# Check account and region
aws sts get-caller-identity
aws configure get region

# Should return us-east-1 (required for CloudFront certificates)
```

### 1.3 Route 53 Domain Setup

**Verify your domain is in Route 53:**

```bash
aws route53 list-hosted-zones --query 'HostedZones[?Name==`codebycarson.com.`]'
```

**Expected output:**
```json
[
    {
        "Id": "/hostedzone/Z1234567890ABC",
        "Name": "codebycarson.com.",
        "CallerReference": "...",
        "Config": {
            "PrivateZone": false
        }
    }
]
```

If not found, create the hosted zone:
```bash
aws route53 create-hosted-zone \
    --name codebycarson.com \
    --caller-reference "goodreads-stats-$(date +%s)"
```

### 1.4 IAM User for GitHub Actions

**In CloudShell, create dedicated IAM user:**

```bash
# Download the secure policy from your repository
curl -o github-actions-policy.json https://raw.githubusercontent.com/CarsonDavis/goodreads_stats/refs/heads/master/cdk/github-actions-policy.json

# Or if the repo is private, create the policy file manually:
cat > github-actions-policy.json << 'EOF'
# Copy the contents from cdk/github-actions-policy.json in your repository
EOF
```

**Create IAM user and policy:**

```bash
# Create IAM user
aws iam create-user --user-name github-actions-goodreads-stats

# Create the policy
aws iam create-policy \
    --policy-name GithubActionsGoodreadsStatsPolicy \
    --policy-document file://github-actions-policy.json

# Attach policy to user
aws iam attach-user-policy \
    --user-name github-actions-goodreads-stats \
    --policy-arn arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):policy/GithubActionsGoodreadsStatsPolicy
```

**Create access keys:**

```bash
aws iam create-access-key --user-name github-actions-goodreads-stats
```

Copy the output - you'll need `AccessKeyId` and `SecretAccessKey` for GitHub Secrets.

---

## 2. GitHub Repository Setup

### 2.1 GitHub Secrets Configuration

Navigate to your GitHub repository → **Settings** → **Secrets and variables** → **Actions**

**Add the following Repository Secrets:**

| Secret Name | Value | Description |
|-------------|-------|-------------|
| `AWS_ACCESS_KEY_ID` | `AKIA...` | From IAM user creation step |
| `AWS_SECRET_ACCESS_KEY` | `wJalrXUt...` | From IAM user creation step |

### 2.2 GitHub Actions Permissions

1. Go to **Settings** → **Actions** → **General**
2. Under **Workflow permissions**, select:
   - **Read and write permissions**
   - **Allow GitHub Actions to create and approve pull requests**

### 2.3 Branch Protection (Optional but Recommended)

1. Go to **Settings** → **Branches**
2. Add rule for `main` branch:
   - **Require status checks to pass before merging**
   - **Require branches to be up to date before merging**
   - Add status check: `deploy-infrastructure`

---

## 3. Initial Deployment

### 3.1 Bootstrap CDK (One-time setup)

**CloudShell bootstrap (recommended for security):**

```bash
# In CloudShell - CDK is pre-installed
# Install/update to latest version
npm install -g aws-cdk

# Bootstrap CDK for your account/region
cdk bootstrap aws://$(aws sts get-caller-identity --query Account --output text)/us-east-1
```

**Alternative: Local bootstrap**

```bash
# Only if using local AWS CLI
cd cdk
pip install -r requirements.txt
cdk bootstrap aws://$(aws sts get-caller-identity --query Account --output text)/us-east-1 --profile personal
```

**Verify bootstrap (in CloudShell or locally):**
```bash
# Check available stacks
aws cloudformation list-stacks --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE --query 'StackSummaries[?contains(StackName, `CDKToolkit`)].StackName'
```

**Expected output:**
```
["CDKToolkit"]
```

### 3.2 First Deployment via GitHub Actions

**Method 1: Push to main branch**
```bash
git add .
git commit -m "Initial deployment setup"
git push origin main
```

**Method 2: Manual workflow dispatch**
1. Go to **Actions** tab in GitHub
2. Select **Deploy Goodreads Stats** workflow
3. Click **Run workflow**
4. Select environment: `prod`
5. Click **Run workflow**

### 3.3 Monitor Deployment

**GitHub Actions:**
- Watch the workflow progress in the **Actions** tab
- Both `deploy-infrastructure` and `deploy-frontend` jobs must succeed

**AWS CloudFormation:**
- Monitor stack creation in AWS Console → CloudFormation
- Expected stacks:
  - `GoodreadsStats-Prod-Storage`
  - `GoodreadsStats-Prod-Api`
  - `GoodreadsStats-Prod-Frontend`

**Deployment time:** ~15-20 minutes for initial deployment

---

## 4. Verification

### 4.1 Check Deployed Resources

**S3 Buckets:**
```bash
aws s3 ls | grep goodreads-stats
```
Expected:
```
goodreads-stats
goodreads-stats-website-prod
```

**Lambda Functions:**
```bash
aws lambda list-functions --query 'Functions[?contains(FunctionName, `GoodreadsStats`)].FunctionName'
```

**API Gateway:**
```bash
aws apigateway get-rest-apis --query 'items[?contains(name, `Goodreads`)].{Name:name,Id:id}'
```

**CloudFront Distribution:**
```bash
aws cloudfront list-distributions --query 'DistributionList.Items[?contains(Comment, `Goodreads`)].{Id:Id,Domain:DomainName}'
```

### 4.2 Test the Application

1. **Visit the website:** https://goodreads-stats.codebycarson.com
2. **Test API endpoint:**
   ```bash
   curl https://goodreads-stats.codebycarson.com/api/health
   ```
3. **Upload a CSV file** and verify processing works

### 4.3 Check DNS Resolution

```bash
# Check domain resolution
dig goodreads-stats.codebycarson.com

# Should return CloudFront distribution domain
nslookup goodreads-stats.codebycarson.com
```

---

## 5. Environment Management

### 5.1 Production Environment

- **Trigger:** Push to `main` or `master` branch
- **Domain:** `goodreads-stats.codebycarson.com`
- **Stack Prefix:** `GoodreadsStats-Prod-*`
- **S3 Buckets:**
  - Data: `goodreads-stats`
  - Website: `goodreads-stats-website-prod`

### 5.2 Development Environment

- **Trigger:** Push to any other branch
- **Domain:** `dev.goodreads-stats.codebycarson.com`
- **Stack Prefix:** `GoodreadsStats-Dev-*`
- **S3 Buckets:**
  - Data: `goodreads-stats-dev`
  - Website: `goodreads-stats-website-dev`

### 5.3 Manual Environment Selection

Use workflow dispatch to override automatic environment detection:

1. Go to **Actions** → **Deploy Goodreads Stats**
2. Click **Run workflow**
3. Select desired environment
4. Click **Run workflow**

---

## 6. Monitoring & Maintenance

### 6.1 CloudWatch Logs

**Lambda Function Logs:**
```bash
# Upload handler logs
aws logs tail /aws/lambda/GoodreadsStats-Prod-Api-UploadHandler --follow

# Orchestrator logs
aws logs tail /aws/lambda/GoodreadsStats-Prod-Api-Orchestrator --follow

# Status checker logs
aws logs tail /aws/lambda/GoodreadsStats-Prod-Api-StatusChecker --follow
```

### 6.2 Cost Monitoring

**Set up billing alerts:**

```bash
# Create SNS topic for billing alerts
aws sns create-topic --name goodreads-stats-billing-alerts

# Create CloudWatch alarm (replace PHONE_NUMBER)
aws cloudwatch put-metric-alarm \
    --alarm-name "GoodreadsStats-HighCosts" \
    --alarm-description "Alert when estimated charges exceed $10" \
    --metric-name EstimatedCharges \
    --namespace AWS/Billing \
    --statistic Maximum \
    --period 86400 \
    --threshold 10 \
    --comparison-operator GreaterThanThreshold \
    --dimensions Name=Currency,Value=USD
```

### 6.3 S3 Lifecycle Management

**Monitor S3 usage:**
```bash
# Check bucket sizes
aws s3 ls s3://goodreads-stats --recursive --human-readable --summarize

# View lifecycle rules
aws s3api get-bucket-lifecycle-configuration --bucket goodreads-stats
```

---

## 7. Troubleshooting

### 7.1 Common Deployment Issues

**CDK Bootstrap Errors:**
```bash
# Re-bootstrap with force
cdk bootstrap aws://$(aws sts get-caller-identity --query Account --output text)/us-east-1 --force
```

**GitHub Actions Failures:**
- Check AWS credentials are correct in GitHub Secrets
- Verify IAM user has required permissions
- Check CDK context in workflow logs

**Domain/SSL Issues:**
- Verify Route 53 hosted zone exists
- Ensure certificate is in `us-east-1` region
- Check DNS propagation: `dig goodreads-stats.codebycarson.com`

### 7.2 Lambda Function Issues

**Import Errors:**
```bash
# Check Lambda layer contents
aws lambda get-layer-version \
    --layer-name GoodreadsStats-Prod-Api-SharedLayer \
    --version-number 1
```

**Timeout Issues:**
- Monitor function duration in CloudWatch
- Increase timeout in CDK if needed
- Check concurrency limits

### 7.3 API Gateway Issues

**CORS Errors:**
- Verify origins in CDK configuration
- Check preflight OPTIONS requests
- Test with browser dev tools

**404 Errors:**
- Verify API Gateway deployment
- Check route configuration in CDK
- Test endpoints directly

### 7.4 Emergency Procedures

**Rollback Deployment:**
```bash
# Find previous stack version in CloudFormation
aws cloudformation describe-stacks --stack-name GoodreadsStats-Prod-Api

# Revert to previous commit and redeploy
git revert HEAD
git push origin main
```

**Complete Infrastructure Teardown:**
```bash
cd cdk
cdk destroy --all --context environment=prod
```

**Warning:** This will delete all data and resources!

---

## 8. Security Considerations

### 8.1 Access Control

- **Principle of least privilege** - IAM user has minimal required permissions
- **No hardcoded secrets** - All sensitive data in GitHub Secrets
- **HTTPS only** - CloudFront redirects HTTP to HTTPS
- **CORS restrictions** - API only accepts requests from allowed domains

### 8.2 Data Protection

- **Temporary storage** - CSV uploads deleted after processing
- **Public dashboard data** - Only processed JSONs are publicly readable
- **User-controlled deletion** - UUID-based data removal
- **No PII logging** - Logs don't contain user data

### 8.3 Cost Protection

- **Lifecycle policies** - Automatic cleanup of old data
- **Serverless scaling** - Pay per request
- **CloudWatch monitoring** - Track usage and costs
- **Free tier usage** - Optimized for AWS free tier

---

## 9. Architecture Summary

```
┌─────────────────────────────────────────────────────────────────┐
│                     DEPLOYMENT ARCHITECTURE                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  GitHub Repository                                              │
│  ├── Push to main → Production deployment                      │
│  ├── Push to branch → Development deployment                   │
│  ├── Manual workflow → Choose environment                      │
│  └── GitHub Actions (CI/CD)                                    │
│               ↓                                                 │
│  AWS CDK (Infrastructure as Code)                              │
│  ├── Storage Stack → S3 buckets + lifecycle policies          │
│  ├── API Stack → Lambda functions + API Gateway               │
│  └── Frontend Stack → CloudFront + Route 53 + SSL            │
│               ↓                                                 │
│  Running Infrastructure                                         │
│  ├── goodreads-stats.codebycarson.com (Production)            │
│  ├── dev.goodreads-stats.codebycarson.com (Development)       │
│  ├── Serverless processing pipeline                           │
│  └── Automatic scaling and cost optimization                  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 10. Next Steps

After successful deployment:

1. **Set up monitoring alerts** for errors and costs
2. **Configure backups** for critical data (if needed)
3. **Test the development environment** by pushing to a feature branch
4. **Document any custom configurations** for your specific use case
5. **Set up log aggregation** if you need centralized logging

## Support

For deployment issues:
1. Check GitHub Actions workflow logs
2. Review AWS CloudFormation events
3. Monitor CloudWatch logs for Lambda functions
4. Verify DNS and SSL certificate status
