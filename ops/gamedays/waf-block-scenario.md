# Game Day Exercise: WAF Block Scenario

## Overview

This game day exercise simulates a scenario where WAF rules begin blocking legitimate traffic due to false positives, causing user access issues. Participants will practice incident response procedures for WAF configuration issues.

## Learning Objectives

- Practice detecting and responding to WAF blocking issues
- Use CloudWatch dashboards and WAF metrics effectively
- Execute WAF false positive runbook procedures
- Understand the impact of WAF blocking on user experience
- Practice WAF rule tuning and exception management

## Prerequisites

- Golden Path infrastructure deployed and healthy
- Access to AWS Console and CLI
- Runbooks available and reviewed
- Incident response team assembled

## Scenario Setup

### Initial State

- Application is running normally
- WAF rules in COUNT mode (monitoring only)
- No active alarms
- Normal traffic patterns

### Failure Injection

The exercise facilitator will change a WAF rule from COUNT to BLOCK mode to simulate false positive blocking.

**Facilitator Commands:**

```bash
# Update WAF Web ACL to set rate limit rule to BLOCK mode
# This requires updating the WAF rule configuration
# The rate limit rule is initially in COUNT mode for tuning
# Changing it to BLOCK will cause legitimate traffic to be blocked

# Example CloudFormation/CDK change to move rate limit rule to BLOCK mode
# This would be done through infrastructure changes rather than CLI for production
```

## Exercise Timeline

### T+0: Failure Injection

**Facilitator Action:** Update WAF rule configuration to change rate limit rule from COUNT to BLOCK mode

**Expected Impact:**

- Legitimate user requests begin being blocked by WAF
- Users report access denied or 403 errors
- WAF blocked requests metric increases
- Business impact from blocked legitimate traffic

### T+2-5 minutes: Alarm Triggers

**Expected Events:**

- CloudWatch alarm `golden-path-waf-blocked-{env}` triggers
- Users report access issues
- WAF metrics show increased blocked requests

**Participant Actions:**

1. Acknowledge alarm notifications
2. Begin incident response procedures
3. Access CloudWatch dashboard and WAF console

### T+5-15 minutes: Investigation Phase

**Participant Tasks:**

#### 1. Initial Assessment (Target: 5 minutes)

```bash
# Check WAF blocked requests metric
aws cloudwatch get-metric-statistics \
  --namespace AWS/WAFV2 \
  --metric-name BlockedRequests \
  --dimensions Name=WebACL,Value=golden-path-waf-{env} Name=Region,Value=us-east-1 Name=Rule,Value=ALL \
  --start-time $(date -d '10 minutes ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 300 \
  --statistics Sum

# Check application logs for blocked requests
aws logs start-query \
  --log-group-name "/ecs/golden-path-app-{env}" \
  --start-time $(date -d '10 minutes ago' +%s) \
  --end-time $(date +%s) \
  --query-string 'fields @timestamp, requestId, path, status, userAgent | filter status = 403 | sort @timestamp desc | limit 20'
```

**Expected Findings:**

- Increased blocked requests in WAF metrics
- 403 errors in application logs
- Users reporting access denied

#### 2. Root Cause Investigation (Target: 5 minutes)

```bash
# Get WAF sampled requests to analyze blocked traffic
aws wafv2 get-sampled-requests \
  --web-acl-arn arn:aws:wafv2:region:account:regional/webacl/golden-path-waf-{env}/id \
  --rule-metric-name ALL \
  --scope REGIONAL \
  --time-window StartTime=$(date -d '10 minutes ago' --iso-8601),EndTime=$(date --iso-8601) \
  --max-items 100

# Check which specific rule is blocking requests
aws wafv2 get-sampled-requests \
  --web-acl-arn arn:aws:wafv2:region:account:regional/webacl/golden-path-waf-{env}/id \
  --rule-metric-name RateLimitRule \
  --scope REGIONAL \
  --time-window StartTime=$(date -d '10 minutes ago' --iso-8601),EndTime=$(date --iso-8601) \
  --max-items 100

# Analyze user agents and IP addresses of blocked requests
# This helps determine if legitimate traffic is being blocked
```

**Expected Finding:**

- Rate limit rule blocking legitimate traffic
- No malicious patterns in blocked requests
- Business users affected by blocking

### T+15-20 minutes: Resolution Phase

**Participant Tasks:**

#### 1. Immediate Fix - Move Rule Back to Count Mode

```bash
# Update WAF Web ACL to set rate limit rule back to COUNT mode
# This requires updating the WAF rule configuration
# In a real scenario, this would be done through infrastructure as code
# For this exercise, we'll simulate the fix

echo "Updating WAF rule configuration to move rate limit rule from BLOCK to COUNT mode"
echo "This would typically be done through CloudFormation/CDK changes"

# In practice, you would:
# 1. Update the CDK stack to change the rule action
# 2. Deploy the changes with 'cdk deploy'
# 3. Or use AWS CLI to update the Web ACL directly
```

#### 2. Alternative Fix - Add IP-Based Exception

```bash
# Create IP set for trusted IPs (if needed)
aws wafv2 create-ip-set \
  --name "TrustedIPs-{env}" \
  --scope REGIONAL \
  --ip-address-version IPV4 \
  --addresses "203.0.113.0/24" "198.51.100.0/24"

# Update Web ACL to allow these IPs
# This would be part of the WAF rule configuration
```

#### 3. Verification

```bash
# Monitor WAF blocked requests returning to normal
aws cloudwatch get-metric-statistics \
  --namespace AWS/WAFV2 \
  --metric-name BlockedRequests \
  --dimensions Name=WebACL,Value=golden-path-waf-{env} Name=Region,Value=us-east-1 Name=Rule,Value=ALL \
  --start-time $(date -d '5 minutes ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 300 \
  --statistics Sum

# Test application access
curl -f https://<ALB_DNS_NAME>/

# Check application logs for 403 errors
aws logs filter-log-events \
  --log-group-name "/ecs/golden-path-app-{env}" \
  --start-time $(date +%s)000 \
  --filter-pattern "403"
```

### T+20-25 minutes: Recovery Verification

**Expected Recovery:**

- WAF blocked requests return to normal levels
- No 403 errors in application logs
- Users can access application normally
- No active WAF alarms

## Alternative Resolution: Rule Tuning

If participants want to properly tune the WAF rules instead of just moving back to COUNT mode:

```bash
# This would involve:
# 1. Analyzing the sampled requests to understand the pattern
# 2. Creating rule exceptions for legitimate traffic
# 3. Adjusting rate limits to appropriate levels
# 4. Testing changes in COUNT mode before moving to BLOCK

# Example: Increase rate limit threshold
# This would be done through infrastructure changes

# Example: Add exception for specific user agents or paths
# This would also be done through infrastructure changes
```

## Evaluation Criteria

### Time to Detection (Target: < 5 minutes)

- [ ] WAF blocked requests alarm triggered
- [ ] 403 errors detected in logs
- [ ] Initial assessment started

### Investigation Effectiveness (Target: < 15 minutes)

- [ ] WAF blocking confirmed
- [ ] Root cause identified (rate limit rule)
- [ ] Appropriate runbook followed

### Resolution Speed (Target: < 20 minutes)

- [ ] Correct fix applied (rule configuration change)
- [ ] Application access restored
- [ ] No ongoing blocking issues

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

### Variation 1: Combined with High Traffic

Combine WAF blocking with high legitimate traffic:

```bash
# Generate legitimate high traffic
hey -z 10m -c 50 "https://<ALB_DNS_NAME>/" &

# Then trigger WAF blocking
# This simulates real-world scenario where legitimate high traffic triggers rate limits
```

### Variation 2: Multiple Rule Blocking

Have multiple WAF rules blocking legitimate traffic:

```bash
# This would require updating multiple rules to BLOCK mode
# Simulates complex WAF configuration issues
```

### Variation 3: Business-Critical Traffic Affected

Focus on blocking business-critical endpoints:

```bash
# Generate load specifically on business-critical endpoints
hey -z 10m -c 20 "https://<ALB_DNS_NAME>/api/critical-business-function"
```

## Cleanup

### Reset Environment

```bash
# Ensure WAF rules are in proper configuration
# In a real scenario, this would be done through infrastructure as code

# Verify application is accessible
curl -f https://<ALB_DNS_NAME>/

# Check WAF metrics for normal blocking levels
aws cloudwatch get-metric-statistics \
  --namespace AWS/WAFV2 \
  --metric-name BlockedRequests \
  --dimensions Name=WebACL,Value=golden-path-waf-{env} Name=Region,Value=us-east-1 Name=Rule,Value=ALL \
  --start-time $(date -d '5 minutes ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 300 \
  --statistics Sum

# Check application logs for errors
aws logs filter-log-events \
  --log-group-name "/ecs/golden-path-app-{env}" \
  --start-time $(date +%s)000 \
  --filter-pattern "ERROR OR 403"
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
2. Update monitoring/alerting for WAF blocking
3. Enhance WAF rule tuning processes
4. Plan next game day exercise

### Long-term (1-3 months)

1. Measure improvement in real incidents
2. Expand game day scenarios
3. Cross-train additional team members
4. Integrate with CI/CD pipeline testing

## Resources

### Documentation

- [WAF False Positive Runbook](./runbooks/waf-false-positive.md)
- [CloudWatch Dashboard](https://console.aws.amazon.com/cloudwatch/home#dashboards:name=GoldenPath-{env})
- [WAF Console](https://console.aws.amazon.com/wafv2)

### Tools

- AWS CLI
- CloudWatch Console
- WAF Console
- Application Load Balancer Console

### Contacts

- On-call Engineer: [Contact Info]
- Security Team: [Contact Info]
- Platform Team: [Contact Info]
- Exercise Facilitator: [Contact Info]
