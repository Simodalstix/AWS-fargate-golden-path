# DB Authentication Failures Runbook

## Overview

This runbook provides step-by-step instructions for investigating and resolving database authentication failures in the Golden Path application.

## Symptoms

- Application returning 500 errors on `/db` endpoint
- CloudWatch alarm: Database authentication failure detected
- Users reporting database connection errors
- Application logs showing database authentication failures

## Initial Assessment (5 minutes)

### 1. Check Application Logs

```bash
# Check recent application logs for database errors
aws logs start-query \
  --log-group-name "/ecs/golden-path-app-{env}" \
  --start-time $(date -d '15 minutes ago' +%s) \
  --end-time $(date +%s) \
  --query-string 'fields @timestamp, requestId, path, status, errorType | filter path = "/db" and ispresent(errorType) | sort @timestamp desc | limit 20'
```

### 2. Check Database Metrics

Navigate to: CloudWatch → Dashboards → `GoldenPath-{env}`

**Key Metrics to Review:**

- RDS Database Connections
- RDS CPU Utilization
- RDS Free Storage Space

### 3. Verify Database Status

```bash
# Check database cluster status
aws rds describe-db-clusters \
  --db-cluster-identifier golden-path-aurora-{env} \
  --query 'DBClusters[0].{Status:Status,Engine:EngineVersion}'

# Check database instance status (if using RDS instance)
aws rds describe-db-instances \
  --db-instance-identifier golden-path-postgres-{env} \
  --query 'DBInstances[0].{Status:DBInstanceStatus,Engine:Engine}'
```

## Investigation Steps

### 4. Check Secret Rotation Status

```bash
# Check if secret rotation is enabled
aws secretsmanager describe-secret \
  --secret-id golden-path/db-credentials/{env} \
  --query 'RotationEnabled'

# Check rotation state if enabled
aws secretsmanager describe-secret \
  --secret-id golden-path/db-credentials/{env} \
  --query 'RotationState'
```

### 5. Validate Current Secret

```bash
# Get current secret value
aws secretsmanager get-secret-value \
  --secret-id golden-path/db-credentials/{env} \
  --query 'SecretString' \
  | jq -r

# Check if application is using outdated credentials
# This requires checking application logs for credential errors
```

### 6. Check Application Environment Variables

```bash
# Check ECS task definition for environment variables
aws ecs describe-task-definition \
  --task-definition $(aws ecs describe-services \
    --cluster golden-path-cluster-{env} \
    --services golden-path-service-{env} \
    --query 'services[0].taskDefinition' \
    --output text) \
  --query 'taskDefinition.containerDefinitions[0].environment'
```

## Common Root Causes & Solutions

### Cause 1: Secret Rotation Without Application Restart

**Symptoms:** Database authentication failures after secret rotation, application using old credentials

**Investigation:**

- Check if secret was recently rotated in Secrets Manager
- Verify application logs show authentication errors with old credentials

**Resolution:**

```bash
# Force redeploy ECS service to pick up new credentials
aws ecs update-service \
  --cluster golden-path-cluster-{env} \
  --service golden-path-service-{env} \
  --force-new-deployment

# Monitor deployment progress
aws ecs describe-services \
  --cluster golden-path-cluster-{env} \
  --services golden-path-service-{env} \
  --query 'services[0].deployments[*].{Status:status,TaskCount:runningCount}'
```

### Cause 2: Incorrect Secret Format or Content

**Symptoms:** Application fails to parse secret, database connection fails immediately

**Investigation:**

```bash
# Validate secret format
aws secretsmanager get-secret-value \
  --secret-id golden-path/db-credentials/{env} \
  --query 'SecretString' \
  | jq -r '.' > /tmp/current-secret.json

# Check secret structure matches expected format
cat /tmp/current-secret.json | jq -r 'keys'
# Should contain: username, password, engine, host, port, dbname, dbInstanceIdentifier
```

**Resolution:**

```bash
# Update secret with correct format (example)
aws secretsmanager put-secret-value \
  --secret-id golden-path/db-credentials/{env} \
  --secret-string '{"username":"dbadmin","password":"NEW_PASSWORD","engine":"postgres","host":"HOST_ENDPOINT","port":5432,"dbname":"goldenpath","dbInstanceIdentifier":"golden-path-aurora-{env}"}'
```

### Cause 3: Database User Permissions Issue

**Symptoms:** Authentication succeeds but access denied to database objects

**Investigation:**

- Check database logs for permission errors
- Verify database user exists and has proper permissions

**Resolution:**

```bash
# Connect to database and check user permissions
# This would typically be done via bastion host or RDS proxy
# Example SQL commands:
# \du -- List users
# \l -- List databases
# \dp -- List permissions
```

## Long-term Solutions

### 1. Implement Runtime Credential Fetching

Modify application to fetch credentials on each connection rather than at startup:

```python
# Example implementation
import boto3
import json

def get_db_credentials(secret_arn):
    """Fetch database credentials from Secrets Manager"""
    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name='us-east-1'  # Replace with your region
    )

    get_secret_value_response = client.get_secret_value(
        SecretId=secret_arn
    )

    secret = json.loads(get_secret_value_response['SecretString'])
    return secret

# Use this function before each database connection
```

### 2. Implement RDS Proxy

```bash
# Create RDS Proxy (requires additional infrastructure)
aws rds create-db-proxy \
  --db-proxy-name golden-path-proxy-{env} \
  --engine-family POSTGRESQL \
  --auth Description="Proxy authentication",AuthScheme=SECRETS,SecretArn=golden-path/db-credentials/{env} \
  --role-arn arn:aws:iam::{account-id}:role/rds-proxy-role-{env} \
  --vpc-subnet-ids subnet-{id1} subnet-{id2} \
  --vpc-security-group-ids sg-{id}
```

### 3. Implement Connection Pooling

```python
# Example using SQLAlchemy connection pooling
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

# Create engine with connection pooling
engine = create_engine(
    'postgresql://user:password@host:port/dbname',
    poolclass=QueuePool,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,  # Validates connections before use
    pool_recycle=3600     # Recycle connections every hour
)
```

## Verification Steps

### 1. Test Database Connection

```bash
# Test database endpoint connectivity
curl -f https://<ALB_DNS_NAME>/db

# Check database connection count
aws cloudwatch get-metric-statistics \
  --namespace AWS/RDS \
  --metric-name DatabaseConnections \
  --dimensions Name=DBClusterIdentifier,Value=golden-path-aurora-{env} \
  --start-time $(date -d '10 minutes ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 300 \
  --statistics Average
```

### 2. Monitor Application Logs

```bash
# Check for database errors in logs
aws logs filter-log-events \
  --log-group-name "/ecs/golden-path-app-{env}" \
  --start-time $(date -d '5 minutes ago' +%s)000 \
  --filter-pattern "database OR db OR auth OR credential"
```

### 3. Confirm Service Health

```bash
# Check ECS service health
aws ecs describe-services \
  --cluster golden-path-cluster-{env} \
  --services golden-path-service-{env} \
  --query 'services[0].{Status:status,Running:runningCount,Desired:desiredCount}'

# Check ALB target health
aws elbv2 describe-target-health \
  --target-group-arn <TARGET_GROUP_ARN>
```

## Escalation

**Escalate if:**

- Database authentication issues persist after redeployment
- Database infrastructure issues identified
- Multiple services affected by database issues

**Escalation Contacts:**

- Database Team: [Contact Info]
- Security Team: [Contact Info]
- Platform Team: [Contact Info]

## Useful Commands Reference

```bash
# Get database endpoint
aws rds describe-db-clusters \
  --db-cluster-identifier golden-path-aurora-{env} \
  --query 'DBClusters[0].Endpoint'

# Check secret rotation history
aws secretsmanager describe-secret \
  --secret-id golden-path/db-credentials/{env} \
  --query 'LastChangedDate'

# Force new deployment
aws ecs update-service \
  --cluster golden-path-cluster-{env} \
  --service golden-path-service-{env} \
  --force-new-deployment

# Check deployment status
aws ecs describe-services \
  --cluster golden-path-cluster-{env} \
  --services golden-path-service-{env} \
  --query 'services[0].deployments[*].{Status:status,UpdatedAt:updatedAt,TaskCount:runningCount}'
```
