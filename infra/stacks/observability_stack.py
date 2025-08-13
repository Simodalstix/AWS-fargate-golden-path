from aws_cdk import (
    Stack,
    aws_elasticloadbalancingv2 as elbv2,
    aws_ecs as ecs,
    aws_logs as logs,
    CfnOutput,
    Tags,
)
from constructs import Construct
from constructs.dashboards import Dashboards
from constructs.alarms import Alarms
from constructs.log_metrics import LogMetrics
from typing import Optional


class ObservabilityStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        alb: elbv2.ApplicationLoadBalancer,
        ecs_service: ecs.FargateService,
        database,
        waf_web_acl,
        env_name: str,
        alarm_email: Optional[str] = None,
        webhook_url: Optional[str] = None,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.env_name = env_name
        self.alb = alb
        self.ecs_service = ecs_service
        self.database = database
        self.waf_web_acl = waf_web_acl

        # Get the application log group from the ECS service
        # We'll need to reference it from the compute stack
        self.log_group = logs.LogGroup.from_log_group_name(
            self,
            "ApplicationLogGroup",
            log_group_name=f"/ecs/golden-path-app-{env_name}",
        )

        # Create log metrics
        self.log_metrics = LogMetrics(
            self, "LogMetrics", env_name=env_name, log_group=self.log_group
        )

        # Create dashboards
        self.dashboards = Dashboards(
            self,
            "Dashboards",
            env_name=env_name,
            alb=alb,
            ecs_service=ecs_service,
            database=database,
            waf_web_acl=waf_web_acl,
        )

        # Create alarms
        self.alarms = Alarms(
            self,
            "Alarms",
            env_name=env_name,
            alb=alb,
            ecs_service=ecs_service,
            database=database,
            waf_web_acl=waf_web_acl,
            alarm_email=alarm_email,
            webhook_url=webhook_url,
        )

        # Add tags
        Tags.of(self.dashboards.dashboard).add("Environment", env_name)
        Tags.of(self.dashboards.dashboard).add("Project", "ECS-Fargate-Golden-Path")

        # Outputs
        CfnOutput(
            self,
            "DashboardURL",
            value=f"https://{self.region}.console.aws.amazon.com/cloudwatch/home?region={self.region}#dashboards:name={self.dashboards.dashboard.dashboard_name}",
            description="CloudWatch Dashboard URL",
            export_name=f"GoldenPath-{env_name}-DashboardURL",
        )

        CfnOutput(
            self,
            "AlarmTopicArn",
            value=self.alarms.alarm_topic.topic_arn,
            description="SNS Topic ARN for alarms",
            export_name=f"GoldenPath-{env_name}-AlarmTopicArn",
        )

        CfnOutput(
            self,
            "LogGroupName",
            value=self.log_group.log_group_name,
            description="Application log group name",
            export_name=f"GoldenPath-{env_name}-LogGroupName",
        )

        # Output useful CloudWatch Insights queries
        CfnOutput(
            self,
            "ErrorLogsQuery",
            value="fields @timestamp, requestId, path, status, errorType, latencyMs | filter ispresent(errorType) | sort @timestamp desc | limit 100",
            description="CloudWatch Insights query for error logs",
        )

        CfnOutput(
            self,
            "SlowRequestsQuery",
            value="fields @timestamp, requestId, path, status, latencyMs | filter latencyMs > 1000 | sort latencyMs desc | limit 100",
            description="CloudWatch Insights query for slow requests",
        )

        CfnOutput(
            self,
            "Status5xxQuery",
            value="fields @timestamp, requestId, path, status, errorType, latencyMs | filter status >= 500 | sort @timestamp desc | limit 100",
            description="CloudWatch Insights query for 5xx status codes",
        )

        CfnOutput(
            self,
            "RequestsByPathQuery",
            value="stats count() by path | sort count desc",
            description="CloudWatch Insights query for requests by path",
        )
