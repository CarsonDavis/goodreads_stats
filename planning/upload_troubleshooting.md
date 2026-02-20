# Upload Troubleshooting Guide

## Current Status: Upload Working, Processing Failing

### Issue Summary

✅ **File Upload**: Working correctly after API Gateway configuration fixes
❌ **Processing**: Failing due to missing Python module dependencies in Lambda

### Root Cause

The orchestrator Lambda function cannot import the `genres` module, causing immediate failure when processing begins. Error: `Runtime.ImportModuleError: Unable to import module 'lambda_function': No module named 'genres'`

### How to Confirm the Issue

1. **Check Upload Handler Logs** (should show successful file receipt):
   ```bash
   aws logs tail /aws/lambda/GoodreadsStats-Prod-Api-UploadHandler4CB020C5-ff7k1bizLPFZ --since 1h --profile personal
   ```
   Look for: Base64 encoded CSV data in the logs

2. **Check Orchestrator Logs** (should show import errors):
   ```bash
   aws logs tail /aws/lambda/GoodreadsStats-Prod-Api-Orchestrator6EF1216F-dANfyO3Bscfp --since 1h --profile personal
   ```
   Look for: `Runtime.ImportModuleError: Unable to import module 'lambda_function': No module named 'genres'`

3. **Frontend Behavior**:
   - Upload progress reaches ~10% (file uploaded successfully)
   - Gets stuck polling for status
   - Eventually times out with "Processing timed out. Please try again."

### Previous Fixes Applied

1. **API Gateway Binary Media Support**: 
   - Added `binary_media_types=["multipart/form-data", "*/*"]` to RestApi
   - Changed upload integration to `proxy=True`
   - Removed explicit integration responses

2. **Frontend Timeout**:
   - Increased polling timeout from 10 minutes to 20 minutes

### Next Steps

The Lambda layer configuration in CDK needs to be fixed to properly bundle the `genres` module and its dependencies for the orchestrator function.

### Testing the Fix

After deploying the Lambda layer fix:

1. Upload a CSV file through the web interface
2. Monitor orchestrator logs for successful import and processing start
3. Verify the processing completes and creates dashboard data

### Log Group Names (for reference)

- Upload Handler: `/aws/lambda/GoodreadsStats-Prod-Api-UploadHandler4CB020C5-ff7k1bizLPFZ`
- Orchestrator: `/aws/lambda/GoodreadsStats-Prod-Api-Orchestrator6EF1216F-dANfyO3Bscfp`
- Status Checker: `/aws/lambda/GoodreadsStats-Prod-Api-StatusChecker11743A0C-ajMunhbcXh8H`