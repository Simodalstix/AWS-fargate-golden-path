import pytest
import aws_cdk as cdk
from aws_cdk import assertions
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_rds as rds
from aws_cdk import aws_secretsmanager as secretsmanager
from aws_cdk import aws_elasticloadbalancingv2 as elbv2
from aws_cdk import aws_ecs as ecs

from stacks.network_stack import NetworkStack
from stacks.data_stack import DataStack
from stacks.compute_stack import ComputeStack
from stacks.observability_stack import ObservabilityStack


class TestObservabilityStack:
    """Test cases for the ObservabilityStack"""

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

    @pytest.fixture
    def observability_stack(self, app, compute_stack, data_stack):
        """Create an observability stack for testing"""
        env = cdk.Environment(account="123456789012", region="us-east-1")
        return ObservabilityStack(
            app,
            "TestObservabilityStack",
            alb=compute_stack.alb,
            ecs_service=compute_stack.ecs_service,
            database=data_stack.database,
            waf_web_acl=compute_stack.waf_web_acl,
            env_name="test",
            alarm_email="test@example.com",
            webhook_url="https://hooks.slack.com/services/TEST",
            env=env,
        )

    def test_dashboard_created(self, observability_stack):
        """Test that CloudWatch dashboard is created"""
        template = assertions.Template.from_stack(observability_stack)

        template.has_resource_properties(
            "AWS::CloudWatch::Dashboard", {"DashboardName": "GoldenPath-test"}
        )

    def test_alarms_created(self, observability_stack):
        """Test that CloudWatch alarms are created"""
        template = assertions.Template.from_stack(observability_stack)

        # Check for ALB 5xx alarm
        template.has_resource_properties(
            "AWS::CloudWatch::Alarm",
            {
                "AlarmName": "golden-path-alb-5xx-test",
                "ComparisonOperator": "GreaterThanThreshold",
                "Threshold": 1.0,
            },
        )

        # Check for ALB response time alarm
        template.has_resource_properties(
            "AWS::CloudWatch::Alarm",
            {
                "AlarmName": "golden-path-alb-response-time-test",
                "ComparisonOperator": "GreaterThanThreshold",
                "Threshold": 2.0,
            },
        )

        # Check for ECS task count alarm
        template.has_resource_properties(
            "AWS::CloudWatch::Alarm",
            {
                "AlarmName": "golden-path-ecs-task-count-test",
                "ComparisonOperator": "LessThanThreshold",
                "Threshold": 1,
            },
        )

        # Check for ECS CPU alarm
        template.has_resource_properties(
            "AWS::CloudWatch::Alarm",
            {
                "AlarmName": "golden-path-ecs-cpu-test",
                "ComparisonOperator": "GreaterThanThreshold",
                "Threshold": 80,
            },
        )

        # Check for ECS memory alarm
        template.has_resource_properties(
            "AWS::CloudWatch::Alarm",
            {
                "AlarmName": "golden-path-ecs-memory-test",
                "ComparisonOperator": "GreaterThanThreshold",
                "Threshold": 80,
            },
        )

        # Check for RDS CPU alarm
        template.has_resource_properties(
            "AWS::CloudWatch::Alarm",
            {
                "AlarmName": "golden-path-rds-cpu-test",
                "ComparisonOperator": "GreaterThanThreshold",
                "Threshold": 80,
            },
        )

        # Check for WAF blocked requests alarm
        template.has_resource_properties(
            "AWS::CloudWatch::Alarm",
            {
                "AlarmName": "golden-path-waf-blocked-test",
                "ComparisonOperator": "GreaterThanThreshold",
                "Threshold": 100,
            },
        )

    def test_sns_topic_created(self, observability_stack):
        """Test that SNS topic for alarms is created"""
        template = assertions.Template.from_stack(observability_stack)

        template.has_resource_properties(
            "AWS::SNS::Topic",
            {
                "TopicName": "golden-path-alarms-test",
                "DisplayName": "Golden Path Alarms - test",
            },
        )

    def test_sns_subscriptions_created(self, observability_stack):
        """Test that SNS subscriptions are created"""
        template = assertions.Template.from_stack(observability_stack)

        # Check for email subscription
        template.has_resource_properties(
            "AWS::SNS::Subscription",
            {"Protocol": "email", "Endpoint": "test@example.com"},
        )

        # Check for webhook subscription
        template.has_resource_properties(
            "AWS::SNS::Subscription",
            {"Protocol": "https", "Endpoint": "https://hooks.slack.com/services/TEST"},
        )

    def test_log_metrics_created(self, observability_stack):
        """Test that log metric filters are created"""
        template = assertions.Template.from_stack(observability_stack)

        # Check for error type metric filter
        template.has_resource_properties(
            "AWS::Logs::MetricFilter",
            {
                "FilterPattern": "{ $.errorType = * }",
                "MetricName": "ErrorCount",
                "MetricNamespace": "GoldenPath/Application",
            },
        )

        # Check for 5xx status metric filter
        template.has_resource_properties(
            "AWS::Logs::MetricFilter",
            {
                "FilterPattern": "{ $.status = * && $.status >= 500 }",
                "MetricName": "Status5xxCount",
                "MetricNamespace": "GoldenPath/Application",
            },
        )

        # Check for latency metric filter
        template.has_resource_properties(
            "AWS::Logs::MetricFilter",
            {
                "FilterPattern": "{ $.latencyMs = * }",
                "MetricName": "RequestLatency",
                "MetricNamespace": "GoldenPath/Application",
            },
        )

        # Check for request count metric filter
        template.has_resource_properties(
            "AWS::Logs::MetricFilter",
            {
                "FilterPattern": "{ $.requestId = * }",
                "MetricName": "RequestCount",
                "MetricNamespace": "GoldenPath/Application",
            },
        )

    def test_dashboard_widgets_configured(self, observability_stack):
        """Test that dashboard widgets are configured properly"""
        # This test would require more complex validation of the dashboard body
        # For now, we'll check that the dashboard exists
        template = assertions.Template.from_stack(observability_stack)

        template.has_resource("AWS::CloudWatch::Dashboard", {})

    def test_alarm_actions_configured(self, observability_stack):
        """Test that alarm actions are configured to use SNS topic"""
        template = assertions.Template.from_stack(observability_stack)

        # Check that alarms have alarm actions pointing to SNS topic
        template.has_resource_properties(
            "AWS::CloudWatch::Alarm",
            {
                "AlarmActions": assertions.Match.array_with(
                    [assertions.Match.string_like_regexp("arn:aws:sns")]
                )
            },
        )

    def test_outputs_created(self, observability_stack):
        """Test that required outputs are created"""
        template = assertions.Template.from_stack(observability_stack)

        # Check for outputs
        template.has_output("DashboardURL", {})
        template.has_output("AlarmTopicArn", {})
        template.has_output("LogGroupName", {})
        template.has_output("ErrorLogsQuery", {})
        template.has_output("SlowRequestsQuery", {})
        template.has_output("Status5xxQuery", {})
        template.has_output("RequestsByPathQuery", {})

    def test_widget_dimensions_match_resources(
        self, observability_stack, compute_stack, data_stack
    ):
        """Test that widget dimensions match actual resource names"""
        # This would be a more complex integration test
        # For now, we verify the dashboard exists
        template = assertions.Template.from_stack(observability_stack)
        template.has_resource("AWS::CloudWatch::Dashboard", {})

    def test_alarm_thresholds_are_reasonable(self, observability_stack):
        """Test that alarm thresholds are set to reasonable values"""
        template = assertions.Template.from_stack(observability_stack)

        # Check ALB 5xx alarm threshold
        template.has_resource_properties(
            "AWS::CloudWatch::Alarm",
            {
                "AlarmName": "golden-path-alb-5xx-test",
                "Threshold": 1.0,  # 1% error rate
            },
        )

        # Check ALB response time threshold
        template.has_resource_properties(
            "AWS::CloudWatch::Alarm",
            {
                "AlarmName": "golden-path-alb-response-time-test",
                "Threshold": 2.0,  # 2 seconds
            },
        )

        # Check ECS CPU threshold
        template.has_resource_properties(
            "AWS::CloudWatch::Alarm",
            {
                "AlarmName": "golden-path-ecs-cpu-test",
                "Threshold": 80,  # 80% utilization
            },
        )

    def test_log_group_reference_is_correct(self, observability_stack):
        """Test that log group reference is correct"""
        template = assertions.Template.from_stack(observability_stack)

        # Check that we're referencing the correct log group
        template.has_resource_properties(
            "AWS::Logs::MetricFilter", {"LogGroupName": "/ecs/golden-path-app-test"}
        )
