# ECS Fargate Golden Path Architecture Diagram

## Main Architecture Flow (Left to Right)

```
[Internet] → [WAF] → [ALB] → [ECS Tasks] → [RDS Aurora]
                      ↓
                   [S3 Logs]
```

## Detailed Component Layout for Excalidraw

### Top Section - Internet & Security
- **Internet Cloud** (top center)
- **WAF Shield** (below internet, protecting ALB)

### Public Subnet Section (Light Blue Background)
- **Application Load Balancer** (rectangle with "ALB" label)
- **Target Group 1** (small rectangle connected to ALB)
- **Target Group 2** (small rectangle connected to ALB)
- Label: "Public Subnets (2 AZs)"

### Private Subnet Section (Light Green Background)
- **ECS Cluster** (large rectangle containing):
  - **ECS Task 1** (container icon)
  - **ECS Task 2** (container icon)
  - **X-Ray Daemon** (small sidecar containers)
- Label: "Private Subnets (2 AZs)"

### Database Section (Light Purple Background)
- **Aurora PostgreSQL Cluster** (cylinder shape)
- **Writer Instance** (smaller cylinder)
- **Reader Instance** (smaller cylinder)
- Label: "Database Subnets"

### Side Services (Right Side)
- **ECR Repository** (container registry icon)
- **Secrets Manager** (key icon)
- **SSM Parameter Store** (settings icon)
- **S3 Logging Bucket** (bucket icon)
- **KMS Key** (lock icon)

### Monitoring Section (Bottom)
- **CloudWatch** (monitoring icon)
- **X-Ray Tracing** (trace icon)
- **SNS Alarms** (notification icon)

### Deployment Section (Top Right)
- **CodeDeploy** (deployment icon)
- **Blue/Green Process** (two circles, one blue, one green)

## Connection Lines & Arrows

### Traffic Flow (Thick Blue Arrows)
1. Internet → WAF
2. WAF → ALB
3. ALB → Target Groups
4. Target Groups → ECS Tasks
5. ECS Tasks → RDS

### Management Flow (Thin Gray Arrows)
1. ECS Tasks → ECR (pull images)
2. ECS Tasks → Secrets Manager (get DB creds)
3. ECS Tasks → SSM (get failure mode)
4. ALB → S3 (access logs)
5. All services → CloudWatch (metrics)
6. ECS Tasks → X-Ray (traces)

### Security Flow (Red Dashed Lines)
1. KMS → S3 (encryption)
2. KMS → RDS (encryption)
3. KMS → CloudWatch Logs (encryption)

## Labels & Annotations

### Network Labels
- "VPC: 10.0.0.0/16"
- "AZ-1: ap-southeast-2a"
- "AZ-2: ap-southeast-2b"
- "NAT Gateway" (in public subnet)

### Security Groups (Small Shields)
- "ALB-SG" (near ALB)
- "ECS-SG" (near ECS tasks)
- "RDS-SG" (near database)

### Ports (Small Numbers)
- "80/443" (ALB)
- "80" (ECS tasks)
- "5432" (RDS)

## Color Scheme
- **Public Subnets**: Light Blue (#E3F2FD)
- **Private Subnets**: Light Green (#E8F5E8)
- **Database Subnets**: Light Purple (#F3E5F5)
- **AWS Services**: Orange (#FFE0B2)
- **Monitoring**: Yellow (#FFF9C4)
- **Security**: Red (#FFEBEE)

## Icons to Use in Excalidraw
- Cloud (Internet)
- Shield (WAF, Security Groups)
- Rectangle (ALB, Load Balancer)
- Container/Box (ECS Tasks)
- Cylinder (Databases)
- Bucket (S3)
- Key/Lock (Secrets, KMS)
- Gear (SSM Parameters)
- Chart (CloudWatch)
- Bell (SNS)
- Arrow (CodeDeploy)

## Text Annotations
- Add small text boxes explaining:
  - "Blue/Green Deployment"
  - "Auto Scaling 2-8 tasks"
  - "Multi-AZ for HA"
  - "Encrypted at rest & transit"
  - "Break/Fix Lab Ready"