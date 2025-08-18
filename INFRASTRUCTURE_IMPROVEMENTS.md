# Infrastructure Best Practices Improvements

## 1. ECS Service Configuration
```python
# Add proper resource limits and requests
self.task_definition = ecs.FargateTaskDefinition(
    self,
    "TaskDefinition",
    family=f"golden-path-task-{self.env_name}",
    cpu=cpu,
    memory_limit_mib=memory_mib,
    execution_role=self.task_execution_role,
    task_role=self.task_role,
    # Add ephemeral storage if needed
    ephemeral_storage_gib=21,  # Default is 20GB
)

# Configure proper scaling
self.scaling_target.scale_on_cpu_utilization(
    "CPUScaling",
    target_utilization_percent=70,
    scale_in_cooldown=Duration.minutes(5),
    scale_out_cooldown=Duration.minutes(2),
    # Add scale-in protection
    disable_scale_in=False,
)

# Add memory-based scaling
self.scaling_target.scale_on_memory_utilization(
    "MemoryScaling",
    target_utilization_percent=80,
    scale_in_cooldown=Duration.minutes(5),
    scale_out_cooldown=Duration.minutes(2),
)
```

## 2. ALB Configuration
```python
# Enable deletion protection
self.alb = elbv2.ApplicationLoadBalancer(
    self,
    "ALB",
    vpc=self.vpc,
    internet_facing=True,
    load_balancer_name=f"golden-path-alb-{self.env_name}",
    security_group=self.alb_security_group,
    vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
    deletion_protection=True,  # Enable for production
    idle_timeout=Duration.seconds(60),
)

# Add HTTPS listener with certificate
certificate = acm.Certificate.from_certificate_arn(
    self, "Certificate", certificate_arn="arn:aws:acm:..."
)

https_listener = self.alb.add_listener(
    "HTTPSListener",
    port=443,
    protocol=elbv2.ApplicationProtocol.HTTPS,
    certificates=[certificate],
    default_action=elbv2.ListenerAction.forward([self.target_group_1]),
)

# Redirect HTTP to HTTPS
http_listener = self.alb.add_listener(
    "HTTPListener",
    port=80,
    protocol=elbv2.ApplicationProtocol.HTTP,
    default_action=elbv2.ListenerAction.redirect(
        protocol="HTTPS",
        port="443",
        permanent=True
    ),
)
```

## 3. RDS Configuration
```python
# Production-ready RDS configuration
self.database = rds.DatabaseCluster(
    self,
    "AuroraCluster",
    engine=rds.DatabaseClusterEngine.aurora_postgres(
        version=rds.AuroraPostgresEngineVersion.VER_15_4  # Latest version
    ),
    credentials=rds.Credentials.from_secret(self.db_secret),
    writer=rds.ClusterInstance.serverless_v2("writer"),
    readers=[
        rds.ClusterInstance.serverless_v2("reader1", scale_with_writer=True),
        rds.ClusterInstance.serverless_v2("reader2", scale_with_writer=True),
    ],
    serverless_v2_min_capacity=min_acu,
    serverless_v2_max_capacity=max_acu,
    vpc=self.vpc,
    vpc_subnets=ec2.SubnetSelection(
        subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
    ),
    security_groups=[self.db_security_group],
    subnet_group=self.db_subnet_group,
    default_database_name="goldenpath",
    backup=rds.BackupProps(
        retention=Duration.days(30),  # Increase backup retention
        preferred_window="03:00-04:00",  # Off-peak hours
    ),
    preferred_maintenance_window="sun:04:00-sun:05:00",
    deletion_protection=True,  # Enable for production
    removal_policy=RemovalPolicy.RETAIN,  # Retain for production
    cluster_identifier=f"golden-path-aurora-{self.env_name}",
    cloudwatch_logs_exports=["postgresql"],
    monitoring_interval=Duration.seconds(60),
    enable_performance_insights=True,
    performance_insight_retention=rds.PerformanceInsightRetention.MONTHS_3,
    # Enable auto minor version upgrade
    auto_minor_version_upgrade=True,
)
```

## 4. VPC Endpoints
```python
# Add VPC endpoints for AWS services
self.vpc.add_gateway_endpoint(
    "S3Endpoint",
    service=ec2.GatewayVpcEndpointAwsService.S3,
    subnets=[ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS)]
)

self.vpc.add_interface_endpoint(
    "SecretsManagerEndpoint",
    service=ec2.InterfaceVpcEndpointAwsService.SECRETS_MANAGER,
    subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
    security_groups=[self.vpc_endpoint_sg]
)

self.vpc.add_interface_endpoint(
    "SSMEndpoint",
    service=ec2.InterfaceVpcEndpointAwsService.SSM,
    subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
    security_groups=[self.vpc_endpoint_sg]
)
```

## 5. Monitoring and Alerting
```python
# Add comprehensive monitoring
self.custom_metrics = [
    cloudwatch.Metric(
        namespace="AWS/ApplicationELB",
        metric_name="RequestCount",
        dimensions_map={"LoadBalancer": self.alb.load_balancer_full_name},
        statistic="Sum",
    ),
    cloudwatch.Metric(
        namespace="AWS/ApplicationELB",
        metric_name="TargetResponseTime",
        dimensions_map={"LoadBalancer": self.alb.load_balancer_full_name},
        statistic="Average",
    ),
]

# Add composite alarms
composite_alarm = cloudwatch.CompositeAlarm(
    self,
    "ServiceHealthAlarm",
    alarm_description="Overall service health",
    composite_alarm_rule=cloudwatch.AlarmRule.any_of(
        cloudwatch.AlarmRule.from_alarm(alb_5xx_alarm, cloudwatch.AlarmState.ALARM),
        cloudwatch.AlarmRule.from_alarm(ecs_task_count_alarm, cloudwatch.AlarmState.ALARM),
        cloudwatch.AlarmRule.from_alarm(rds_cpu_alarm, cloudwatch.AlarmState.ALARM),
    ),
)
```