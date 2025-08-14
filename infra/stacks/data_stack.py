from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    aws_rds as rds,
    aws_secretsmanager as secretsmanager,
    aws_ssm as ssm,
    CfnOutput,
    Duration,
    RemovalPolicy,
    Tags,
)
from constructs import Construct


class DataStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        vpc: ec2.Vpc,
        env_name: str,
        db_engine: str = "aurora-postgres",
        rotate_secrets: bool = False,
        min_acu: float = 0.5,
        max_acu: float = 1,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.env_name = env_name
        self.vpc = vpc

        # Create database subnet group
        self.db_subnet_group = rds.SubnetGroup(
            self,
            "DBSubnetGroup",
            description=f"Subnet group for {env_name} database",
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
            subnet_group_name=f"golden-path-db-subnet-group-{env_name}",
        )

        # Create database security group
        self.db_security_group = ec2.SecurityGroup(
            self,
            "DatabaseSecurityGroup",
            vpc=vpc,
            description="Security group for RDS database",
            security_group_name=f"golden-path-db-sg-{env_name}",
            allow_all_outbound=False,
        )

        # Create database credentials secret
        self.db_secret = secretsmanager.Secret(
            self,
            "DatabaseSecret",
            description=f"Database credentials for {env_name}",
            secret_name=f"golden-path/db-credentials/{env_name}",
            generate_secret_string=secretsmanager.SecretStringGenerator(
                secret_string_template='{"username": "dbadmin"}',
                generate_string_key="password",
                exclude_characters=" %+~`#$&*()|[]{}:;<>?!'/\"\\",
                password_length=32,
            ),
        )

        # Create the database based on engine type
        if db_engine == "aurora-postgres":
            self._create_aurora_postgres_cluster(min_acu, max_acu)
        elif db_engine == "postgres":
            self._create_postgres_instance()
        elif db_engine == "mysql":
            self._create_mysql_instance()
        else:
            raise ValueError(f"Unsupported database engine: {db_engine}")

        # Set up secret rotation if enabled
        if rotate_secrets:
            self._setup_secret_rotation()

        # Create SSM parameter for failure mode (for break/fix lab)
        self.failure_mode_parameter = ssm.StringParameter(
            self,
            "FailureModeParameter",
            parameter_name=f"/golden/failure_mode",
            string_value="none",
            description="Parameter to control application failure modes for break/fix lab",
            tier=ssm.ParameterTier.STANDARD,
        )

        # Add tags
        Tags.of(self.database).add("Environment", env_name)
        Tags.of(self.database).add("Project", "ECS-Fargate-Golden-Path")

        # Outputs
        CfnOutput(
            self,
            "DatabaseEndpoint",
            value=(
                self.database.cluster_endpoint.hostname
                if hasattr(self.database, "cluster_endpoint")
                else self.database.instance_endpoint.hostname
            ),
            description="Database endpoint",
            export_name=f"GoldenPath-{env_name}-DatabaseEndpoint",
        )

        CfnOutput(
            self,
            "DatabaseSecretArn",
            value=self.db_secret.secret_arn,
            description="Database secret ARN",
            export_name=f"GoldenPath-{env_name}-DatabaseSecretArn",
        )

        CfnOutput(
            self,
            "DatabaseSecurityGroupId",
            value=self.db_security_group.security_group_id,
            description="Database security group ID",
            export_name=f"GoldenPath-{env_name}-DatabaseSecurityGroupId",
        )

        CfnOutput(
            self,
            "FailureModeParameterName",
            value=self.failure_mode_parameter.parameter_name,
            description="SSM parameter name for failure mode",
            export_name=f"GoldenPath-{env_name}-FailureModeParameterName",
        )

    def _create_aurora_postgres_cluster(self, min_acu: float, max_acu: float):
        """Create Aurora PostgreSQL Serverless v2 cluster"""
        self.database = rds.DatabaseCluster(
            self,
            "AuroraCluster",
            engine=rds.DatabaseClusterEngine.aurora_postgres(
                version=rds.AuroraPostgresEngineVersion.VER_15_3
            ),
            credentials=rds.Credentials.from_secret(self.db_secret),
            writer=rds.ClusterInstance.serverless_v2("writer"),
            readers=[
                rds.ClusterInstance.serverless_v2("reader", scale_with_writer=True)
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
            backup=rds.BackupProps(retention=Duration.days(7)),
            deletion_protection=False,  # Set to True for production
            removal_policy=RemovalPolicy.DESTROY,  # Set to RETAIN for production
            cluster_identifier=f"golden-path-aurora-{self.env_name}",
            monitoring_interval=Duration.seconds(60),
            enable_performance_insights=True,
            performance_insight_retention=rds.PerformanceInsightRetention.DEFAULT,
            cloudwatch_logs_exports=["postgresql"],
        )

    def _create_postgres_instance(self):
        """Create PostgreSQL RDS instance"""
        self.database = rds.DatabaseInstance(
            self,
            "PostgreSQLInstance",
            engine=rds.DatabaseInstanceEngine.postgres(
                version=rds.PostgresEngineVersion.VER_15_3
            ),
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.T3, ec2.InstanceSize.MICRO
            ),
            credentials=rds.Credentials.from_secret(self.db_secret),
            vpc=self.vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
            security_groups=[self.db_security_group],
            subnet_group=self.db_subnet_group,
            default_database_name="goldenpath",
            backup_retention=Duration.days(7),
            deletion_protection=False,
            removal_policy=RemovalPolicy.DESTROY,
            instance_identifier=f"golden-path-postgres-{self.env_name}",
            monitoring_interval=Duration.seconds(60),
            enable_performance_insights=True,
            performance_insight_retention=rds.PerformanceInsightRetention.DEFAULT,
            cloudwatch_logs_exports=["postgresql"],
        )

    def _create_mysql_instance(self):
        """Create MySQL RDS instance"""
        self.database = rds.DatabaseInstance(
            self,
            "MySQLInstance",
            engine=rds.DatabaseInstanceEngine.mysql(
                version=rds.MysqlEngineVersion.VER_8_0_35
            ),
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.T3, ec2.InstanceSize.MICRO
            ),
            credentials=rds.Credentials.from_secret(self.db_secret),
            vpc=self.vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
            security_groups=[self.db_security_group],
            subnet_group=self.db_subnet_group,
            default_database_name="goldenpath",
            backup_retention=Duration.days(7),
            deletion_protection=False,
            removal_policy=RemovalPolicy.DESTROY,
            instance_identifier=f"golden-path-mysql-{self.env_name}",
            monitoring_interval=Duration.seconds(60),
            enable_performance_insights=True,
            performance_insight_retention=rds.PerformanceInsightRetention.DEFAULT,
            cloudwatch_logs_exports=["error", "general", "slow-query"],
        )

    def _setup_secret_rotation(self):
        """Set up automatic secret rotation"""
        if hasattr(self.database, "add_rotation_single_user"):
            # For Aurora clusters
            self.database.add_rotation_single_user()
        else:
            # For RDS instances
            self.db_secret.add_rotation_schedule(
                "RotationSchedule",
                rotation_lambda=secretsmanager.RotationSchedule.rotation_lambda_for_database(
                    self.database, vpc=self.vpc
                ),
                automatically_after=Duration.days(30),
            )
