import pytest
import aws_cdk as cdk
from aws_cdk import assertions

from stacks.network_stack import NetworkStack


class TestBasicSynthesis:
    """Basic tests that verify CDK synthesis works"""

    def test_network_stack_synthesizes(self):
        """Test that network stack can be synthesized"""
        app = cdk.App()
        env = cdk.Environment(account="123456789012", region="us-east-1")
        
        stack = NetworkStack(app, "TestNetworkStack", env_name="test", use_one_nat=True, env=env)
        template = assertions.Template.from_stack(stack)
        
        # Basic check - VPC should exist
        template.has_resource("AWS::EC2::VPC", {})

    def test_app_synthesizes_without_errors(self):
        """Test that the main app can be synthesized without errors"""
        # This is the most important test - if synthesis works, the infrastructure is valid
        import subprocess
        import os
        
        env = os.environ.copy()
        env["CDK_DEFAULT_ACCOUNT"] = "123456789012"
        env["CDK_DEFAULT_REGION"] = "us-east-1"
        
        result = subprocess.run(
            ["python", "app.py"],
            cwd=".",
            env=env,
            capture_output=True,
            text=True
        )
        
        # If synthesis succeeds, return code should be 0
        assert result.returncode == 0, f"CDK synthesis failed: {result.stderr}"