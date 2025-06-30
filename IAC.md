# Goodreads Stats - Infrastructure as Code

## Overview

The Goodreads Stats infrastructure is defined and provisioned using the **AWS Cloud Development Kit (CDK)**. This IaC approach allows for repeatable, version-controlled, and automated deployments. The infrastructure is divided into three main stacks: `StorageStack`, `ApiStack`, and `FrontendStack`.

## Directory Structure

```
goodreads_stats/
├── cdk/
│   ├── app.py                    # CDK application entry point
│   ├── cdk.json                  # CDK configuration
│   ├── requirements.txt          # Python dependencies for CDK
│   ├── stacks/
│   │   ├── storage_stack.py      # S3 buckets and IAM policies
│   │   ├── api_stack.py          # API Gateway and Lambda functions
│   │   └── frontend_stack.py     # CloudFront, Route 53, and SSL certs
│   └── lambda_code/
│       ├── orchestrator/         # Main data processing Lambda
│       ├── shared/               # Shared code and dependencies for Lambdas
│       ├── status_checker/       # Lambda for checking processing status
│       └── upload_handler/       # Lambda for handling file uploads
└── .github/
    └── workflows/
        └── deploy.yml            # GitHub Actions CI/CD pipeline
```

---

## AWS CDK Stacks

### `StorageStack` (`cdk/stacks/storage_stack.py`)

This stack is responsible for creating the S3 buckets used by the application.

*   **Data Bucket:**
    *   A single bucket named `goodreads-stats` (or `goodreads-stats-<env>`) stores all application data.
    *   **Prefixes:**
        *   `uploads/`: For temporary storage of uploaded CSV files.
        *   `data/`: For the final, enriched JSON dashboard data.
        *   `status/`: For tracking the status of processing jobs.
    *   **Lifecycle Policies:**
        *   Uploads are automatically deleted after 7 days.
        *   Dashboard data is moved to Infrequent Access storage after 90 days.
*   **Website Bucket:**
    *   Hosts the static frontend files (HTML, CSS, JS).
    *   In production, this bucket is private and accessed via a CloudFront Origin Access Identity (OAI).

### `ApiStack` (`cdk/stacks/api_stack.py`)

This stack defines the serverless backend, including the API Gateway and Lambda functions.

*   **API Gateway:**
    *   Provides a RESTful API with endpoints for `/upload`, `/status/{uuid}`, and `/data/{uuid}`.
    *   Handles CORS to allow requests from the frontend domain.
*   **Lambda Functions:**
    *   **`UploadHandler`:** Triggered by the `/upload` endpoint. It receives the CSV file, saves it to the `uploads/` prefix in S3, and asynchronously invokes the `Orchestrator` function.
    *   **`Orchestrator`:** Performs the core data enrichment, fetching data from the Google Books and Open Library APIs.
    *   **`StatusChecker`:** Provides the processing status to the frontend.
*   **Lambda Layer:**
    *   A shared Lambda Layer contains common Python dependencies (`requests`, `pandas`, etc.) to reduce the size of each Lambda function package.

### `FrontendStack` (`cdk/stacks/frontend_stack.py`)

This stack configures the public-facing part of the application.

*   **CloudFront:**
    *   Acts as a CDN for the static website assets, improving performance.
    *   Routes API requests to the API Gateway.
    *   **Error Handling:** Configured to return `/index.html` for 403 and 404 errors. This is the cause of the bug where navigating to a page like `/dashboard` doesn't work as expected.
*   **Route 53:**
    *   Creates an `A` record to point the custom domain (e.g., `goodreads-stats.codebycarson.com`) to the CloudFront distribution.
*   **ACM (Certificate Manager):**
    *   Provisions and manages the SSL/TLS certificate for the custom domain, enabling HTTPS.

---

## Deployment Pipeline (`.github/workflows/deploy.yml`)

The deployment process is automated with GitHub Actions.

*   **Trigger:** The workflow runs on pushes to the `main` branch or can be triggered manually.
*   **Jobs:**
    1.  `deploy-infrastructure`: Installs CDK dependencies and runs `cdk deploy --all` to provision the AWS resources.
    2.  `deploy-frontend`: Syncs the static files from the `dashboard/` directory to the S3 website bucket and creates a CloudFront invalidation to ensure the changes are deployed immediately.
