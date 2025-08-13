# ALB 5xx Spike Runbook

## Overview

This runbook provides step-by-step instructions for investigating and resolving ALB 5xx error spikes in the Golden Path application.

## Symptoms

- ALB 5xx error rate > 1% for 5+ minutes
- CloudWatch alarm: `golden-path-alb-5xx-{env}` triggered
- Users reporting application errors or timeouts

## Initial Assessment (5 minutes)

### 1. Check ALB Target Health

```bash
# Get target group ARN from CloudFormation outputs
aws elbv2 describe-target-health --target-group-arn <TARGET_GROUP_ARN>
```

**Expected Output:**

- All targets should show `State: healthy`
- If targets are unhealthy, proceed to ECS service investigation

### 2. Check CloudWatch Dashboard

Navigate to: CloudWatch → Dashboards → `GoldenPath-{env}`

**Key Metrics to Review:**

- ALB HTTP Status Codes widget
- ALB Response Times widget
- ECS CPU/Memory Utilization
- ECS Running Task Count

### 3. Quick Log Analysis

```bash
# Check recent application logs for errors
aws logs start-query \
  --log-group-name "/ecs/golden-path-app-{env}" \
  --start-time $(date -d '15 minutes ago' +%s) \
  --end-time $(date +%s) \
  --query-string 'fields @timestamp, requestId, path, status, errorType, latencyMs | filter status >= 500 | sort @timestamp desc | limit 20'
```

## Investigation Steps

### 4. Analyze Error Patterns

```bash
# Get error breakdown by endpoint
aws logs start-query \
  --log-group-name "/ecs/golden-path-app-{env}" \
  --start-time $(date -d '1 hour ago' +%s) \
  --end-time $(date +%s) \
  --query-string 'stats count() by path, status | filter status >= 500 | sort count desc'
```

### 5. Check ECS Service Health

```bash
# Get ECS service details
aws ecs describe-services \
  --cluster golden-path-cluster-{env} \
  --services golden-path-service-{env}

# Check recent ECS events
aws ecs describe-services \
  --cluster golden-path-cluster-{env} \
  --services golden-path-service-{env} \
  --query 'services[0].events[0:10]'
```

### 6. Review X-Ray Traces

Navigate to: X-Ray → Traces

- Filter by time range of the incident
- Look for high latency or error traces
- Identify bottlenecks in service map

## Common Root Causes & Solutions

### Cause 1: Application Failure Mode Enabled

**Symptoms:** All requests returning 500, health checks failing

**Investigation:**

```bash
# Check failure mode parameter
aws ssm get-parameter --name "/golden/failure_mode"
```

**Resolution:**

```bash
# Reset failure mode to normal
aws ssm put-parameter \
  --name "/golden/failure_mode" \
  --value "none" \
  --type String \
  --overwrite
```

### Cause 2: Database Connection Issues

**Symptoms:** `/db` endpoint errors, connection timeouts

**Investigation:**

```bash
# Check RDS metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/RDS \
  --metric-name DatabaseConnections \
  --dimensions Name=DBClusterIdentifier,Value=golden-path-aurora-{env} \
  --start-time $(date -d '1 hour ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 300 \
  --statistics Average
```

**Resolution:**

- If connection count is high, restart ECS tasks to clear connections
- Consider implementing connection pooling
- Check for connection leak failure mode

### Cause 3: Resource Exhaustion

**Symptoms:** High CPU/memory, slow response times

**Investigation:**

- Check ECS CPU/Memory metrics in dashboard
- Review autoscaling activity

**Resolution:**

```bash
# Scale out ECS service manually if needed
aws ecs update-service \
  --cluster golden-path-cluster-{env} \
  --service golden-path-service-{env} \
  --desired-count 4
```

### Cause 4: Deployment Issues

**Symptoms:** Errors started after recent deployment

**Investigation:**

```bash
# Check recent CodeDeploy deployments
aws deploy list-deployments \
  --application-name golden-path-app-{env} \
  --max-items 5
```

**Resolution:**

```bash
# Rollback via CodeDeploy
aws deploy create-deployment \
  --application-name golden-path-app-{env} \
  --deployment-group-name golden-path-dg-{env} \
  --revision revisionType=S3,s3Location={bucket=<BUCKET>,key=<PREVIOUS_VERSION>,bundleType=zip}
```

## Recovery Actions

### Immediate (< 5 minutes)

1. **Reset failure mode** if enabled
2. **Scale out ECS service** if resource constrained
3. **Restart unhealthy tasks** if target health issues

### Short-term (< 30 minutes)

1. **Deploy hotfix** if application bug identified
2. **Rollback deployment** if recent deployment caused issues
3. **Adjust autoscaling** if capacity planning issue

### Long-term

1. **Implement circuit breakers** for external dependencies
2. **Add connection pooling** for database
3. **Improve monitoring** for early detection
4. **Conduct post-incident review**

## Verification Steps

### 1. Confirm Error Rate Reduction

```bash
# Check current error rate
aws cloudwatch get-metric-statistics \
  --namespace AWS/ApplicationELB \
  --metric-name HTTPCode_Target_5XX_Count \
  --dimensions Name=LoadBalancer,Value=<ALB_FULL_NAME> \
  --start-time $(date -d '10 minutes ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 300 \
  --statistics Sum
```

### 2. Test Application Endpoints

```bash
# Test main endpoints
curl -f https://<ALB_DNS_NAME>/
curl -f https://<ALB_DNS_NAME>/healthz
curl -f https://<ALB_DNS_NAME>/db
```

### 3. Monitor for 15 minutes

- Watch CloudWatch dashboard for sustained improvement
- Ensure no new alarms trigger
- Verify target health remains stable

## Escalation

**Escalate if:**

- Error rate doesn't improve within 15 minutes
- Multiple services affected
- Database or infrastructure issues identified
- Customer impact is severe

**Escalation Contacts:**

- On-call Engineer: [Contact Info]
- Platform Team: [Contact Info]
- Database Team: [Contact Info]

## Post-Incident Actions

1. **Document timeline** and root cause
2. **Update runbook** with lessons learned
3. **Schedule post-incident review**
4. **Implement preventive measures**
5. **Update monitoring/alerting** if gaps identified

## Useful Commands Reference

```bash
# Get ALB DNS name
aws elbv2 describe-load-balancers --names golden-path-alb-{env} --query 'LoadBalancers[0].DNSName'

# Get ECS service status
aws ecs describe-services --cluster golden-path-cluster-{env} --services golden-path-service-{env} --query 'services[0].{Status:status,Running:runningCount,Desired:desiredCount}'

# Force new deployment
aws ecs update-service --cluster golden-path-cluster-{env} --service golden-path-service-{env} --force-new-deployment

# Check recent CloudTrail events
aws logs filter-log-events --log-group-name CloudTrail/ECSEvents --start-time $(date -d '1 hour ago' +%s)000
```
