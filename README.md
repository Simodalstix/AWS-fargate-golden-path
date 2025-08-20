# ECS Fargate Golden Path + Break/Fix Lab

## In a Nutshell

A production-ready ECS Fargate web service with comprehensive observability, blue/green deployments, and built-in chaos engineering scenarios for incident response training. Deploy once, break things safely, learn how to fix them.

**What you get:** ALB + ECS Fargate + Aurora + WAF + CloudWatch dashboards/alarms + X-Ray tracing + CodeDeploy blue/green + break/fix scenarios via SSM parameters.

## Quick Start

```bash
# Deploy infrastructure
python -m venv .venv && source .venv/bin/activate
pip install -r infra/requirements.txt
cd infra && cdk bootstrap && cdk deploy --all

# Optional: Subscribe to alarms
cdk deploy --parameters alarm_email=your-email@example.com
```

## Architecture

```
Internet → WAF → ALB → ECS Fargate (2 AZs) → Aurora PostgreSQL
                 ↓
            CloudWatch + X-Ray + SNS Alarms
```

**Core Components:**
- **VPC**: 2 AZs, public/private subnets, 1 NAT Gateway
- **ECS Fargate**: 2 tasks, health checks, X-Ray sidecars, ECS Exec enabled
- **Aurora Serverless v2**: Writer/reader, Secrets Manager, private subnets
- **ALB**: Blue/green target groups, WAF protection, S3 access logs
- **Observability**: CloudWatch dashboards, 10+ alarms, structured JSON logs
- **Deployment**: CodeDeploy blue/green with auto-rollback on alarms

## Break/Fix Lab

Trigger failures via SSM Parameter `/golden/failure_mode`:

| Mode | Effect | Learning |
|------|--------|----------|
| `return_500` | Health checks fail → ALB 5xx alarms | Unhealthy targets, rollback procedures |
| `connection_leak` | DB connections exhaust → RDS alarms | Connection pooling, task restarts |
| `none` | Normal operation | Reset to healthy state |

**Game Day Scenarios:**
1. **Unhealthy Targets** - Set failure mode, observe alarms, execute rollback
2. **Secret Drift** - Rotate DB secret, hit `/db` until errors, redeploy service
3. **CPU Burn** - Load test `/work` endpoint, watch autoscaling
4. **WAF Blocks** - Tune rate rules, observe block metrics

## Application Endpoints

- `/` - App info and health status
- `/healthz` - Health check (ALB target)
- `/work?ms=250` - CPU burn simulation
- `/db` - Database query test

## Project Structure

```
├── app/                    # FastAPI application + Dockerfile
├── infra/                  # CDK infrastructure code
│   ├── stacks/            # Network, compute, data, observability
│   └── custom_constructs/ # Reusable components
└── ops/                   # Runbooks and game day scenarios
    ├── runbooks/          # Incident response procedures
    └── gamedays/          # Break/fix exercise guides
```

## Key Features

**Production Ready:**
- Multi-AZ high availability
- Blue/green deployments with auto-rollback
- Comprehensive monitoring and alerting
- Security best practices (WAF, private subnets, KMS encryption)
- Cost optimized (1 NAT, Aurora Serverless v2)

**Observability:**
- CloudWatch dashboards for ALB, ECS, RDS metrics
- X-Ray distributed tracing with service maps
- Structured JSON application logs
- 10+ CloudWatch alarms with SNS notifications

**Break/Fix Learning:**
- Safe failure injection via SSM parameters
- Real-world incident scenarios
- Guided runbooks for resolution
- MTTR measurement and improvement

## Cost Considerations

- **Minimal**: ~$50-100/month for learning/demo
- **Optimizations**: Single NAT Gateway, Aurora Serverless v2 min ACUs
- **Scaling**: Configurable task sizes, autoscaling policies

## Next Steps

1. **Deploy** - Follow Quick Start above
2. **Explore** - Check CloudWatch dashboards, X-Ray traces
3. **Break** - Try failure modes in break/fix lab
4. **Learn** - Follow runbooks to resolve incidents
5. **Extend** - Add Fault Injection Simulator, RDS Proxy, CDK Pipeline

## Advanced Enhancements

**Fault Injection Simulator Integration** (~4-6 hours work):
- Chaos experiments for network latency, CPU stress, memory pressure
- Automated failure injection with rollback
- Integration with existing CloudWatch alarms
- Would add `fis_stack.py` and experiment templates

Ready to break things safely and learn incident response? Deploy and start your first game day! 🚀