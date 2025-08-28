from aws_cdk import (
    Stack,
    Duration,
    aws_fis as fis,
    aws_iam as iam,
    aws_ecs as ecs,
    aws_rds as rds,
    aws_ec2 as ec2,
    aws_cloudwatch as cloudwatch,
)
from constructs import Construct
from typing import List


class FISStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        env_name: str,
        vpc: ec2.Vpc,
        ecs_cluster: ecs.Cluster,
        ecs_service: ecs.FargateService,
        database,
        stop_condition_alarms: List[cloudwatch.Alarm],
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.env_name = env_name
        self.vpc = vpc
        self.ecs_cluster = ecs_cluster
        self.ecs_service = ecs_service
        self.database = database
        self.stop_condition_alarms = stop_condition_alarms

        # Create FIS service role
        self.fis_role = self._create_fis_role()

        # Create experiment templates
        self.experiments = {}
        self._create_ecs_experiments()
        self._create_network_experiments()
        self._create_database_experiments()

    def _create_fis_role(self) -> iam.Role:
        """Create IAM role for FIS experiments"""
        role = iam.Role(
            self,
            "FISRole",
            role_name=f"golden-path-fis-role-{self.env_name}",
            assumed_by=iam.ServicePrincipal("fis.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("CloudWatchReadOnlyAccess")
            ],
        )

        # ECS permissions
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "ecs:StopTask",
                    "ecs:ListTasks",
                    "ecs:DescribeTasks",
                    "ecs:DescribeServices",
                    "ecs:DescribeClusters",
                ],
                resources=["*"],
            )
        )

        # RDS permissions
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "rds:FailoverDBCluster",
                    "rds:DescribeDBClusters",
                    "rds:DescribeDBInstances",
                ],
                resources=["*"],
            )
        )

        # EC2 permissions for network experiments
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "ec2:DescribeInstances",
                    "ec2:DescribeNetworkInterfaces",
                    "ec2:DescribeSubnets",
                ],
                resources=["*"],
            )
        )

        return role

    def _create_ecs_experiments(self):
        """Create ECS-related chaos experiments"""
        
        # ECS Task Termination Experiment
        self.experiments["ecs_task_termination"] = fis.CfnExperimentTemplate(
            self,
            "ECSTaskTermination",
            description="Terminate random ECS tasks to test auto-recovery",
            role_arn=self.fis_role.role_arn,
            actions={
                "StopTasks": {
                    "actionId": "aws:ecs:stop-task",
                    "parameters": {
                        "clusterArn": self.ecs_cluster.cluster_arn,
                        "serviceName": self.ecs_service.service_name,
                    },
                    "targets": {"Tasks": "ECSTasksTarget"},
                }
            },
            targets={
                "ECSTasksTarget": {
                    "resourceType": "aws:ecs:task",
                    "resourceArns": ["*"],
                    "selectionMode": "PERCENT(50)",
                    "resourceTags": {
                        "Environment": self.env_name,
                    },
                }
            },
            stop_conditions=[
                {
                    "source": "aws:cloudwatch:alarm",
                    "value": alarm.alarm_arn,
                }
                for alarm in self.stop_condition_alarms
            ],
            tags={
                "Name": f"golden-path-ecs-task-termination-{self.env_name}",
                "Environment": self.env_name,
                "ExperimentType": "ECS",
            },
        )

        # ECS CPU Stress Experiment
        self.experiments["ecs_cpu_stress"] = fis.CfnExperimentTemplate(
            self,
            "ECSCPUStress",
            description="Inject CPU stress into ECS tasks",
            role_arn=self.fis_role.role_arn,
            actions={
                "CPUStress": {
                    "actionId": "aws:ecs:task-cpu-stress",
                    "parameters": {
                        "duration": "PT10M",  # 10 minutes
                        "percent": "80",
                    },
                    "targets": {"Tasks": "ECSTasksTarget"},
                }
            },
            targets={
                "ECSTasksTarget": {
                    "resourceType": "aws:ecs:task",
                    "resourceArns": ["*"],
                    "selectionMode": "COUNT(1)",
                    "resourceTags": {
                        "Environment": self.env_name,
                    },
                }
            },
            stop_conditions=[
                {
                    "source": "aws:cloudwatch:alarm",
                    "value": alarm.alarm_arn,
                }
                for alarm in self.stop_condition_alarms
            ],
            tags={
                "Name": f"golden-path-ecs-cpu-stress-{self.env_name}",
                "Environment": self.env_name,
                "ExperimentType": "ECS",
            },
        )

    def _create_network_experiments(self):
        """Create network-related chaos experiments"""
        
        # Network Latency Experiment
        self.experiments["network_latency"] = fis.CfnExperimentTemplate(
            self,
            "NetworkLatency",
            description="Inject network latency to test resilience",
            role_arn=self.fis_role.role_arn,
            actions={
                "NetworkLatency": {
                    "actionId": "aws:network:latency",
                    "parameters": {
                        "duration": "PT5M",  # 5 minutes
                        "delayMilliseconds": "200",
                        "jitterMilliseconds": "50",
                    },
                    "targets": {"Subnets": "PrivateSubnetsTarget"},
                }
            },
            targets={
                "PrivateSubnetsTarget": {
                    "resourceType": "aws:ec2:subnet",
                    "resourceArns": [subnet.subnet_arn for subnet in self.vpc.private_subnets],
                    "selectionMode": "COUNT(1)",
                }
            },
            stop_conditions=[
                {
                    "source": "aws:cloudwatch:alarm",
                    "value": alarm.alarm_arn,
                }
                for alarm in self.stop_condition_alarms
            ],
            tags={
                "Name": f"golden-path-network-latency-{self.env_name}",
                "Environment": self.env_name,
                "ExperimentType": "Network",
            },
        )

    def _create_database_experiments(self):
        """Create database-related chaos experiments"""
        
        # Aurora Failover Experiment
        if hasattr(self.database, 'cluster_identifier'):
            self.experiments["aurora_failover"] = fis.CfnExperimentTemplate(
                self,
                "AuroraFailover",
                description="Force Aurora cluster failover to test application resilience",
                role_arn=self.fis_role.role_arn,
                actions={
                    "FailoverCluster": {
                        "actionId": "aws:rds:failover-db-cluster",
                        "parameters": {
                            "forceFailover": "true",
                        },
                        "targets": {"Clusters": "AuroraClusterTarget"},
                    }
                },
                targets={
                    "AuroraClusterTarget": {
                        "resourceType": "aws:rds:cluster",
                        "resourceArns": [self.database.cluster_arn],
                        "selectionMode": "ALL",
                    }
                },
                stop_conditions=[
                    {
                        "source": "aws:cloudwatch:alarm",
                        "value": alarm.alarm_arn,
                    }
                    for alarm in self.stop_condition_alarms
                ],
                tags={
                    "Name": f"golden-path-aurora-failover-{self.env_name}",
                    "Environment": self.env_name,
                    "ExperimentType": "Database",
                },
            )