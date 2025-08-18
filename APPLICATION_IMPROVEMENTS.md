# Application Best Practices Improvements

## 1. Container Image Security
```dockerfile
# Use specific version tags, not latest
FROM python:3.11-slim

# Add security scanning
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Use distroless or minimal base images for production
# FROM gcr.io/distroless/python3-debian11
```

## 2. Database Connection Management
```python
# Add proper connection pooling
import asyncpg
from sqlalchemy.pool import QueuePool

# Use connection pooling
engine = create_async_engine(
    database_url,
    poolclass=QueuePool,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=3600
)
```

## 3. Secrets Management
```python
# Fetch secrets at runtime, not startup
async def get_db_credentials():
    """Fetch fresh credentials from Secrets Manager"""
    try:
        response = await secrets_client.get_secret_value(SecretId=DB_SECRET_ARN)
        return json.loads(response['SecretString'])
    except Exception as e:
        logger.error("Failed to fetch credentials", error=str(e))
        raise
```

## 4. Health Check Improvements
```python
@app.get("/healthz")
async def health_check():
    """Enhanced health check with dependency validation"""
    checks = {
        "database": await check_database_connection(),
        "secrets_manager": await check_secrets_access(),
        "parameter_store": await check_parameter_access()
    }
    
    if all(checks.values()):
        return {"status": "healthy", "checks": checks}
    else:
        raise HTTPException(status_code=503, detail={"status": "unhealthy", "checks": checks})
```

## 5. Observability Enhancements
```python
# Add custom metrics
import boto3
cloudwatch = boto3.client('cloudwatch')

async def put_custom_metric(metric_name: str, value: float, unit: str = 'Count'):
    """Send custom metrics to CloudWatch"""
    try:
        cloudwatch.put_metric_data(
            Namespace='GoldenPath/Application',
            MetricData=[
                {
                    'MetricName': metric_name,
                    'Value': value,
                    'Unit': unit,
                    'Dimensions': [
                        {
                            'Name': 'Environment',
                            'Value': os.getenv('ENVIRONMENT', 'dev')
                        }
                    ]
                }
            ]
        )
    except Exception as e:
        logger.warning(f"Failed to send metric {metric_name}", error=str(e))
```