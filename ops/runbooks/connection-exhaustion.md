# Connection Exhaustion Runbook

## Overview

This runbook provides step-by-step instructions for investigating and resolving database connection exhaustion issues in the Golden Path application.

## Symptoms

- Application returning 500 errors on `/db` endpoint
- High database connection count approaching limits
- CloudWatch alarm: `golden-path-rds-connections-{env}` triggered
- Users reporting slow database queries or timeouts
- Application logs showing connection pool errors

## Initial Assessment (5 minutes)

### 1. Check Database Connection Metrics

Navigate to: CloudWatch → Dashboards → `GoldenPath-{env}`

**Key Metrics to Review:**

- RDS Database Connections (current vs max)
- RDS CPU Utilization
- Application response times

### 2. Check Application Logs

```bash
# Check recent application logs for connection errors
aws logs start-query \
  --log-group-name "/ecs/golden-path-app-{env}" \
  --start-time $(date -d '15 minutes ago' +%s) \
  --end-time $(date +%s) \
  --query-string 'fields @timestamp, requestId, path, status, errorType | filter path = "/db" and (errorType = "connection_error" or ispresent(errorType)) | sort @timestamp desc | limit 20'
```

### 3. Check Database Status

```bash
# Check database connection count
aws cloudwatch get-metric-statistics \
  --namespace AWS/RDS \
  --metric-name DatabaseConnections \
  --dimensions Name=DBClusterIdentifier,Value=golden-path-aurora-{env} \
  --start-time $(date -d '1 hour ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 300 \
  --statistics Maximum,Average

# Check database cluster status
aws rds describe-db-clusters \
  --db-cluster-identifier golden-path-aurora-{env} \
  --query 'DBClusters[0].{Status:Status,Engine:Engine}'
```

## Investigation Steps

### 4. Analyze Connection Patterns

```bash
# Check connection count over time
aws cloudwatch get-metric-statistics \
  --namespace AWS/RDS \
  --metric-name DatabaseConnections \
  --dimensions Name=DBClusterIdentifier,Value=golden-path-aurora-{env} \
  --start-time $(date -d '1 hour ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 300 \
  --statistics Maximum \
  --query 'Datapoints[*].{Timestamp:Timestamp,Value:Maximum}' \
  | jq -r 'sort_by(.Timestamp) | .[] | "\(.Timestamp): \(.Value)"'

# Check for connection spikes
```

### 5. Check Application Task Count

```bash
# Check current ECS task count
aws ecs describe-services \
  --cluster golden-path-cluster-{env} \
  --services golden-path-service-{env} \
  --query 'services[0].{Running:runningCount,Desired:desiredCount,Pending:pendingCount}'
```

### 6. Check for Connection Leak Failure Mode

```bash
# Check if connection leak failure mode is enabled
aws ssm get-parameter \
  --name "/golden/failure_mode" \
  --query 'Parameter.Value'
```

## Common Root Causes & Solutions

### Cause 1: Connection Leak Failure Mode Enabled

**Symptoms:** Steadily increasing connection count, application not closing connections

**Investigation:**

- Check failure mode parameter value is "connection_leak"
- Monitor connection count increasing over time

**Resolution:**

```bash
# Reset failure mode to normal
aws ssm put-parameter \
  --name "/golden/failure_mode" \
  --value "none" \
  --type String \
  --overwrite

# Restart ECS tasks to clear existing connections
aws ecs update-service \
  --cluster golden-path-cluster-{env} \
  --service golden-path-service-{env} \
  --force-new-deployment
```

### Cause 2: High Task Count Causing Connection Overload

**Symptoms:** Connection count proportional to task count, autoscaling recently triggered

**Investigation:**

- Check recent autoscaling activities
- Correlate task count with connection count

**Resolution:**

```bash
# If connections are legitimate but too many, consider:
# 1. Implement connection pooling in application
# 2. Increase database connection limits
# 3. Optimize queries to reduce connection time

# For immediate relief, scale down if appropriate:
aws ecs update-service \
  --cluster golden-path-cluster-{env} \
  --service golden-path-service-{env} \
  --desired-count 2  # Adjust to appropriate level
```

### Cause 3: Missing Connection Pooling

**Symptoms:** Each request creates new database connection, connections not reused

**Investigation:**

- Application code review for connection management
- High connection turnover rate

**Resolution:**
This requires application code changes to implement connection pooling:

```python
# Example implementation with SQLAlchemy
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

# Create engine with connection pooling
engine = create_engine(
    'postgresql://user:password@host:port/dbname',
    poolclass=QueuePool,
    pool_size=10,        # Number of connections to maintain
    max_overflow=20,     # Additional connections beyond pool_size
    pool_pre_ping=True,  # Validate connections before use
    pool_recycle=3600,   # Recycle connections every hour
    pool_timeout=30      # Timeout when waiting for connection
)

# Use the engine for database operations
with engine.connect() as connection:
    result = connection.execute("SELECT 1")
    # Connection automatically returned to pool
```

## Immediate Actions (< 10 minutes)

### 1. Restart ECS Tasks

```bash
# Force new deployment to clear all connections
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

### 2. Scale Down Service (if appropriate)

```bash
# Reduce task count to decrease connection demand
aws ecs update-service \
  --cluster golden-path-cluster-{env} \
  --service golden-path-service-{env} \
  --desired-count 2  # Adjust based on normal operations
```

## Long-term Solutions

### 1. Implement RDS Proxy

```bash
# Create RDS Proxy for connection pooling
aws rds create-db-proxy \
  --db-proxy-name golden-path-proxy-{env} \
  --engine-family POSTGRESQL \
  --auth Description="Proxy authentication",AuthScheme=SECRETS,SecretArn=arn:aws:secretsmanager:region:account:secret:golden-path/db-credentials/{env} \
  --role-arn arn:aws:iam::{account-id}:role/rds-proxy-role-{env} \
  --vpc-subnet-ids subnet-{id1} subnet-{id2} \
  --vpc-security-group-ids sg-{id}

# Update application to use proxy endpoint instead of direct database
```

### 2. Optimize Application Connection Handling

- Implement proper connection pooling
- Ensure connections are closed after use
- Add connection timeouts
- Implement retry logic with exponential backoff

### 3. Monitor and Alert on Connection Usage

```bash
# Create enhanced CloudWatch alarm for connection usage
aws cloudwatch put-metric-alarm \
  --alarm-name golden-path-rds-connections-warning-{env} \
  --alarm-description "RDS connection usage approaching limit" \
  --metric-name DatabaseConnections \
  --namespace AWS/RDS \
  --statistic Maximum \
  --period 300 \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=DBClusterIdentifier,Value=golden-path-aurora-{env} \
  --evaluation-periods 2 \
  --alarm-actions arn:aws:sns:region:account:golden-path-alarms
```
