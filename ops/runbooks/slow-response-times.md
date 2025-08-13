# Slow Response Times Runbook

## Overview

This runbook provides step-by-step instructions for investigating and resolving slow response times (high p95 latency) in the Golden Path application.

## Symptoms

- ALB TargetResponseTime p95 > 2 seconds for 10+ minutes
- CloudWatch alarm: `golden-path-alb-response-time-{env}` triggered
- Users reporting slow application performance

## Initial Assessment (5 minutes)

### 1. Check Current Response Times

Navigate to: CloudWatch → Dashboards → `GoldenPath-{env}`

**Key Metrics to Review:**

- ALB Response Times widget (Average vs p95)
- Request Count Per Target
- ECS CPU/Memory Utilization
- ECS Running Task Count

### 2. Identify Affected Endpoints

```bash
# Check slow requests by endpoint
aws logs start-query \
  --log-group-name "/ecs/golden-path-app-{env}" \
  --start-time $(date -d '30 minutes ago' +%s) \
  --end-time $(date +%s) \
  --query-string 'fields @timestamp, requestId, path, latencyMs | filter latencyMs > 1000 | stats avg(latencyMs), max(latencyMs), count() by path | sort avg desc'
```

### 3. Check X-Ray Service Map

Navigate to: X-Ray → Service Map

- Look for services with high latency
- Identify bottlenecks in the request flow
- Check for external dependency issues

## Investigation Steps

### 4. Analyze Request Patterns

```bash
# Check request volume trends
aws logs start-query \
  --log-group-name "/ecs/golden-path-app-{env}" \
  --start-time $(date -d '1 hour ago' +%s) \
  --end-time $(date +%s) \
  --query-string 'stats count() by bin(5m) | sort @timestamp'

# Check for specific slow endpoints
aws logs start-query \
  --log-group-name "/ecs/golden-path-app-{env}" \
  --start-time $(date -d '30 minutes ago' +%s) \
  --end-time $(date +%s) \
  --query-string 'fields @timestamp, path, latencyMs | filter path = "/work" | stats avg(latencyMs), max(latencyMs), count() by bin(5m)'
```

### 5. Check Resource Utilization

```bash
# Check ECS CPU utilization
aws cloudwatch get-metric-statistics \
  --namespace AWS/ECS \
  --metric-name CPUUtilization \
  --dimensions Name=ServiceName,Value=golden-path-service-{env} Name=ClusterName,Value=golden-path-cluster-{env} \
  --start-time $(date -d '1 hour ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 300 \
  --statistics Average,Maximum

# Check ECS memory utilization
aws cloudwatch get-metric-statistics \
  --namespace AWS/ECS \
  --metric-name MemoryUtilization \
  --dimensions Name=ServiceName,Value=golden-path-service-{env} Name=ClusterName,Value=golden-path-cluster-{env} \
  --start-time $(date -d '1 hour ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 300 \
  --statistics Average,Maximum
```

### 6. Check Database Performance

```bash
# Check RDS CPU utilization
aws cloudwatch get-metric-statistics \
  --namespace AWS/RDS \
  --metric-name CPUUtilization \
  --dimensions Name=DBClusterIdentifier,Value=golden-path-aurora-{env} \
  --start-time $(date -d '1 hour ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 300 \
  --statistics Average,Maximum

# Check database connections
aws cloudwatch get-metric-statistics \
  --namespace AWS/RDS \
  --metric-name DatabaseConnections \
  --dimensions Name=DBClusterIdentifier,Value=golden-path-aurora-{env} \
  --start-time $(date -d '1 hour ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 300 \
  --statistics Average,Maximum
```

## Common Root Causes & Solutions

### Cause 1: High CPU Load from /work Endpoint

**Symptoms:** High CPU utilization, `/work` endpoint with high latency

**Investigation:**

```bash
# Check /work endpoint usage
aws logs start-query \
  --log-group-name "/ecs/golden-path-app-{env}" \
  --start-time $(date -d '30 minutes ago' +%s) \
  --end-time $(date +%s) \
  --query-string 'fields @timestamp, path, latencyMs | filter path = "/work" | stats count(), avg(latencyMs) by bin(5m)'
```

**Resolution:**

- Scale out ECS service to handle load
- Implement rate limiting on `/work` endpoint
- Check if load testing is running

```bash
# Scale out ECS service
aws ecs update-service \
  --cluster golden-path-cluster-{env} \
  --service golden-path-service-{env} \
  --desired-count 4
```

### Cause 2: Database Performance Issues

**Symptoms:** `/db` endpoint slow, high database CPU/connections

**Investigation:**

- Check RDS Performance Insights
- Review slow query logs
- Check for connection leaks

**Resolution:**

```bash
# Check for connection leak failure mode
aws ssm get-parameter --name "/golden/failure_mode"

# Reset if connection leak mode is active
aws ssm put-parameter \
  --name "/golden/failure_mode" \
  --value "none" \
  --type String \
  --overwrite

# Restart ECS tasks to clear connections
aws ecs update-service \
  --cluster golden-path-cluster-{env} \
  --service golden-path-service-{env} \
  --force-new-deployment
```

### Cause 3: Insufficient Capacity

**Symptoms:** High request count per target, resource exhaustion

**Investigation:**

```bash
# Check request count per target
aws cloudwatch get-metric-statistics \
  --namespace AWS/ApplicationELB \
  --metric-name RequestCountPerTarget \
  --dimensions Name=LoadBalancer,Value=<ALB_FULL_NAME> \
  --start-time $(date -d '1 hour ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 300 \
  --statistics Average,Maximum
```

**Resolution:**

```bash
# Scale out ECS service
aws ecs update-service \
  --cluster golden-path-cluster-{env} \
  --service golden-path-service-{env} \
  --desired-count 6

# Check autoscaling configuration
aws application-autoscaling describe-scaling-policies \
  --service-namespace ecs \
  --resource-id service/golden-path-cluster-{env}/golden-path-service-{env}
```

### Cause 4: External Dependency Issues

**Symptoms:** X-Ray traces show external service delays

**Investigation:**

- Review X-Ray traces for external calls
- Check AWS service health dashboard
- Verify network connectivity

**Resolution:**

- Implement circuit breakers
- Add retry logic with exponential backoff
- Consider caching for external data

## Performance Optimization Actions

### Immediate (< 5 minutes)

1. **Scale out ECS service** if resource constrained
2. **Reset failure modes** that cause artificial delays
3. **Check for load testing** and coordinate if needed

### Short-term (< 30 minutes)

1. **Optimize slow endpoints** identified in logs
2. **Implement caching** for frequently accessed data
3. **Tune autoscaling policies** for faster response

### Long-term

1. **Add performance monitoring** at application level
2. **Implement connection pooling** for database
3. **Add CDN** for static content
4. **Optimize database queries** and indexing

## X-Ray Trace Analysis

### 1. Access X-Ray Console

Navigate to: X-Ray → Traces

### 2. Filter Traces

- Time range: Last 30 minutes
- Filter: `responsetime > 2`
- Sort by: Response time (descending)

### 3. Analyze Slow Traces

Look for:

- Database query times
- External service calls
- Application processing time
- Network latency

### 4. Common Patterns

```bash
# Get trace summaries for analysis
aws xray get-trace-summaries \
  --time-range-type TimeRangeByStartTime \
  --start-time $(date -d '30 minutes ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --filter-expression 'responsetime > 2'
```

## Verification Steps

### 1. Monitor Response Time Improvement

```bash
# Check current p95 response time
aws cloudwatch get-metric-statistics \
  --namespace AWS/ApplicationELB \
  --metric-name TargetResponseTime \
  --dimensions Name=LoadBalancer,Value=<ALB_FULL_NAME> \
  --start-time $(date -d '10 minutes ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 300 \
  --statistics Average,p95
```

### 2. Test Application Performance

```bash
# Test response times
time curl -s https://<ALB_DNS_NAME>/
time curl -s https://<ALB_DNS_NAME>/db
time curl -s "https://<ALB_DNS_NAME>/work?ms=100"
```

### 3. Verify Autoscaling Response

```bash
# Check current task count
aws ecs describe-services \
  --cluster golden-path-cluster-{env} \
  --services golden-path-service-{env} \
  --query 'services[0].{Running:runningCount,Desired:desiredCount,Pending:pendingCount}'
```

## Load Testing Coordination

If load testing is causing the issue:

### 1. Identify Load Test Source

```bash
# Check for patterns in user agents or source IPs
aws logs start-query \
  --log-group-name "/ecs/golden-path-app-{env}" \
  --start-time $(date -d '30 minutes ago' +%s) \
  --end-time $(date +%s) \
  --query-string 'stats count() by userAgent | sort count desc | limit 10'
```

### 2. Coordinate with Testing Team

- Verify if load test is planned
- Request test parameters and duration
- Ensure monitoring is in place

### 3. Prepare Infrastructure

```bash
# Pre-scale for known load tests
aws ecs update-service \
  --cluster golden-path-cluster-{env} \
  --service golden-path-service-{env} \
  --desired-count 8
```

## Escalation

**Escalate if:**

- Response times don't improve within 20 minutes
- Resource scaling doesn't help
- Database performance issues identified
- Infrastructure limits reached

**Escalation Contacts:**

- Performance Engineering: [Contact Info]
- Database Team: [Contact Info]
- Platform Team: [Contact Info]

## Useful Commands Reference

```bash
# Get current ECS service metrics
aws ecs describe-services --cluster golden-path-cluster-{env} --services golden-path-service-{env} --query 'services[0].{Status:status,Running:runningCount,Desired:desiredCount,CPU:taskDefinition}'

# Force ECS service scaling
aws ecs update-service --cluster golden-path-cluster-{env} --service golden-path-service-{env} --desired-count 6

# Check autoscaling activity
aws application-autoscaling describe-scaling-activities --service-namespace ecs --resource-id service/golden-path-cluster-{env}/golden-path-service-{env}

# Get ALB target health
aws elbv2 describe-target-health --target-group-arn <TARGET_GROUP_ARN>
```
