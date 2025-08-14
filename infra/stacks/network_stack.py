from aws_cdk import Stack, aws_ec2 as ec2, CfnOutput, Tags
from constructs import Construct


class NetworkStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        env_name: str,
        use_one_nat: bool = True,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.env_name = env_name

        # Create VPC with 2 AZs
        self.vpc = ec2.Vpc(
            self,
            "VPC",
            vpc_name=f"golden-path-vpc-{env_name}",
            ip_addresses=ec2.IpAddresses.cidr("10.0.0.0/16"),
            max_azs=2,
            subnet_configuration=[
                # Public subnets for ALB
                ec2.SubnetConfiguration(
                    name="Public", subnet_type=ec2.SubnetType.PUBLIC, cidr_mask=24
                ),
                # Private subnets for ECS and RDS
                ec2.SubnetConfiguration(
                    name="Private",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    cidr_mask=24,
                ),
            ],
            nat_gateways=1 if use_one_nat else 2,
            enable_dns_hostnames=True,
            enable_dns_support=True,
        )

        # Add tags
        Tags.of(self.vpc).add("Name", f"golden-path-vpc-{env_name}")
        Tags.of(self.vpc).add("Environment", env_name)
        Tags.of(self.vpc).add("Project", "ECS-Fargate-Golden-Path")

        # Create VPC Flow Logs
        self.vpc.add_flow_log(
            "VPCFlowLog",
            destination=ec2.FlowLogDestination.to_cloud_watch_logs(),
            traffic_type=ec2.FlowLogTrafficType.ALL,
        )

        # Security Groups will be created in other stacks as needed

        # Outputs
        CfnOutput(
            self,
            "VPCId",
            value=self.vpc.vpc_id,
            description="VPC ID",
            export_name=f"GoldenPath-{env_name}-VPCId",
        )

        CfnOutput(
            self,
            "PublicSubnetIds",
            value=",".join([subnet.subnet_id for subnet in self.vpc.public_subnets]),
            description="Public Subnet IDs",
            export_name=f"GoldenPath-{env_name}-PublicSubnetIds",
        )

        CfnOutput(
            self,
            "PrivateSubnetIds",
            value=",".join([subnet.subnet_id for subnet in self.vpc.private_subnets]),
            description="Private Subnet IDs",
            export_name=f"GoldenPath-{env_name}-PrivateSubnetIds",
        )

        CfnOutput(
            self,
            "AvailabilityZones",
            value=",".join(self.vpc.availability_zones),
            description="Availability Zones",
            export_name=f"GoldenPath-{env_name}-AZs",
        )
