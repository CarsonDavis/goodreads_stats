# Troubleshooting

This guide covers common issues and their solutions for both local development and cloud production environments.

## Local Development Issues

### Docker Compose Won't Start

**Symptoms:** `docker-compose up` fails or containers exit immediately.

**Solutions:**

1. **Check Docker is running:**
   ```bash
   docker info
   ```

2. **Check port availability:**
   ```bash
   # Check if ports 8000 or 8001 are in use
   lsof -i :8000
   lsof -i :8001
   ```

3. **Rebuild containers:**
   ```bash
   docker-compose down
   docker-compose build --no-cache
   docker-compose up
   ```

4. **Check logs:**
   ```bash
   docker-compose logs api
   docker-compose logs frontend
   ```

---

### API Server Not Responding

**Symptoms:** `curl http://localhost:8001/health` times out or returns connection refused.

**Solutions:**

1. **Check if server is running:**
   ```bash
   docker-compose ps
   # or if running locally:
   ps aux | grep local_server
   ```

2. **Check server logs:**
   ```bash
   docker-compose logs api
   # or check terminal output if running manually
   ```

3. **Restart the API:**
   ```bash
   docker-compose restart api
   ```

4. **Check for missing dependencies:**
   ```bash
   uv pip install -r requirements.txt
   ```

---

### Upload Fails with "Invalid CSV Format"

**Symptoms:** Uploading a CSV returns error about invalid format.

**Causes:**
- CSV is not from Goodreads export
- CSV has been modified and is missing required columns

**Solutions:**

1. **Verify CSV has required columns:**
   ```bash
   head -1 your_file.csv
   # Should contain: Title, Author, My Rating, Date Read
   ```

2. **Re-export from Goodreads:**
   - Go to https://www.goodreads.com/review/import
   - Click "Export Library"
   - Download fresh CSV

3. **Check for encoding issues:**
   ```bash
   file your_file.csv
   # Should be "UTF-8 Unicode text"
   ```

---

### Processing Gets Stuck

**Symptoms:** Progress bar stops moving, status stays at "processing" indefinitely.

**Solutions:**

1. **Check API logs for errors:**
   ```bash
   docker-compose logs -f api
   ```

2. **Look for rate limiting:**
   - Google Books API may temporarily block requests
   - Wait a few minutes and try again

3. **Check if enrichment is failing:**
   - Look for "Enrichment failed" messages in logs
   - External APIs may be down

4. **Restart processing:**
   - Upload the CSV again to start fresh

---

### Dashboard Shows No Data

**Symptoms:** Dashboard page loads but charts are empty or show errors.

**Solutions:**

1. **Check UUID in URL:**
   - Ensure `?uuid=` parameter matches your processing job

2. **Check if JSON file exists:**
   ```bash
   ls dashboard_data/
   # Should contain {uuid}.json
   ```

3. **Verify JSON is valid:**
   ```bash
   python -m json.tool dashboard_data/{uuid}.json > /dev/null
   ```

4. **Check browser console:**
   - Open DevTools (F12)
   - Look for JavaScript errors
   - Check Network tab for failed requests

---

## Cloud Production Issues

### Upload Returns 403 Forbidden

**Symptoms:** POST to `/api/upload` returns 403 error.

**Causes:**
- CloudFront routing issue
- API Gateway configuration

**Solutions:**

1. **Verify API path:**
   - Use full path: `https://goodreads-stats.codebycarson.com/api/upload`
   - Not: `https://goodreads-stats.codebycarson.com/upload`

2. **Test API Gateway directly:**
   ```bash
   curl -X POST https://{api-id}.execute-api.us-east-1.amazonaws.com/prod/api/upload \
     -F "csv=@your_file.csv"
   ```

3. **Check CloudFront cache:**
   ```bash
   aws cloudfront create-invalidation --distribution-id XXXX --paths "/api/*"
   ```

---

### Processing Fails Immediately

**Symptoms:** Upload succeeds but status immediately shows "error".

**Causes:**
- Lambda function missing dependencies
- S3 bucket permissions

**Solutions:**

1. **Check Orchestrator logs:**
   ```bash
   aws logs tail /aws/lambda/GoodreadsStats-Prod-Api-Orchestrator... --since 1h
   ```

2. **Look for import errors:**
   - Common: `No module named 'genres'`
   - Lambda layer may not be configured correctly

3. **Check IAM permissions:**
   - Verify Lambda has read/write access to S3 bucket
   - Verify Lambda can invoke other Lambda functions

---

### Lambda Import Error: No Module Named 'genres'

**Symptoms:** Orchestrator logs show `Runtime.ImportModuleError: Unable to import module 'lambda_function': No module named 'genres'`

**Cause:** Lambda Layer not properly configured or deployed.

**Solutions:**

1. **Redeploy CDK stacks:**
   ```bash
   cd cdk
   cdk deploy --all
   ```

2. **Verify layer is attached:**
   ```bash
   aws lambda get-function --function-name GoodreadsStats-Prod-Api-Orchestrator... \
     --query 'Configuration.Layers'
   ```

3. **Check layer contents:**
   - Layer should contain `python/genres/` directory
   - Verify all dependencies are included

---

### SQS Messages Not Being Processed

**Symptoms:** Books are sent to queue but never processed; status stays at 40%.

**Causes:**
- BookProcessor Lambda not triggered by SQS
- Messages going to dead-letter queue

**Solutions:**

1. **Check SQS queue:**
   ```bash
   aws sqs get-queue-attributes \
     --queue-url https://sqs.us-east-1.amazonaws.com/ACCOUNT/goodreads-stats-books \
     --attribute-names ApproximateNumberOfMessages
   ```

2. **Check dead-letter queue:**
   - Messages may be failing and moved to DLQ
   - Check BookProcessor logs for errors

3. **Verify Lambda trigger:**
   ```bash
   aws lambda get-event-source-mapping \
     --function-name GoodreadsStats-Prod-Api-BookProcessor...
   ```

---

### Aggregator Never Runs

**Symptoms:** All books enriched but status never changes to "complete".

**Causes:**
- CloudWatch Events rule not triggering
- Aggregator failing silently

**Solutions:**

1. **Check CloudWatch Events rule:**
   ```bash
   aws events list-rules --name-prefix GoodreadsStats
   ```

2. **Manually trigger aggregator:**
   ```bash
   aws lambda invoke \
     --function-name GoodreadsStats-Prod-Api-Aggregator... \
     --payload '{"processing_uuid": "your-uuid"}' \
     output.json
   ```

3. **Check Aggregator logs:**
   ```bash
   aws logs tail /aws/lambda/GoodreadsStats-Prod-Api-Aggregator... --since 1h
   ```

---

## Frontend Issues

### Page Shows "Access Denied"

**Symptoms:** Visiting any page returns S3 access denied error.

**Causes:**
- CloudFront OAI configuration issue
- S3 bucket policy

**Solutions:**

1. **Invalidate CloudFront cache:**
   ```bash
   aws cloudfront create-invalidation --distribution-id XXXX --paths "/*"
   ```

2. **Check bucket policy:**
   ```bash
   aws s3api get-bucket-policy --bucket goodreads-stats-website-prod
   ```

3. **Verify files exist in S3:**
   ```bash
   aws s3 ls s3://goodreads-stats-website-prod/
   ```

---

### JavaScript Errors in Console

**Symptoms:** Dashboard doesn't load, browser console shows errors.

**Common Errors:**

1. **"Cannot read property of undefined"**
   - JSON data may be malformed
   - Check `data/{uuid}.json` structure

2. **"Failed to fetch"**
   - CORS issue
   - Check API endpoint URL

3. **"UUID not found"**
   - Processing job doesn't exist
   - UUID may have been deleted

---

### Dark Mode Not Working

**Symptoms:** Theme toggle doesn't persist or doesn't apply.

**Solutions:**

1. **Clear localStorage:**
   ```javascript
   localStorage.removeItem('darkMode');
   ```

2. **Check for CSS conflicts:**
   - Inspect element and verify classes are applied

---

## API Rate Limiting

### Google Books API

**Symptoms:** Many books fail enrichment with "rate limit" errors.

**Solutions:**

1. **Reduce concurrency:**
   - Edit `local_server.py`: `max_local_concurrent=5`

2. **Add delays:**
   - The pipeline has built-in rate limiting
   - If still hitting limits, wait and retry

3. **Use API key (optional):**
   - Register for Google Books API key
   - Set as environment variable

### Open Library API

**Symptoms:** Open Library requests failing.

**Solutions:**

1. **Check Open Library status:**
   - https://status.archivelab.org/

2. **Open Library is best-effort:**
   - System falls back to Google Books
   - Some books may not have subjects

---

## Diagnostic Commands

### Local Environment

```bash
# Check service health
curl http://localhost:8001/health

# View active processing jobs
curl http://localhost:8001/

# Check specific job status
curl http://localhost:8001/status/{uuid}

# View Docker logs
docker-compose logs -f api

# Check disk space for dashboard_data
du -sh dashboard_data/
```

### AWS Environment

```bash
# List Lambda functions
aws lambda list-functions --query 'Functions[?starts_with(FunctionName, `GoodreadsStats`)].FunctionName'

# Check recent Lambda errors
aws logs filter-log-events \
  --log-group-name '/aws/lambda/GoodreadsStats-Prod-Api-Orchestrator...' \
  --filter-pattern "ERROR" \
  --start-time $(($(date +%s) - 3600))000

# Check S3 bucket contents
aws s3 ls s3://goodreads-stats-data-prod/status/
aws s3 ls s3://goodreads-stats-data-prod/data/

# View CloudFront distribution
aws cloudfront get-distribution --id XXXX --query 'Distribution.Status'
```

---

## Getting Help

If you're still stuck:

1. **Check existing issues:** https://github.com/carsondavis/goodreads_stats/issues
2. **Open a new issue** with:
   - Steps to reproduce
   - Error messages (from logs)
   - Environment (local/cloud)
   - Screenshot if applicable
