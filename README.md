# ECS Fargate Golden Path + Break/Fix Lab

## In a Nutshell

A production-ready ECS Fargate web service with comprehensive observability, blue/green deployments, and built-in chaos engineering scenarios for incident response training. Deploy once, break things safely, learn how to fix them.

**What you get:** ALB + ECS Fargate + Aurora + WAF + CloudWatch dashboards/alarms + X-Ray tracing + CodeDeploy blue/green + AWS Fault Injection Simulator chaos experiments.

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

![ECS Fargate Golden Path Architecture](diagrams/ecs-golden-path-diagram.svg)

*Architecture diagram created using AWS official icons and Excalidraw*

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

## Chaos Engineering Lab

Trigger infrastructure failures via AWS Fault Injection Simulator:

| Experiment | Effect | Learning |
|------------|--------|----------|
| **ECS Task Termination** | Kill 50% of tasks → Auto-recovery | Task resilience, health checks |
| **CPU Stress** | 80% CPU load → Autoscaling | Performance under load |
| **Network Latency** | 200ms delays → Response time | Latency tolerance |
| **Aurora Failover** | Force DB failover → Connection handling | Database resilience |

**Game Day Scenarios:**
1. **Task Termination** - Run FIS experiment, observe auto-recovery
2. **Secret Drift** - Rotate DB secret, hit `/db` until errors, redeploy service
3. **CPU Stress** - FIS CPU experiment, watch autoscaling trigger
4. **Network Chaos** - Inject latency, observe p95 metrics

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

**Chaos Engineering:**
- Professional failure injection via AWS FIS
- Infrastructure-level chaos experiments
- Automated rollback on alarm breach
- Enterprise-grade resilience testing

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

## Chaos Experiments

**AWS Fault Injection Simulator Integration:**
- ECS task termination and CPU stress experiments
- Network latency injection for resilience testing
- Aurora failover simulation
- Automated stop conditions via CloudWatch alarms
- Professional chaos engineering patterns

Ready to break things safely and learn incident response? Deploy and start your first game day! 🚀