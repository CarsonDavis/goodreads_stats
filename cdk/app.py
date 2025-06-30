#!/usr/bin/env python3
"""
CDK Application for Goodreads Stats
"""
import os
import aws_cdk as cdk
from stacks.storage_stack import StorageStack
from stacks.api_stack import ApiStack
from stacks.frontend_stack import FrontendStack

app = cdk.App()

# Get environment from context or environment variables
environment = app.node.try_get_context("environment") or os.environ.get("ENVIRONMENT", "prod")
account = app.node.try_get_context("account") or os.environ.get("CDK_DEFAULT_ACCOUNT")
region = app.node.try_get_context("region") or os.environ.get("CDK_DEFAULT_REGION", "us-east-1")

# Environment configuration
env = cdk.Environment(account=account, region=region)

# Stack name prefix based on environment
stack_prefix = f"GoodreadsStats-{environment.title()}"

# Deploy stacks in dependency order
storage_stack = StorageStack(
    app, f"{stack_prefix}-Storage", 
    environment=environment,
    env=env
)

api_stack = ApiStack(
    app, f"{stack_prefix}-Api",
    storage_stack=storage_stack,
    environment=environment,
    env=env
)

frontend_stack = FrontendStack(
    app, f"{stack_prefix}-Frontend",
    api_stack=api_stack,
    storage_stack=storage_stack,
    environment=environment,
    env=env
)

# Tag all resources
cdk.Tags.of(app).add("Project", "GoodreadsStats")
cdk.Tags.of(app).add("Environment", environment)
cdk.Tags.of(app).add("Repository", "goodreads_stats")

app.synth()