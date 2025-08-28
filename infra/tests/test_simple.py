import pytest
import aws_cdk as cdk
from aws_cdk import assertions

from stacks.network_stack import NetworkStack
from stacks.data_stack import DataStack
from stacks.compute_stack import ComputeStack
from stacks.observability_stack import ObservabilityStack


class TestSimpleIntegration:
    """Simple integration tests that verify basic stack creation"""

    @pytest.fixture
    def app(self):
        """Create a CDK app for testing"""
        return cdk.App(context={
            "@aws-cdk/aws-s3:createDefaultLoggingPolicy": True,
        })

    def test_all_stacks_synthesize(self, app):
        """Test that all stacks can be synthesized without errors"""
        env = cdk.Environment(account="123456789012", region="us-east-1")
        
        # Create all stacks
        network_stack = NetworkStack(app, "TestNetworkStack", env_name="test", use_one_nat=True, env=env)
        
        data_stack = DataStack(
            app, "TestDataStack", vpc=network_stack.vpc, env_name="test",
            db_engine="aurora-postgres", rotate_secrets=False, min_acu=0.5, max_acu=1, env=env
        )
        
        compute_stack = ComputeStack(
            app, "TestComputeStack", vpc=network_stack.vpc, database=data_stack.database,
            db_secret=data_stack.db_secret, env_name="test", desired_count=2, cpu=512, memory_mib=1024, env=env
        )
        
        observability_stack = ObservabilityStack(
            app, "TestObservabilityStack", alb=compute_stack.alb, ecs_service=compute_stack.ecs_service,
            database=data_stack.database, waf_web_acl=compute_stack.waf_web_acl, env_name="test", env=env
        )
        
        # If we get here without exceptions, synthesis worked
        assert network_stack is not None
        assert data_stack is not None
        assert compute_stack is not None
        assert observability_stack is not None

    def test_basic_resources_exist(self, app):
        """Test that basic resources are created"""
        env = cdk.Environment(account="123456789012", region="us-east-1")
        
        network_stack = NetworkStack(app, "TestNetworkStack2", env_name="test", use_one_nat=True, env=env)
        template = assertions.Template.from_stack(network_stack)
        
        # Check VPC exists
        template.has_resource("AWS::EC2::VPC", {})
        
        # Check subnets exist
        template.has_resource("AWS::EC2::Subnet", {})
        
        # Check NAT Gateway exists
        template.has_resource("AWS::EC2::NatGateway", {})