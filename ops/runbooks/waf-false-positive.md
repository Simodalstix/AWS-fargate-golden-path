# WAF False Positive Blocks Runbook

## Overview

This runbook provides step-by-step instructions for investigating and resolving WAF false positive blocking issues in the Golden Path application.

## Symptoms

- Legitimate user requests being blocked by WAF
- CloudWatch alarm: `golden-path-waf-blocked-{env}` triggered
- Users reporting access denied or 403 errors
- WAF metrics showing unexpected blocked requests
- Business impact from blocked legitimate traffic

## Initial Assessment (5 minutes)

### 1. Check WAF Metrics

Navigate to: CloudWatch → Dashboards → `GoldenPath-{env}`

**Key Metrics to Review:**

- WAF Allowed vs Blocked Requests
- Rate of blocked requests over time
- Specific rules triggering blocks

### 2. Check WAF Sampled Requests

```bash
# Get recent sampled requests (last 10 minutes)
aws wafv2 get-sampled-requests \
  --web-acl-arn arn:aws:wafv2:region:account:regional/webacl/golden-path-waf-{env}/id \
  --rule-metric-name ALL \
  --scope REGIONAL \
  --time-window StartTime=$(date -d '10 minutes ago' --iso-8601),EndTime=$(date --iso-8601) \
  --max-items 100
```

### 3. Check Application Logs

```bash
# Check recent application logs for blocked requests
aws logs start-query \
  --log-group-name "/ecs/golden-path-app-{env}" \
  --start-time $(date -d '15 minutes ago' +%s) \
  --end-time $(date +%s) \
  --query-string 'fields @timestamp, requestId, path, status, userAgent, remoteAddr | filter status = 403 | sort @timestamp desc | limit 20'
```

## Investigation Steps

### 4. Analyze Blocked Request Patterns

```bash
# Get detailed WAF sampled requests for analysis
aws wafv2 get-sampled-requests \
  --web-acl-arn arn:aws:wafv2:region:account:regional/webacl/golden-path-waf-{env}/id \
  --rule-metric-name ALL \
  --scope REGIONAL \
  --time-window StartTime=$(date -d '30 minutes ago' --iso-8601),EndTime=$(date --iso-8601) \
  --max-items 500 \
  > /tmp/waf-sampled-requests.json

# Analyze patterns in blocked requests
cat /tmp/waf-sampled-requests.json | jq -r '.SampledRequests[] | .Request.Headers[] | select(.Name=="user-agent") | .Value' | sort | uniq -c | sort -nr | head -10
```

### 5. Identify Specific Rules Triggering Blocks

```bash
# Check which WAF rules are blocking requests
aws wafv2 get-sampled-requests \
  --web-acl-arn arn:aws:wafv2:region:account:regional/webacl/golden-path-waf-{env}/id \
  --rule-metric-name AWSManagedRulesCommonRuleSet \
  --scope REGIONAL \
  --time-window StartTime=$(date -d '30 minutes ago' --iso-8601),EndTime=$(date --iso-8601) \
  --max-items 100

# Check other managed rule sets
aws wafv2 get-sampled-requests \
  --web-acl-arn arn:aws:wafv2:region:account:regional/webacl/golden-path-waf-{env}/id \
  --rule-metric-name AWSManagedRulesKnownBadInputsRuleSet \
  --scope REGIONAL \
  --time-window StartTime=$(date -d '30 minutes ago' --iso-8601),EndTime=$(date --iso-8601) \
  --max-items 100
```

### 6. Check Rate-Based Rule Triggers

```bash
# Check rate limit rule blocks
aws wafv2 get-sampled-requests \
  --web-acl-arn arn:aws:wafv2:region:account:regional/webacl/golden-path-waf-{env}/id \
  --rule-metric-name RateLimitRule \
  --scope REGIONAL \
  --time-window StartTime=$(date -d '30 minutes ago' --iso-8601),EndTime=$(date --iso-8601) \
  --max-items 100
```

## Common Root Causes & Solutions

### Cause 1: Legitimate Traffic Matching Security Rules

**Symptoms:** Legitimate user agents, paths, or patterns being blocked by managed rule sets

**Investigation:**

- Analyze sampled requests for legitimate business traffic
- Identify specific rules causing false positives

**Resolution:**

```bash
# Add exception to WAF rule for specific pattern
# This requires creating a rule group with exclusion
aws wafv2 create-rule-group \
  --name "GoldenPath-Exceptions-{env}" \
  --scope REGIONAL \
  --capacity 100 \
  --rules '[
    {
      "Name": "AllowSpecificUserAgent",
      "Priority": 1,
      "Statement": {
        "ByteMatchStatement": {
          "SearchString": "LegitimateBot/1.0",
          "FieldToMatch": {
            "SingleHeader": {
              "Name": "user-agent"
            }
          },
          "TextTransformations": [
            {
              "Priority": 0,
              "Type": "NONE"
            }
          ],
          "PositionalConstraint": "CONTAINS"
        }
      },
      "Action": {
        "Allow": {}
      },
      "VisibilityConfig": {
        "SampledRequestsEnabled": true,
        "CloudWatchMetricsEnabled": true,
        "MetricName": "AllowSpecificUserAgent"
      }
    }
  ]' \
  --visibility-config SampledRequestsEnabled=true,CloudWatchMetricsEnabled=true,MetricName=GoldenPathExceptions
```

### Cause 2: Overly Restrictive Rate Limiting

**Symptoms:** Legitimate high-traffic users or applications being rate-limited

**Investigation:**

- Check if rate limit rule is blocking legitimate traffic
- Identify IP addresses or user patterns affected

**Resolution:**

```bash
# Temporarily increase rate limit threshold
# This requires updating the WAF Web ACL
# Example CloudFormation/CDK change to increase limit from 2000 to 5000

# Or add IP-based exceptions
aws wafv2 update-web-acl \
  --name golden-path-waf-{env} \
  --scope REGIONAL \
  --id <WEB_ACL_ID> \
  --default-action Allow={} \
  --rules '[
    {
      "Name": "RateLimitRule",
      "Priority": 4,
      "Statement": {
        "RateBasedStatement": {
          "Limit": 5000,
          "AggregateKeyType": "IP",
          "ScopeDownStatement": {
            "NotStatement": {
              "Statement": {
                "IPSetReferenceStatement": {
                  "ARN": "arn:aws:wafv2:region:account:regional/ipset/TrustedIPs-{env}/id"
                }
              }
            }
          }
        }
      },
      "Action": {
        "Block": {}
      },
      "VisibilityConfig": {
        "SampledRequestsEnabled": true,
        "CloudWatchMetricsEnabled": true,
        "MetricName": "RateLimitMetric"
      }
    }
  ]' \
  --visibility-config SampledRequestsEnabled=true,CloudWatchMetricsEnabled=true,MetricName=GoldenPathWAF{env} \
  --lock-token <LOCK_TOKEN>
```

### Cause 3: Business Logic Conflicts with Security Rules

**Symptoms:** Application-specific endpoints or payloads being flagged as malicious

**Investigation:**

- Identify specific paths or payloads causing blocks
- Check if application behavior triggers security rules

**Resolution:**

```bash
# Add path-based exclusions
# Example: Exclude specific API endpoints from certain rules
aws wafv2 update-rule-group \
  --name AWSManagedRulesCommonRuleSet \
  --scope REGIONAL \
  --id <RULE_GROUP_ID> \
  --excluded-rules '[
    {
      "Name": "GenericRFI_BODY"
    }
  ]' \
  --lock-token <LOCK_TOKEN>
```

## Immediate Actions (< 10 minutes)

### 1. Move Problematic Rules to Count Mode

```bash
# Update WAF Web ACL to set specific rules to COUNT instead of BLOCK
# This allows traffic while still monitoring
aws wafv2 update-web-acl \
  --name golden-path-waf-{env} \
  --scope REGIONAL \
  --id <WEB_ACL_ID> \
  --rules '[
    {
      "Name": "AWSManagedRulesCommonRuleSet",
      "Priority": 1,
      "OverrideAction": {
        "Count": {}
      },
      "Statement": {
        "ManagedRuleGroupStatement": {
          "VendorName": "AWS",
          "Name": "AWSManagedRulesCommonRuleSet"
        }
      },
      "VisibilityConfig": {
        "SampledRequestsEnabled": true,
        "CloudWatchMetricsEnabled": true,
        "MetricName": "CommonRuleSetMetric"
      }
    }
  ]' \
  --visibility-config SampledRequestsEnabled=true,CloudWatchMetricsEnabled=true,MetricName=GoldenPathWAF{env} \
  --lock-token <LOCK_TOKEN>
```

### 2. Create Temporary IP Allow List

```bash
# Create IP set for trusted IPs
aws wafv2 create-ip-set \
  --name "TrustedIPs-{env}" \
  --scope REGIONAL \
  --ip-address-version IPV4 \
  --addresses "203.0.113.0/24" "198.51.100.0/24"

# Update Web ACL to allow these IPs
aws wafv2 update-web-acl \
  --name golden-path-waf-{env} \
  --scope REGIONAL \
  --id <WEB_ACL_ID> \
  --rules '[
    {
      "Name": "AllowTrustedIPs",
      "Priority": 0,
      "Statement": {
        "IPSetReferenceStatement": {
          "ARN": "arn:aws:wafv2:region:account:regional/ipset/TrustedIPs-{env}/id"
        }
      },
      "Action": {
        "Allow": {}
      },
      "VisibilityConfig": {
        "SampledRequestsEnabled": true,
        "CloudWatchMetricsEnabled": true,
        "MetricName": "AllowTrustedIPs"
      }
    }
  ]' \
  --default-action Block={} \
  --visibility-config SampledRequestsEnabled=true,CloudWatchMetricsEnabled=true,MetricName=GoldenPathWAF{env} \
  --lock-token <LOCK_TOKEN>
```

## Long-term Solutions

### 1. Implement Proper WAF Rule Tuning

- Regularly review sampled requests
- Create custom rules for business-specific exceptions
- Use rule groups for better organization

### 2. Add Business Context to Security Rules

```bash
# Example: Exclude specific headers from inspection
# This would be implemented in the WAF rule configuration
{
  "Name": "ExcludeAuthHeader",
  "Priority": 10,
  "Statement": {
    "NotStatement": {
      "Statement": {
        "ByteMatchStatement": {
          "SearchString": "Authorization",
          "FieldToMatch": {
            "SingleHeader": {
              "Name": "header-name"
            }
          },
          "TextTransformations": [
            {
              "Priority": 0,
              "Type": "LOWERCASE"
            }
          ],
          "PositionalConstraint": "EXACTLY"
        }
      }
    }
  },
  "Action": {
    "Count": {}
  },
  "VisibilityConfig": {
    "SampledRequestsEnabled": true,
    "CloudWatchMetricsEnabled": true,
    "MetricName": "ExcludeAuthHeader"
  }
}
```

### 3. Implement WAF Logging for Analysis

```bash
# Enable WAF logging to S3 or CloudWatch Logs
aws wafv2 put-logging-configuration \
  --logging-configuration '{
    "ResourceArn": "arn:aws:wafv2:region:account:regional/webacl/golden-path-waf-{env}/id",
    "LogDestinationConfigs": [
      "arn:aws:logs:region:account:log-group:aws-waf-logs-golden-path-{env}"
    ]
  }'
```

## Verification Steps

### 1. Confirm Traffic Is No Longer Blocked

```bash
# Monitor WAF blocked requests metric
aws cloudwatch get-metric-statistics \
  --namespace AWS/WAFV2 \
  --metric-name BlockedRequests \
  --dimensions Name=WebACL,Value=golden-path-waf-{env} Name=Region,Value=us-east-1 Name=Rule,Value=ALL \
  --start-time $(date -d '10 minutes ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 300 \
  --statistics Sum

# Test application access
curl -f https://<ALB_DNS_NAME>/
```

### 2. Validate Business Traffic

- Coordinate with business users to confirm access
- Check application logs for successful requests
- Monitor user experience metrics

### 3. Monitor for New Issues

- Watch for new false negatives (malicious traffic not blocked)
- Ensure legitimate traffic flows normally
- Verify performance is not impacted

## Escalation

**Escalate if:**

- Business-critical traffic remains blocked
- Security team identifies actual threats being missed
- Performance issues arise from WAF changes

**Escalation Contacts:**

- Security Team: [Contact Info]
- Application Team: [Contact Info]
- Platform Team: [Contact Info]

## Useful Commands Reference

```bash
# Get WAF Web ACL details
aws wafv2 get-web-acl \
  --name golden-path-waf-{env} \
  --scope REGIONAL \
  --id <WEB_ACL_ID>

# List WAF rule groups
aws wafv2 list-available-managed-rule-groups \
  --scope REGIONAL

# Check WAF logging configuration
aws wafv2 get-logging-configuration \
  --resource-arn arn:aws:wafv2:region:account:regional/webacl/golden-path-waf-{env}/id

# Test WAF rule changes in COUNT mode first
# Then move to BLOCK mode after validation
```
