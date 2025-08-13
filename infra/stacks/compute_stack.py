from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_elasticloadbalancingv2 as elbv2,
    aws_ecr as ecr,
    aws_iam as iam,
    aws_logs as logs,
    aws_secretsmanager as secretsmanager,
    aws_ssm as ssm,
    aws_wafv2 as wafv2,
    CfnOutput,
    Duration,
    RemovalPolicy,
    Tags,
)
from constructs import Construct
from constructs.kms_key import KmsKey
from constructs.logging_bucket import LoggingBucket
from constructs.waf_web_acl import WafWebAcl


class ComputeStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        vpc: ec2.Vpc,
        database,
        db_secret: secretsmanager.Secret,
        env_name: str,
        desired_count: int = 2,
        cpu: int = 512,
        memory_mib: int = 1024,
        enable_break_fix: bool = True,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.env_name = env_name
        self.vpc = vpc
        self.database = database
        self.db_secret = db_secret

        # Create KMS key for encryption
        self.kms_key = KmsKey(
            self,
            "ComputeKmsKey",
            env_name=env_name,
            description=f"KMS key for Golden Path compute resources in {env_name}",
        )

        # Create S3 bucket for ALB access logs
        self.logging_bucket = LoggingBucket(
            self, "ALBLoggingBucket", env_name=env_name, kms_key=self.kms_key.key
        )

        # Create WAF Web ACL
        self.waf_web_acl = WafWebAcl(self, "WAFWebACL", env_name=env_name)

        # Create ECR repository
        self.ecr_repository = ecr.Repository(
            self,
            "ECRRepository",
            repository_name=f"golden-path-app-{env_name}",
            removal_policy=RemovalPolicy.DESTROY,  # Set to RETAIN for production
            image_scan_on_push=True,
            lifecycle_rules=[
                ecr.LifecycleRule(description="Keep last 10 images", max_image_count=10)
            ],
        )

        # Create ECS cluster
        self.cluster = ecs.Cluster(
            self,
            "ECSCluster",
            cluster_name=f"golden-path-cluster-{env_name}",
            vpc=vpc,
            enable_fargate_capacity_providers=True,
            container_insights=True,
        )

        # Create CloudWatch log group for application logs
        self.log_group = logs.LogGroup(
            self,
            "ApplicationLogGroup",
            log_group_name=f"/ecs/golden-path-app-{env_name}",
            retention=logs.RetentionDays.ONE_MONTH,
            encryption_key=self.kms_key.key,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # Create security groups
        self._create_security_groups()

        # Create ALB
        self._create_application_load_balancer()

        # Create ECS service
        self._create_ecs_service(cpu, memory_mib, desired_count, enable_break_fix)

        # Associate WAF with ALB
        wafv2.CfnWebACLAssociation(
            self,
            "WAFAssociation",
            resource_arn=self.alb.load_balancer_arn,
            web_acl_arn=self.waf_web_acl.web_acl_arn,
        )

        # Add tags
        Tags.of(self.cluster).add("Environment", env_name)
        Tags.of(self.cluster).add("Project", "ECS-Fargate-Golden-Path")

        # Outputs
        CfnOutput(
            self,
            "ALBDNSName",
            value=self.alb.load_balancer_dns_name,
            description="ALB DNS name",
            export_name=f"GoldenPath-{env_name}-ALBDNSName",
        )

        CfnOutput(
            self,
            "ECRRepositoryURI",
            value=self.ecr_repository.repository_uri,
            description="ECR repository URI",
            export_name=f"GoldenPath-{env_name}-ECRRepositoryURI",
        )

        CfnOutput(
            self,
            "ECSClusterName",
            value=self.cluster.cluster_name,
            description="ECS cluster name",
            export_name=f"GoldenPath-{env_name}-ECSClusterName",
        )

        CfnOutput(
            self,
            "ECSServiceName",
            value=self.ecs_service.service_name,
            description="ECS service name",
            export_name=f"GoldenPath-{env_name}-ECSServiceName",
        )

    def _create_security_groups(self):
        """Create security groups for ALB and ECS"""
        # ALB Security Group
        self.alb_security_group = ec2.SecurityGroup(
            self,
            "ALBSecurityGroup",
            vpc=self.vpc,
            description="Security group for ALB",
            security_group_name=f"golden-path-alb-sg-{self.env_name}",
            allow_all_outbound=False,
        )

        # Allow HTTP and HTTPS inbound
        self.alb_security_group.add_ingress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(80),
            description="Allow HTTP inbound",
        )

        self.alb_security_group.add_ingress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(443),
            description="Allow HTTPS inbound",
        )

        # ECS Security Group
        self.ecs_security_group = ec2.SecurityGroup(
            self,
            "ECSSecurityGroup",
            vpc=self.vpc,
            description="Security group for ECS tasks",
            security_group_name=f"golden-path-ecs-sg-{self.env_name}",
            allow_all_outbound=True,
        )

        # Allow inbound from ALB
        self.ecs_security_group.add_ingress_rule(
            peer=self.alb_security_group,
            connection=ec2.Port.tcp(80),
            description="Allow inbound from ALB",
        )

        # Allow ALB to reach ECS
        self.alb_security_group.add_egress_rule(
            peer=self.ecs_security_group,
            connection=ec2.Port.tcp(80),
            description="Allow outbound to ECS",
        )

        # Allow ECS to reach database
        if hasattr(self.database, "connections"):
            self.database.connections.allow_default_port_from(
                self.ecs_security_group, "Allow ECS to access database"
            )

    def _create_application_load_balancer(self):
        """Create Application Load Balancer"""
        self.alb = elbv2.ApplicationLoadBalancer(
            self,
            "ALB",
            vpc=self.vpc,
            internet_facing=True,
            load_balancer_name=f"golden-path-alb-{self.env_name}",
            security_group=self.alb_security_group,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
        )

        # Enable access logging
        self.alb.log_access_logs(
            bucket=self.logging_bucket.bucket, prefix=f"alb-logs/{self.env_name}"
        )

        # Create target groups for blue/green deployment
        self.target_group_1 = elbv2.ApplicationTargetGroup(
            self,
            "TargetGroup1",
            vpc=self.vpc,
            port=80,
            protocol=elbv2.ApplicationProtocol.HTTP,
            target_type=elbv2.TargetType.IP,
            target_group_name=f"golden-path-tg1-{self.env_name}",
            health_check=elbv2.HealthCheck(
                enabled=True,
                healthy_http_codes="200",
                path="/healthz",
                protocol=elbv2.Protocol.HTTP,
                timeout=Duration.seconds(5),
                interval=Duration.seconds(30),
                healthy_threshold_count=2,
                unhealthy_threshold_count=3,
            ),
        )

        self.target_group_2 = elbv2.ApplicationTargetGroup(
            self,
            "TargetGroup2",
            vpc=self.vpc,
            port=80,
            protocol=elbv2.ApplicationProtocol.HTTP,
            target_type=elbv2.TargetType.IP,
            target_group_name=f"golden-path-tg2-{self.env_name}",
            health_check=elbv2.HealthCheck(
                enabled=True,
                healthy_http_codes="200",
                path="/healthz",
                protocol=elbv2.Protocol.HTTP,
                timeout=Duration.seconds(5),
                interval=Duration.seconds(30),
                healthy_threshold_count=2,
                unhealthy_threshold_count=3,
            ),
        )

        # Create listener
        self.listener = self.alb.add_listener(
            "Listener",
            port=80,
            protocol=elbv2.ApplicationProtocol.HTTP,
            default_action=elbv2.ListenerAction.forward([self.target_group_1]),
        )

    def _create_ecs_service(
        self, cpu: int, memory_mib: int, desired_count: int, enable_break_fix: bool
    ):
        """Create ECS Fargate service"""
        # Create task execution role
        self.task_execution_role = iam.Role(
            self,
            "TaskExecutionRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AmazonECSTaskExecutionRolePolicy"
                )
            ],
        )

        # Grant access to ECR
        self.ecr_repository.grant_pull(self.task_execution_role)

        # Grant access to CloudWatch Logs
        self.log_group.grant_write(self.task_execution_role)

        # Grant access to Secrets Manager
        self.db_secret.grant_read(self.task_execution_role)

        # Create task role
        self.task_role = iam.Role(
            self, "TaskRole", assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com")
        )

        # Grant access to Secrets Manager for runtime
        self.db_secret.grant_read(self.task_role)

        # Grant access to SSM Parameter Store for failure mode
        if enable_break_fix:
            self.task_role.add_to_policy(
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["ssm:GetParameter"],
                    resources=[
                        f"arn:aws:ssm:{self.region}:{self.account}:parameter/golden/failure_mode"
                    ],
                )
            )

        # Grant access to X-Ray
        self.task_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["xray:PutTraceSegments", "xray:PutTelemetryRecords"],
                resources=["*"],
            )
        )

        # Create task definition
        self.task_definition = ecs.FargateTaskDefinition(
            self,
            "TaskDefinition",
            family=f"golden-path-task-{self.env_name}",
            cpu=cpu,
            memory_limit_mib=memory_mib,
            execution_role=self.task_execution_role,
            task_role=self.task_role,
        )

        # Add main application container
        self.app_container = self.task_definition.add_container(
            "AppContainer",
            image=ecs.ContainerImage.from_registry(
                "public.ecr.aws/nginx/nginx:latest"
            ),  # Placeholder image
            container_name="app",
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="app", log_group=self.log_group
            ),
            environment={
                "DB_SECRET_ARN": self.db_secret.secret_arn,
                "PARAM_FAILURE_MODE": (
                    "/golden/failure_mode" if enable_break_fix else ""
                ),
                "AWS_REGION": self.region,
            },
            health_check=ecs.HealthCheck(
                command=["CMD-SHELL", "curl -f http://localhost/healthz || exit 1"],
                interval=Duration.seconds(30),
                timeout=Duration.seconds(5),
                retries=3,
                start_period=Duration.seconds(60),
            ),
        )

        # Add port mapping
        self.app_container.add_port_mappings(
            ecs.PortMapping(container_port=80, protocol=ecs.Protocol.TCP)
        )

        # Add X-Ray daemon sidecar
        self.xray_container = self.task_definition.add_container(
            "XRayContainer",
            image=ecs.ContainerImage.from_registry(
                "public.ecr.aws/xray/aws-xray-daemon:latest"
            ),
            container_name="xray-daemon",
            cpu=32,
            memory_limit_mib=256,
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="xray", log_group=self.log_group
            ),
            user="1337",
        )

        self.xray_container.add_port_mappings(
            ecs.PortMapping(container_port=2000, protocol=ecs.Protocol.UDP)
        )

        # Create ECS service
        self.ecs_service = ecs.FargateService(
            self,
            "ECSService",
            cluster=self.cluster,
            task_definition=self.task_definition,
            service_name=f"golden-path-service-{self.env_name}",
            desired_count=desired_count,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
            security_groups=[self.ecs_security_group],
            enable_execute_command=True,
            capacity_provider_strategies=[
                ecs.CapacityProviderStrategy(capacity_provider="FARGATE", weight=1)
            ],
            enable_logging=True,
            health_check_grace_period=Duration.seconds(60),
            min_healthy_percent=100,
            max_healthy_percent=200,
        )

        # Attach to target group
        self.ecs_service.attach_to_application_target_group(self.target_group_1)

        # Enable auto scaling
        self.scaling_target = self.ecs_service.auto_scale_task_count(
            min_capacity=desired_count, max_capacity=desired_count * 4
        )

        # Scale based on CPU utilization
        self.scaling_target.scale_on_cpu_utilization(
            "CPUScaling",
            target_utilization_percent=70,
            scale_in_cooldown=Duration.minutes(5),
            scale_out_cooldown=Duration.minutes(2),
        )

        # Scale based on ALB request count per target
        self.scaling_target.scale_on_request_count(
            "RequestCountScaling",
            requests_per_target=1000,
            target_group=self.target_group_1,
            scale_in_cooldown=Duration.minutes(5),
            scale_out_cooldown=Duration.minutes(2),
        )
