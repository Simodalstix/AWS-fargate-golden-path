# ADR-001: Use ECS Fargate over EC2 for Container Orchestration

## Status
Accepted

## Context
We need to choose a container orchestration platform for our golden path reference architecture. The main options are:
- ECS with EC2 instances
- ECS with Fargate
- Amazon EKS

## Decision
We will use **ECS with Fargate** for the golden path implementation.

## Rationale

### Advantages of Fargate
- **Zero server management**: No EC2 instances to patch, scale, or manage
- **Right-sizing**: Pay only for the exact CPU/memory used by containers
- **Security**: AWS manages the underlying infrastructure and security patches
- **Simplicity**: Reduces operational overhead for teams learning container patterns
- **Faster deployment**: No need to manage cluster capacity or instance types

### Trade-offs Accepted
- **Higher per-task cost**: Fargate costs more per vCPU/GB than equivalent EC2 instances
- **Less control**: Cannot access underlying host or install custom agents
- **Resource constraints**: Limited to Fargate-supported CPU/memory combinations

## Consequences
- Simplified architecture suitable for learning and demonstration
- Higher operational costs acceptable for reference implementation
- Easier to maintain and explain in documentation
- Aligns with AWS serverless-first recommendations

## Alternatives Considered
- **ECS on EC2**: More cost-effective at scale but requires cluster management
- **EKS**: More complex, higher learning curve, overkill for this use case