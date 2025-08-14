# Game Day Exercise: Secret Drift Scenario

## Overview

This game day exercise simulates a scenario where database credentials are rotated but the application continues to use outdated credentials, causing authentication failures. Participants will practice incident response procedures for secret management issues.

## Learning Objectives

- Practice detecting and responding to credential rotation issues
- Use CloudWatch dashboards and alarms effectively
- Execute database authentication failure runbook procedures
- Understand the impact of credential drift on application availability
- Practice service redeployment procedures

## Prerequisites

- Golden Path infrastructure deployed and healthy
- Access to AWS Console and CLI
- Runbooks available and reviewed
- Incident response team assembled

## Scenario Setup

### Initial State

- Application is running normally
- Database connections are healthy
- No active alarms
- Normal traffic patterns

### Failure Injection

The exercise facilitator will manually rotate the database secret while the application is running.

**Facilitator Commands:**

```bash
# Rotate the database secret
aws secretsmanager rotate-secret \
  --secret-id golden-path/db-credentials/{env}

# Verify rotation is in progress
aws secretsmanager describe-secret \
  --secret-id golden-path/db-credentials/{env} \
  --query 'RotationState'
```

## Exercise Timeline

### T+0: Failure Injection

**Facilitator Action:** Execute secret rotation commands above

**Expected Impact:**

- Application continues using old credentials
- Database authentication failures begin
- `/db` endpoint starts returning 500 errors

### T+2-5 minutes: Alarm Triggers

**Expected Events:**

- Application logs show database authentication errors
- Users may report database connection issues
- No immediate CloudWatch alarms (depends on configuration)

**Participant Actions:**

1. Monitor application logs for errors
2. Begin investigation when errors are detected
3. Access CloudWatch dashboard

### T+5-15 minutes: Investigation Phase

**Participant Tasks:**

#### 1. Initial Assessment (Target: 5 minutes)

```bash
# Check application logs for database errors
aws logs start-query \
  --log-group-name "/ecs/golden-path-app-{env}" \
  --start-time $(date -d '10 minutes ago' +%s) \
  --end-time $(date +%s) \
  --query-string 'fields @timestamp, requestId, path, status, errorType | filter path = "/db" and ispresent(errorType) | sort @timestamp desc | limit 20'

# Test database endpoint
curl -s -o /dev/null -w "%{http_code}" https://<ALB_DNS_NAME>/db
# Should return 500
```

**Expected Findings:**

- Database authentication errors in logs
- 500 errors on `/db` endpoint
- Other endpoints may still work

#### 2. Root Cause Investigation (Target: 5 minutes)

```bash
# Check if secret was recently rotated
aws secretsmanager describe-secret \
  --secret-id golden-path/db-credentials/{env} \
  --query 'LastChangedDate'

# Check current secret value
aws secretsmanager get-secret-value \
  --secret-id golden-path/db-credentials/{env} \
  --query 'SecretString' \
  | jq -r

# Check ECS task definition environment variables
aws ecs describe-task-definition \
  --task-definition $(aws ecs describe-services \
    --cluster golden-path-cluster-{env} \
    --services golden-path-service-{env} \
    --query 'services[0].taskDefinition' \
    --output text) \
  --query 'taskDefinition.containerDefinitions[0].Environment'
```

**Expected Finding:**

- Secret was recently rotated
- Application is using outdated credentials (environment variable approach)

### T+15-20 minutes: Resolution Phase

**Participant Tasks:**

#### 1. Immediate Fix - Redeploy Service

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

#### 2. Verification

```bash
# Test database endpoint
curl -f https://<ALB_DNS_NAME>/db

# Monitor application logs for database errors
aws logs filter-log-events \
  --log-group-name "/ecs/golden-path-app-{env}" \
  --start-time $(date +%s)000 \
  --filter-pattern "database AND error"
```

### T+20-25 minutes: Recovery Verification

**Expected Recovery:**

- Application returns 200 responses on `/db` endpoint
- No database authentication errors in logs
- Service health restored

## Alternative Resolution: Manual Secret Update

If participants choose to manually update the secret instead of redeploying:

```bash
# Update secret with known good credentials
aws secretsmanager put-secret-value \
  --secret-id golden-path/db-credentials/{env} \
  --secret-string '{"username":"dbadmin","password":"CURRENT_PASSWORD","engine":"postgres","host":"DB_ENDPOINT","port":5432,"dbname":"goldenpath","dbInstanceIdentifier":"golden-path-aurora-{env}"}'

# Then redeploy service
aws ecs update-service \
  --cluster golden-path-cluster-{env} \
  --service golden-path-service-{env} \
  --force-new-deployment
```

## Evaluation Criteria

### Time to Detection (Target: < 5 minutes)

- [ ] Database errors detected in logs
- [ ] `/db` endpoint failure identified
- [ ] Initial assessment started

### Investigation Effectiveness (Target: < 15 minutes)

- [ ] Database errors confirmed
- [ ] Secret rotation identified as potential cause
- [ ] Appropriate runbook followed

### Resolution Speed (Target: < 20 minutes)

- [ ] Correct fix applied (service redeployment)
- [ ] Application recovery verified
- [ ] No ongoing database errors

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

### Variation 1: Combined with High Load

Combine with load testing to simulate failure under stress:

```bash
# Start load test first
hey -z 10m -c 10 https://<ALB_DNS_NAME>/db

# Then rotate secret
aws secretsmanager rotate-secret --secret-id golden-path/db-credentials/{env}
```

### Variation 2: Multiple Secret Rotations

Rotate secret multiple times to test detection of ongoing issues:

```bash
# Rotate secret
aws secretsmanager rotate-secret --secret-id golden-path/db-credentials/{env}

# Wait 2 minutes
sleep 120

# Rotate again
aws secretsmanager rotate-secret --secret-id golden-path/db-credentials/{env}
```

### Variation 3: Partial Service Impact

Configure some tasks with old credentials and some with new:
This would require more complex setup but could simulate partial failures.

## Cleanup

### Reset Environment

```bash
# Ensure service is healthy
aws ecs describe-services \
  --cluster golden-path-cluster-{env} \
  --services golden-path-service-{env} \
  --query 'services[0].{Status:status,Running:runningCount,Desired:desiredCount}'

# Test application endpoints
curl -f https://<ALB_DNS_NAME>/
curl -f https://<ALB_DNS_NAME>/db

# Check application logs for errors
aws logs filter-log-events \
  --log-group-name "/ecs/golden-path-app-{env}" \
  --start-time $(date +%s)000 \
  --filter-pattern "ERROR OR database"
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
2. Update monitoring/alerting for database auth failures
3. Enhance automation for credential rotation
4. Plan next game day exercise

### Long-term (1-3 months)

1. Measure improvement in real incidents
2. Expand game day scenarios
3. Cross-train additional team members
4. Integrate with CI/CD pipeline testing

## Resources

### Documentation

- [DB Authentication Failures Runbook](./runbooks/db-auth-failures.md)
- [CloudWatch Dashboard](https://console.aws.amazon.com/cloudwatch/home#dashboards:name=GoldenPath-{env})
- [Secrets Manager Console](https://console.aws.amazon.com/secretsmanager)

### Tools

- AWS CLI
- CloudWatch Console
- Secrets Manager Console
- ECS Console

### Contacts

- On-call Engineer: [Contact Info]
- Database Team: [Contact Info]
- Security Team: [Contact Info]
- Exercise Facilitator: [Contact Info]
