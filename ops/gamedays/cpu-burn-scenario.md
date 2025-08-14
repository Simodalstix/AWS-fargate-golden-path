# Game Day Exercise: CPU Burn Scenario

## Overview

This game day exercise simulates a scenario where the application experiences high CPU usage due to CPU-intensive workloads, triggering autoscaling and affecting performance. Participants will practice incident response procedures for performance degradation issues.

## Learning Objectives

- Practice detecting and responding to CPU performance issues
- Use CloudWatch dashboards and alarms effectively
- Execute autoscaling and performance runbook procedures
- Understand the impact of CPU-intensive workloads on application performance
- Practice load testing and performance analysis

## Prerequisites

- Golden Path infrastructure deployed and healthy
- Access to AWS Console and CLI
- Runbooks available and reviewed
- Incident response team assembled
- Load testing tool (e.g., hey, ab, or similar) available

## Scenario Setup

### Initial State

- Application is running normally
- CPU utilization is low (typically < 20%)
- No active alarms
- Normal traffic patterns

### Failure Injection

Participants will generate CPU-intensive load against the application's `/work` endpoint.

**Participant Commands:**

```bash
# Generate CPU-intensive load
hey -z 10m -c 20 "https://<ALB_DNS_NAME>/work?ms=500"

# Or use ab (Apache Bench)
ab -t 600 -c 20 "https://<ALB_DNS_NAME>/work?ms=500"
```

## Exercise Timeline

### T+0: Failure Injection

**Participant Action:** Execute load testing commands above

**Expected Impact:**

- CPU utilization begins to rise
- Response times increase
- Autoscaling may trigger
- Potential resource exhaustion

### T+2-5 minutes: Alarm Triggers

**Expected Events:**

- CloudWatch alarm `golden-path-ecs-cpu-{env}` triggers
- ECS CPU utilization metrics show high usage
- Response times increase in ALB metrics
- Autoscaling activities may begin

**Participant Actions:**

1. Acknowledge alarm notifications
2. Begin incident response procedures
3. Access CloudWatch dashboard

### T+5-15 minutes: Investigation Phase

**Participant Tasks:**

#### 1. Initial Assessment (Target: 5 minutes)

```bash
# Check ECS CPU utilization
aws cloudwatch get-metric-statistics \
  --namespace AWS/ECS \
  --metric-name CPUUtilization \
  --dimensions Name=ServiceName,Value=golden-path-service-{env} Name=ClusterName,Value=golden-path-cluster-{env} \
  --start-time $(date -d '10 minutes ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 300 \
  --statistics Average,Maximum

# Check ALB response times
aws cloudwatch get-metric-statistics \
  --namespace AWS/ApplicationELB \
  --metric-name TargetResponseTime \
  --dimensions Name=LoadBalancer,Value=<ALB_FULL_NAME> \
  --start-time $(date -d '10 minutes ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 300 \
  --statistics Average,p95
```

**Expected Findings:**

- High CPU utilization (> 80%)
- Increased response times
- Autoscaling activities in progress

#### 2. Root Cause Investigation (Target: 5 minutes)

```bash
# Check application logs for /work endpoint usage
aws logs start-query \
  --log-group-name "/ecs/golden-path-app-{env}" \
  --start-time $(date -d '10 minutes ago' +%s) \
  --end-time $(date +%s) \
  --query-string 'fields @timestamp, path, latencyMs | filter path = "/work" | stats count(), avg(latencyMs) by bin(1m) | sort @timestamp'

# Check autoscaling activities
aws application-autoscaling describe-scaling-activities \
  --service-namespace ecs \
  --resource-id service/golden-path-cluster-{env}/golden-path-service-{env}

# Check current task count
aws ecs describe-services \
  --cluster golden-path-cluster-{env} \
  --services golden-path-service-{env} \
  --query 'services[0].{Running:runningCount,Desired:desiredCount,Pending:pendingCount}'
```

**Expected Finding:**

- High volume of requests to `/work` endpoint
- CPU-intensive work causing resource exhaustion
- Autoscaling triggered to handle load

### T+15-20 minutes: Resolution Phase

**Participant Tasks:**

#### 1. Immediate Actions

```bash
# Stop load testing (if still running)
# Control+C in the terminal running hey/ab

# Check if autoscaling has stabilized
aws application-autoscaling describe-scaling-activities \
  --service-namespace ecs \
  --resource-id service/golden-path-cluster-{env}/golden-path-service-{env} \
  --max-items 5
```

#### 2. Verification

```bash
# Monitor CPU utilization returning to normal
aws cloudwatch get-metric-statistics \
  --namespace AWS/ECS \
  --metric-name CPUUtilization \
  --dimensions Name=ServiceName,Value=golden-path-service-{env} Name=ClusterName,Value=golden-path-cluster-{env} \
  --start-time $(date -d '5 minutes ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 300 \
  --statistics Average

# Test application endpoints
curl -f https://<ALB_DNS_NAME>/
curl -f https://<ALB_DNS_NAME>/healthz

# Check response times
curl -w "Total time: %{time_total}s\n" -o /dev/null -s https://<ALB_DNS_NAME>/
```

### T+20-25 minutes: Recovery Verification

**Expected Recovery:**

- CPU utilization returns to normal levels (< 30%)
- Response times return to baseline
- Autoscaling stabilizes
- No active alarms

## Alternative Resolution: Rate Limiting

If participants want to implement rate limiting to prevent future occurrences:

```bash
# This would require application-level changes or infrastructure additions
# Example: Add rate limiting middleware to FastAPI application

# Or implement at ALB level with WAF rules
# This would be part of a longer-term solution
```

## Evaluation Criteria

### Time to Detection (Target: < 5 minutes)

- [ ] CPU utilization alarm triggered
- [ ] Response time degradation identified
- [ ] Initial assessment started

### Investigation Effectiveness (Target: < 15 minutes)

- [ ] High CPU utilization confirmed
- [ ] Root cause identified (/work endpoint load)
- [ ] Appropriate runbook followed

### Resolution Speed (Target: < 20 minutes)

- [ ] Load testing stopped
- [ ] CPU utilization normalized
- [ ] Response times returned to baseline

### Communication

- [ ] Incident declared appropriately
- [ ] Status updates provided
- [ ] Stakeholders notified

## Debrief Questions

### What Went Well?

- Which monitoring tools were most helpful?
- What runbook steps were most effective?
- How was team coordination?

### What Could Be Improved?

- Were there any delays in detection or response?
- Which tools or procedures need improvement?
- What additional monitoring would be helpful?

### Lessons Learned

- How would you prevent this type of issue?
- What automation could speed up resolution?
- What additional training is needed?

## Variations

### Variation 1: Combined with Other Failures

Combine CPU burn with another failure mode:

```bash
# Start CPU burn
hey -z 10m -c 20 "https://<ALB_DNS_NAME>/work?ms=500" &

# Set failure mode to return 500 errors
aws ssm put-parameter \
  --name "/golden/failure_mode" \
  --value "return_500" \
  --type String \
  --overwrite
```

### Variation 2: Gradual Load Increase

Start with low load and gradually increase:

```bash
# Start with low load
hey -z 5m -c 5 "https://<ALB_DNS_NAME>/work?ms=100"

# After 2 minutes, increase load
hey -z 5m -c 15 "https://<ALB_DNS_NAME>/work?ms=300"

# After another 2 minutes, increase further
hey -z 5m -c 25 "https://<ALB_DNS_NAME>/work?ms=500"
```

### Variation 3: Multiple Endpoints

Generate load on multiple endpoints simultaneously:

```bash
# Generate load on /work endpoint
hey -z 10m -c 10 "https://<ALB_DNS_NAME>/work?ms=300" &

# Generate load on /db endpoint
hey -z 10m -c 10 "https://<ALB_DNS_NAME>/db" &

# Generate load on root endpoint
hey -z 10m -c 10 "https://<ALB_DNS_NAME}/" &
```

## Cleanup

### Reset Environment

```bash
# Ensure failure mode is reset (if used)
aws ssm put-parameter \
  --name "/golden/failure_mode" \
  --value "none" \
  --type String \
  --overwrite

# Verify application is healthy
curl -f https://<ALB_DNS_NAME>/healthz

# Check all alarms are cleared
aws cloudwatch describe-alarms \
  --alarm-names golden-path-ecs-cpu-{env} \
  --query 'MetricAlarms[*].{Name:AlarmName,State:StateValue}'

# Check CPU utilization is normal
aws cloudwatch get-metric-statistics \
  --namespace AWS/ECS \
  --metric-name CPUUtilization \
  --dimensions Name=ServiceName,Value=golden-path-service-{env} Name=ClusterName,Value=golden-path-cluster-{env} \
  --start-time $(date -d '5 minutes ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 300 \
  --statistics Average
```

### Document Results

- Record actual time to detection
- Note any issues with procedures
- Update runbooks based on findings
- Schedule follow-up improvements

## Success Metrics

### Primary Metrics

- **Mean Time to Detection (MTTD):** < 5 minutes
- **Mean Time to Resolution (MTTR):** < 20 minutes
- **False Positive Rate:** 0%

### Secondary Metrics

- Team coordination effectiveness
- Runbook adherence
- Communication clarity
- Post-incident learning

## Next Steps

### Immediate (Post-Exercise)

1. Conduct debrief session
2. Document lessons learned
3. Update runbooks if needed
4. Schedule follow-up training

### Short-term (1-2 weeks)

1. Implement identified improvements
2. Update monitoring/alerting for CPU performance
3. Enhance autoscaling policies
4. Plan next game day exercise

### Long-term (1-3 months)

1. Measure improvement in real incidents
2. Expand game day scenarios
3. Cross-train additional team members
4.
