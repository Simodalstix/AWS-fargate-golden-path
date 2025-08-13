# Game Day Exercise: Unhealthy Targets Scenario

## Overview

This game day exercise simulates a scenario where ALB targets become unhealthy, triggering 5xx errors and alarms. Participants will practice incident response procedures and learn to use the break/fix lab functionality.

## Learning Objectives

- Practice incident detection and response procedures
- Use CloudWatch dashboards and alarms effectively
- Execute runbook procedures under time pressure
- Understand the impact of unhealthy targets on user experience
- Practice rollback procedures using CodeDeploy

## Prerequisites

- Golden Path infrastructure deployed and healthy
- Access to AWS Console and CLI
- Runbooks available and reviewed
- Incident response team assembled

## Scenario Setup

### Initial State

- Application is running normally
- All targets are healthy
- No active alarms
- Normal traffic patterns

### Failure Injection

The exercise facilitator will inject the failure by setting the failure mode parameter.

**Facilitator Commands:**

```bash
# Set failure mode to return 500 errors
aws ssm put-parameter \
  --name "/golden/failure_mode" \
  --value "return_500" \
  --type String \
  --overwrite

# Verify parameter is set
aws ssm get-parameter --name "/golden/failure_mode"
```

## Exercise Timeline

### T+0: Failure Injection

**Facilitator Action:** Execute failure injection commands above

**Expected Impact:**

- Application starts returning 500 errors
- Health checks begin failing
- ALB marks targets as unhealthy

### T+2-5 minutes: Alarm Triggers

**Expected Events:**

- CloudWatch alarm `golden-path-alb-5xx-{env}` triggers
- SNS notifications sent (if configured)
- ALB unhealthy targets alarm may trigger

**Participant Actions:**

1. Acknowledge alarm notifications
2. Begin incident response procedures
3. Access CloudWatch dashboard

### T+5-15 minutes: Investigation Phase

**Participant Tasks:**

#### 1. Initial Assessment (Target: 5 minutes)

```bash
# Check ALB target health
aws elbv2 describe-target-health --target-group-arn <TARGET_GROUP_ARN>

# Check ECS service status
aws ecs describe-services \
  --cluster golden-path-cluster-{env} \
  --services golden-path-service-{env}
```

**Expected Findings:**

- Targets showing as unhealthy
- ECS tasks may be running but failing health checks
- 5xx error rate elevated

#### 2. Log Analysis (Target: 5 minutes)

```bash
# Check recent application logs
aws logs start-query \
  --log-group-name "/ecs/golden-path-app-{env}" \
  --start-time $(date -d '10 minutes ago' +%s) \
  --end-time $(date +%s) \
  --query-string 'fields @timestamp, requestId, path, status, errorType | filter status >= 500 | sort @timestamp desc | limit 20'
```

**Expected Findings:**

- High volume of 500 errors
- Errors affecting all endpoints including `/healthz`
- Error type indicating server errors

#### 3. Root Cause Investigation (Target: 5 minutes)

```bash
# Check failure mode parameter
aws ssm get-parameter --name "/golden/failure_mode"
```

**Expected Finding:**

- Parameter value is `return_500`
- This indicates the break/fix lab failure mode is active

### T+15-20 minutes: Resolution Phase

**Participant Tasks:**

#### 1. Immediate Fix

```bash
# Reset failure mode to normal
aws ssm put-parameter \
  --name "/golden/failure_mode" \
  --value "none" \
  --type String \
  --overwrite
```

#### 2. Verification

```bash
# Test application endpoints
curl -f https://<ALB_DNS_NAME>/
curl -f https://<ALB_DNS_NAME>/healthz

# Monitor target health
aws elbv2 describe-target-health --target-group-arn <TARGET_GROUP_ARN>
```

### T+20-25 minutes: Recovery Verification

**Expected Recovery:**

- Application returns 200 responses
- Health checks pass
- Targets become healthy
- Alarms clear

## Alternative Resolution: CodeDeploy Rollback

If participants choose to use CodeDeploy rollback instead of fixing the parameter:

```bash
# List recent deployments
aws deploy list-deployments \
  --application-name golden-path-app-{env} \
  --max-items 5

# Create rollback deployment (if previous version available)
aws deploy create-deployment \
  --application-name golden-path-app-{env} \
  --deployment-group-name golden-path-dg-{env} \
  --revision revisionType=S3,s3Location={bucket=<BUCKET>,key=<PREVIOUS_VERSION>,bundleType=zip}
```

## Evaluation Criteria

### Time to Detection (Target: < 5 minutes)

- [ ] Alarm acknowledged within 2 minutes
- [ ] Dashboard accessed within 3 minutes
- [ ] Initial assessment started within 5 minutes

### Investigation Effectiveness (Target: < 15 minutes)

- [ ] Target health checked
- [ ] Log analysis performed
- [ ] Root cause identified (failure mode parameter)
- [ ] Appropriate runbook followed

### Resolution Speed (Target: < 20 minutes)

- [ ] Correct fix applied (parameter reset)
- [ ] Application recovery verified
- [ ] Alarms cleared

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

### Variation 1: Partial Failure

Set failure mode to affect only specific endpoints:

```bash
# This would require application code modification
# to support partial failure modes
```

### Variation 2: Gradual Failure

Introduce failure gradually by:

1. Starting with intermittent errors
2. Increasing error rate over time
3. Eventually reaching 100% failure rate

### Variation 3: During High Load

Combine with load testing to simulate failure under stress:

```bash
# Start load test first
hey -z 10m -c 10 https://<ALB_DNS_NAME>/

# Then inject failure
aws ssm put-parameter --name "/golden/failure_mode" --value "return_500" --type String --overwrite
```

## Cleanup

### Reset Environment

```bash
# Ensure failure mode is reset
aws ssm put-parameter \
  --name "/golden/failure_mode" \
  --value "none" \
  --type String \
  --overwrite

# Verify application is healthy
curl https://<ALB_DNS_NAME>/healthz

# Check all alarms are cleared
aws cloudwatch describe-alarms \
  --alarm-names golden-path-alb-5xx-{env} golden-path-alb-unhealthy-targets-{env} \
  --query 'MetricAlarms[*].{Name:AlarmName,State:StateValue}'
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
2. Update monitoring/alerting
3. Enhance automation
4. Plan next game day exercise

### Long-term (1-3 months)

1. Measure improvement in real incidents
2. Expand game day scenarios
3. Cross-train additional team members
4. Integrate with CI/CD pipeline testing

## Resources

### Documentation

- [ALB 5xx Spike Runbook](./runbooks/alb-5xx-spike.md)
- [Slow Response Times Runbook](./runbooks/slow-response-times.md)
- [CloudWatch Dashboard](https://console.aws.amazon.com/cloudwatch/home#dashboards:name=GoldenPath-{env})

### Tools

- AWS CLI
- CloudWatch Console
- X-Ray Console
- ECS Console
- Application Load Balancer Console

### Contacts

- On-call Engineer: [Contact Info]
- Platform Team: [Contact Info]
- Exercise Facilitator: [Contact Info]
