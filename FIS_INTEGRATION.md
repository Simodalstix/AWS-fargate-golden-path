# AWS Fault Injection Simulator Integration

## Why Use FIS Instead of SSM Parameters

### Current SSM Approach Limitations
- Only application-level failures
- No infrastructure testing
- Manual intervention required
- Limited failure scenarios

### FIS Advantages
- Infrastructure-level fault injection
- Automated experiment management
- Built-in safety mechanisms
- Comprehensive failure scenarios

## Recommended FIS Experiments

### 1. ECS Task Failure
```python
# Add to infrastructure
fis_experiment_template = fis.CfnExperimentTemplate(
    self,
    "ECSTaskFailureExperiment",
    description="Stop ECS tasks to test auto-scaling and recovery",
    role_arn=fis_role.role_arn,
    actions={
        "StopTasks": {
            "actionId": "aws:ecs:stop-task",
            "parameters": {
                "clusterArn": self.cluster.cluster_arn,
                "serviceName": self.ecs_service.service_name
            },
            "targets": {
                "Tasks": "ECSTasksTarget"
            }
        }
    },
    targets={
        "ECSTasksTarget": {
            "resourceType": "aws:ecs:task",
            "resourceArns": ["*"],
            "selectionMode": "PERCENT(50)"
        }
    },
    stop_conditions=[
        {
            "source": "aws:cloudwatch:alarm",
            "value": alb_5xx_alarm.alarm_arn
        }
    ],
    tags={
        "Environment": env_name,
        "ExperimentType": "ECSFailure"
    }
)
```

### 2. Network Latency Injection
```python
network_latency_experiment = fis.CfnExperimentTemplate(
    self,
    "NetworkLatencyExperiment",
    description="Inject network latency to test application resilience",
    role_arn=fis_role.role_arn,
    actions={
        "InjectLatency": {
            "actionId": "aws:ec2:send-spot-instance-interruptions",
            "parameters": {
                "durationMinutes": "10"
            }
        }
    }
)
```

### 3. RDS Failover Test
```python
rds_failover_experiment = fis.CfnExperimentTemplate(
    self,
    "RDSFailoverExperiment",
    description="Test RDS Aurora failover scenarios",
    role_arn=fis_role.role_arn,
    actions={
        "FailoverDB": {
            "actionId": "aws:rds:failover-db-cluster",
            "parameters": {
                "forceFailover": "true"
            },
            "targets": {
                "Clusters": "RDSClustersTarget"
            }
        }
    },
    targets={
        "RDSClustersTarget": {
            "resourceType": "aws:rds:cluster",
            "resourceArns": [self.database.cluster_arn],
            "selectionMode": "ALL"
        }
    }
)
```

## Implementation Strategy

### Phase 1: Keep Current SSM Approach
- Maintain existing application-level failures
- Good for basic testing and demos

### Phase 2: Add FIS Experiments
- Implement infrastructure-level testing
- More comprehensive chaos engineering

### Phase 3: Hybrid Approach
- Use SSM for application failures
- Use FIS for infrastructure failures
- Create comprehensive game day scenarios

## FIS IAM Role
```python
fis_role = iam.Role(
    self,
    "FISRole",
    assumed_by=iam.ServicePrincipal("fis.amazonaws.com"),
    managed_policies=[
        iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSFaultInjectionSimulatorECSAccess"),
        iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSFaultInjectionSimulatorRDSAccess"),
        iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSFaultInjectionSimulatorEC2Access"),
    ]
)
```

## Game Day Scenarios with FIS

### Scenario 1: Complete Service Disruption
1. Stop 50% of ECS tasks (FIS)
2. Inject network latency (FIS)
3. Trigger application errors (SSM)
4. Monitor recovery and scaling

### Scenario 2: Database Resilience
1. Force RDS failover (FIS)
2. Inject connection errors (SSM)
3. Test connection pooling and retry logic

### Scenario 3: Multi-AZ Failure
1. Simulate AZ failure (FIS)
2. Test cross-AZ failover
3. Validate data consistency