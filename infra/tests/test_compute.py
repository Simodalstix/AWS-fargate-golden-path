import pytest
import aws_cdk as cdk
from aws_cdk import assertions
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_rds as rds
from aws_cdk import aws_secretsmanager as secretsmanager

from stacks.network_stack import NetworkStack
from stacks.data_stack import DataStack
from stacks.compute_stack import ComputeStack


class TestComputeStack:
    """Test cases for the ComputeStack"""

    @pytest.fixture
    def app(self):
        """Create a CDK app for testing"""
        return cdk.App(context={
            "@aws-cdk/aws-s3:createDefaultLoggingPolicy": True,
        })

    @pytest.fixture
    def network_stack(self, app):
        """Create a network stack for testing"""
        env = cdk.Environment(account="123456789012", region="us-east-1")
        return NetworkStack(app, "TestNetworkStack", env_name="test", use_one_nat=True, env=env)

    @pytest.fixture
    def data_stack(self, app, network_stack):
        """Create a data stack for testing"""
        env = cdk.Environment(account="123456789012", region="us-east-1")
        return DataStack(
            app,
            "TestDataStack",
            vpc=network_stack.vpc,
            env_name="test",
            db_engine="aurora-postgres",
            rotate_secrets=False,
            min_acu=0.5,
            max_acu=1,
            env=env,
        )

    @pytest.fixture
    def compute_stack(self, app, network_stack, data_stack):
        """Create a compute stack for testing"""
        env = cdk.Environment(account="123456789012", region="us-east-1")
        return ComputeStack(
            app,
            "TestComputeStack",
            vpc=network_stack.vpc,
            database=data_stack.database,
            db_secret=data_stack.db_secret,
            env_name="test",
            desired_count=2,
            cpu=512,
            memory_mib=1024,
            env=env,
        )

    def test_ecs_service_created(self, compute_stack):
        """Test that ECS service is created with correct configuration"""
        template = assertions.Template.from_stack(compute_stack)

        # Check ECS service exists
        template.has_resource_properties(
            "AWS::ECS::Service",
            {
                "ServiceName": "golden-path-service-test",
                "DesiredCount": 2,
                "LaunchType": "FARGATE",
            },
        )

    def test_ecs_service_has_fargate_capacity_provider(self, compute_stack):
        """Test that ECS service uses Fargate capacity provider"""
        template = assertions.Template.from_stack(compute_stack)

        template.has_resource_properties(
            "AWS::ECS::Service",
            {
                "CapacityProviderStrategy": [
                    {"CapacityProvider": "FARGATE", "Weight": 1}
                ]
            },
        )

    def test_alb_created_with_correct_configuration(self, compute_stack):
        """Test that ALB is created with proper configuration"""
        template = assertions.Template.from_stack(compute_stack)

        # Check ALB exists
        template.has_resource_properties(
            "AWS::ElasticLoadBalancingV2::LoadBalancer",
            {
                "Name": "golden-path-alb-test",
                "Scheme": "internet-facing",
                "Type": "application",
            },
        )

    def test_alb_has_access_logging_enabled(self, compute_stack):
        """Test that ALB has access logging enabled"""
        template = assertions.Template.from_stack(compute_stack)

        template.has_resource_properties(
            "AWS::ElasticLoadBalancingV2::LoadBalancer",
            {
                "LoadBalancerAttributes": assertions.Match.array_with(
                    [{"Key": "access_logs.s3.enabled", "Value": "true"}]
                )
            },
        )

    def test_target_groups_created_for_blue_green(self, compute_stack):
        """Test that two target groups are created for blue/green deployment"""
        template = assertions.Template.from_stack(compute_stack)

        # Should have exactly 2 target groups
        template.resource_count_is("AWS::ElasticLoadBalancingV2::TargetGroup", 2)

        # Check target group configuration
        template.has_resource_properties(
            "AWS::ElasticLoadBalancingV2::TargetGroup",
            {
                "Name": "golden-path-tg1-test",
                "Port": 80,
                "Protocol": "HTTP",
                "TargetType": "ip",
                "HealthCheckPath": "/healthz",
            },
        )

        template.has_resource_properties(
            "AWS::ElasticLoadBalancingV2::TargetGroup",
            {
                "Name": "golden-path-tg2-test",
                "Port": 80,
                "Protocol": "HTTP",
                "TargetType": "ip",
                "HealthCheckPath": "/healthz",
            },
        )

    def test_task_definition_has_correct_configuration(self, compute_stack):
        """Test that ECS task definition has correct configuration"""
        template = assertions.Template.from_stack(compute_stack)

        template.has_resource_properties(
            "AWS::ECS::TaskDefinition",
            {
                "Family": "golden-path-task-test",
                "Cpu": "512",
                "Memory": "1024",
                "NetworkMode": "awsvpc",
                "RequiresCompatibilities": ["FARGATE"],
            },
        )

    def test_task_role_has_required_permissions(self, compute_stack):
        """Test that task role has required permissions"""
        template = assertions.Template.from_stack(compute_stack)

        # Check that task role exists
        template.has_resource_properties(
            "AWS::IAM::Role",
            {
                "AssumeRolePolicyDocument": {
                    "Statement": [
                        {
                            "Action": "sts:AssumeRole",
                            "Effect": "Allow",
                            "Principal": {"Service": "ecs-tasks.amazonaws.com"},
                        }
                    ]
                }
            },
        )

        # Check for SSM parameter access policy
        template.has_resource_properties(
            "AWS::IAM::Policy",
            {
                "PolicyDocument": {
                    "Statement": assertions.Match.array_with(
                        [
                            {
                                "Effect": "Allow",
                                "Action": ["ssm:GetParameter"],
                                "Resource": assertions.Match.string_like_regexp(
                                    ".*parameter/golden/failure_mode"
                                ),
                            }
                        ]
                    )
                }
            },
        )

        # Check for X-Ray permissions
        template.has_resource_properties(
            "AWS::IAM::Policy",
            {
                "PolicyDocument": {
                    "Statement": assertions.Match.array_with(
                        [
                            {
                                "Effect": "Allow",
                                "Action": [
                                    "xray:PutTraceSegments",
                                    "xray:PutTelemetryRecords",
                                ],
                                "Resource": "*",
                            }
                        ]
                    )
                }
            },
        )

    def test_security_groups_configured_correctly(self, compute_stack):
        """Test that security groups are configured with proper rules"""
        template = assertions.Template.from_stack(compute_stack)

        # ALB security group should allow HTTP/HTTPS inbound
        template.has_resource_properties(
            "AWS::EC2::SecurityGroup",
            {
                "GroupDescription": "Security group for ALB",
                "SecurityGroupIngress": assertions.Match.array_with(
                    [
                        {
                            "IpProtocol": "tcp",
                            "FromPort": 80,
                            "ToPort": 80,
                            "CidrIp": "0.0.0.0/0",
                        },
                        {
                            "IpProtocol": "tcp",
                            "FromPort": 443,
                            "ToPort": 443,
                            "CidrIp": "0.0.0.0/0",
                        },
                    ]
                ),
            },
        )

        # ECS security group should allow inbound from ALB
        template.has_resource_properties(
            "AWS::EC2::SecurityGroup",
            {"GroupDescription": "Security group for ECS tasks"},
        )

    def test_waf_web_acl_created(self, compute_stack):
        """Test that WAF Web ACL is created"""
        template = assertions.Template.from_stack(compute_stack)

        template.has_resource_properties(
            "AWS::WAFv2::WebACL", {"Name": "golden-path-waf-test", "Scope": "REGIONAL"}
        )

    def test_waf_has_managed_rule_groups(self, compute_stack):
        """Test that WAF includes required managed rule groups"""
        template = assertions.Template.from_stack(compute_stack)

        template.has_resource_properties(
            "AWS::WAFv2::WebACL",
            {
                "Rules": assertions.Match.array_with(
                    [
                        {
                            "Name": "AWSManagedRulesCommonRuleSet",
                            "Priority": 1,
                            "Statement": {
                                "ManagedRuleGroupStatement": {
                                    "VendorName": "AWS",
                                    "Name": "AWSManagedRulesCommonRuleSet",
                                }
                            },
                        },
                        {
                            "Name": "AWSManagedRulesKnownBadInputsRuleSet",
                            "Priority": 2,
                            "Statement": {
                                "ManagedRuleGroupStatement": {
                                    "VendorName": "AWS",
                                    "Name": "AWSManagedRulesKnownBadInputsRuleSet",
                                }
                            },
                        },
                        {
                            "Name": "RateLimitRule",
                            "Priority": 4,
                            "Statement": {
                                "RateBasedStatement": {
                                    "Limit": 2000,
                                    "AggregateKeyType": "IP",
                                }
                            },
                        },
                    ]
                )
            },
        )

    def test_waf_associated_with_alb(self, compute_stack):
        """Test that WAF is associated with ALB"""
        template = assertions.Template.from_stack(compute_stack)

        template.has_resource(
            "AWS::WAFv2::WebACLAssociation",
            {
                "Properties": assertions.Match.object_like(
                    {
                        "ResourceArn": assertions.Match.any_value(),
                        "WebACLArn": assertions.Match.any_value(),
                    }
                )
            },
        )

    def test_ecr_repository_created(self, compute_stack):
        """Test that ECR repository is created"""
        template = assertions.Template.from_stack(compute_stack)

        template.has_resource_properties(
            "AWS::ECR::Repository",
            {
                "RepositoryName": "golden-path-app-test",
                "ImageScanningConfiguration": {"ScanOnPush": True},
            },
        )

    def test_cloudwatch_log_group_created(self, compute_stack):
        """Test that CloudWatch log group is created"""
        template = assertions.Template.from_stack(compute_stack)

        template.has_resource_properties(
            "AWS::Logs::LogGroup",
            {"LogGroupName": "/ecs/golden-path-app-test", "RetentionInDays": 30},
        )

    def test_autoscaling_configured(self, compute_stack):
        """Test that autoscaling is configured for ECS service"""
        template = assertions.Template.from_stack(compute_stack)

        # Check for autoscaling target
        template.has_resource_properties(
            "AWS::ApplicationAutoScaling::ScalableTarget",
            {
                "ServiceNamespace": "ecs",
                "ScalableDimension": "ecs:service:DesiredCount",
                "MinCapacity": 2,
                "MaxCapacity": 8,
            },
        )

        # Check for CPU scaling policy
        template.has_resource_properties(
            "AWS::ApplicationAutoScaling::ScalingPolicy",
            {
                "PolicyType": "TargetTrackingScaling",
                "TargetTrackingScalingPolicyConfiguration": {
                    "TargetValue": 70,
                    "PredefinedMetricSpecification": {
                        "PredefinedMetricType": "ECSServiceAverageCPUUtilization"
                    },
                },
            },
        )

        # Check for ALB request count scaling policy
        template.has_resource_properties(
            "AWS::ApplicationAutoScaling::ScalingPolicy",
            {
                "PolicyType": "TargetTrackingScaling",
                "TargetTrackingScalingPolicyConfiguration": {
                    "TargetValue": 1000,
                    "PredefinedMetricSpecification": {
                        "PredefinedMetricType": "ALBRequestCountPerTarget"
                    },
                },
            },
        )

    def test_s3_bucket_for_alb_logs_created(self, compute_stack):
        """Test that S3 bucket for ALB logs is created with proper configuration"""
        template = assertions.Template.from_stack(compute_stack)

        template.has_resource_properties(
            "AWS::S3::Bucket",
            {
                "BucketEncryption": {
                    "ServerSideEncryptionConfiguration": [
                        {"ServerSideEncryptionByDefault": {"SSEAlgorithm": "aws:kms"}}
                    ]
                },
                "VersioningConfiguration": {"Status": "Enabled"},
                "PublicAccessBlockConfiguration": {
                    "BlockPublicAcls": True,
                    "BlockPublicPolicy": True,
                    "IgnorePublicAcls": True,
                    "RestrictPublicBuckets": True,
                },
            },
        )

    def test_kms_key_created_for_encryption(self, compute_stack):
        """Test that KMS key is created for encryption"""
        template = assertions.Template.from_stack(compute_stack)

        template.has_resource_properties(
            "AWS::KMS::Key",
            {
                "Description": "KMS key for Golden Path compute resources in test",
                "EnableKeyRotation": True,
            },
        )

    def test_task_definition_has_xray_sidecar(self, compute_stack):
        """Test that task definition includes X-Ray daemon sidecar"""
        template = assertions.Template.from_stack(compute_stack)

        # The task definition should have container definitions including X-Ray
        template.has_resource_properties(
            "AWS::ECS::TaskDefinition",
            {
                "ContainerDefinitions": assertions.Match.array_with(
                    [
                        {
                            "Name": "xray-daemon",
                            "Image": "public.ecr.aws/xray/aws-xray-daemon:latest",
                            "Cpu": 32,
                            "Memory": 256,
                            "User": "1337",
                        }
                    ]
                )
            },
        )

    def test_ecs_exec_enabled(self, compute_stack):
        """Test that ECS Exec is enabled on the service"""
        template = assertions.Template.from_stack(compute_stack)

        template.has_resource_properties(
            "AWS::ECS::Service", {"EnableExecuteCommand": True}
        )

    def test_health_check_configuration(self, compute_stack):
        """Test that health checks are properly configured"""
        template = assertions.Template.from_stack(compute_stack)

        template.has_resource_properties(
            "AWS::ElasticLoadBalancingV2::TargetGroup",
            {
                "HealthCheckPath": "/healthz",
                "HealthCheckProtocol": "HTTP",
                "HealthCheckTimeoutSeconds": 5,
                "HealthCheckIntervalSeconds": 30,
                "HealthyThresholdCount": 2,
                "UnhealthyThresholdCount": 3,
            },
        )

    def test_outputs_created(self, compute_stack):
        """Test that required outputs are created"""
        template = assertions.Template.from_stack(compute_stack)

        # Check for outputs
        template.has_output("ALBDNSName", {})
        template.has_output("ECRRepositoryURI", {})
        template.has_output("ECSClusterName", {})
        template.has_output("ECSServiceName", {})
