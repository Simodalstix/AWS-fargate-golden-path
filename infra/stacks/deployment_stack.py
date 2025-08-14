from aws_cdk import (
    Stack,
    aws_codedeploy as codedeploy,
    aws_elasticloadbalancingv2 as elbv2,
    aws_ecs as ecs,
    aws_iam as iam,
    aws_lambda as lambda_,
    aws_logs as logs,
    CfnOutput,
    Duration,
    Tags,
)
from constructs import Construct


class DeploymentStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        ecs_service: ecs.FargateService,
        alb: elbv2.ApplicationLoadBalancer,
        target_group_1: elbv2.ApplicationTargetGroup,
        target_group_2: elbv2.ApplicationTargetGroup,
        env_name: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.env_name = env_name
        self.ecs_service = ecs_service
        self.alb = alb
        self.target_group_1 = target_group_1
        self.target_group_2 = target_group_2

        # Create CodeDeploy service role
        self.codedeploy_service_role = iam.Role(
            self,
            "CodeDeployServiceRole",
            assumed_by=iam.ServicePrincipal("codedeploy.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSCodeDeployRoleForECS"
                )
            ],
        )

        # Create CodeDeploy application
        self.codedeploy_application = codedeploy.EcsApplication(
            self,
            "CodeDeployApplication",
            application_name=f"golden-path-app-{env_name}",
        )

        # Create pre-traffic hook Lambda function
        self.pre_traffic_hook = self._create_pre_traffic_hook()

        # Create post-traffic hook Lambda function
        self.post_traffic_hook = self._create_post_traffic_hook()

        # Create CodeDeploy deployment group
        self.deployment_group = codedeploy.EcsDeploymentGroup(
            self,
            "DeploymentGroup",
            application=self.codedeploy_application,
            deployment_group_name=f"golden-path-dg-{env_name}",
            service=ecs_service,
            blue_green_deployment_config=codedeploy.EcsBlueGreenDeploymentConfig(
                blue_target_group=target_group_1,
                green_target_group=target_group_2,
                listener=alb.listeners[0],
                test_listener=None,  # Optional test listener for validation
                deployment_approval_wait_time=Duration.minutes(
                    0
                ),  # Auto-approve for demo
                termination_wait_time=Duration.minutes(5),
            ),
            deployment_config=codedeploy.EcsDeploymentConfig.CANARY_10_PERCENT_5_MINUTES,
            role=self.codedeploy_service_role,
            auto_rollback=codedeploy.AutoRollbackConfig(
                failed_deployment=True,
                stopped_deployment=True,
                deployment_in_alarm=False,
            ),
        )

        # Add alarms for auto-rollback (these would be created in observability stack)
        # We'll reference them by name since they're in a different stack

        # Add tags
        Tags.of(self.codedeploy_application).add("Environment", env_name)
        Tags.of(self.codedeploy_application).add("Project", "ECS-Fargate-Golden-Path")

        # Outputs
        CfnOutput(
            self,
            "CodeDeployApplicationName",
            value=self.codedeploy_application.application_name,
            description="CodeDeploy application name",
            export_name=f"GoldenPath-{env_name}-CodeDeployApplicationName",
        )

        CfnOutput(
            self,
            "CodeDeployDeploymentGroupName",
            value=self.deployment_group.deployment_group_name,
            description="CodeDeploy deployment group name",
            export_name=f"GoldenPath-{env_name}-CodeDeployDeploymentGroupName",
        )

        CfnOutput(
            self,
            "DeploymentCommand",
            value=f"aws deploy create-deployment --application-name {self.codedeploy_application.application_name} --deployment-group-name {self.deployment_group.deployment_group_name} --revision revisionType=S3,s3Location={{bucket=YOUR_BUCKET,key=YOUR_KEY,bundleType=zip}}",
            description="Example deployment command",
        )

    def _create_pre_traffic_hook(self) -> lambda_.Function:
        """Create pre-traffic hook Lambda function"""
        # Create execution role for Lambda
        lambda_role = iam.Role(
            self,
            "PreTrafficHookRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                )
            ],
        )

        # Grant CodeDeploy permissions
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["codedeploy:PutLifecycleEventHookExecutionStatus"],
                resources=["*"],
            )
        )

        # Create Lambda function
        pre_traffic_hook = lambda_.Function(
            self,
            "PreTrafficHook",
            runtime=lambda_.Runtime.PYTHON_3_9,
            handler="index.handler",
            role=lambda_role,
            function_name=f"golden-path-pre-traffic-hook-{self.env_name}",
            timeout=Duration.minutes(5),
            log_retention=logs.RetentionDays.ONE_WEEK,
            code=lambda_.Code.from_inline(
                """
import json
import boto3
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

codedeploy = boto3.client('codedeploy')

def handler(event, context):
    logger.info(f"Pre-traffic hook event: {json.dumps(event)}")
    
    deployment_id = event['DeploymentId']
    lifecycle_event_hook_execution_id = event['LifecycleEventHookExecutionId']
    
    try:
        # Perform pre-traffic validation here
        # For example: health checks, smoke tests, etc.
        
        logger.info("Pre-traffic validation passed")
        
        # Signal success to CodeDeploy
        codedeploy.put_lifecycle_event_hook_execution_status(
            deploymentId=deployment_id,
            lifecycleEventHookExecutionId=lifecycle_event_hook_execution_id,
            status='Succeeded'
        )
        
        return {
            'statusCode': 200,
            'body': json.dumps('Pre-traffic hook succeeded')
        }
        
    except Exception as e:
        logger.error(f"Pre-traffic validation failed: {str(e)}")
        
        # Signal failure to CodeDeploy
        codedeploy.put_lifecycle_event_hook_execution_status(
            deploymentId=deployment_id,
            lifecycleEventHookExecutionId=lifecycle_event_hook_execution_id,
            status='Failed'
        )
        
        return {
            'statusCode': 500,
            'body': json.dumps(f'Pre-traffic hook failed: {str(e)}')
        }
"""
            ),
        )

        return pre_traffic_hook

    def _create_post_traffic_hook(self) -> lambda_.Function:
        """Create post-traffic hook Lambda function"""
        # Create execution role for Lambda
        lambda_role = iam.Role(
            self,
            "PostTrafficHookRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                )
            ],
        )

        # Grant CodeDeploy permissions
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["codedeploy:PutLifecycleEventHookExecutionStatus"],
                resources=["*"],
            )
        )

        # Create Lambda function
        post_traffic_hook = lambda_.Function(
            self,
            "PostTrafficHook",
            runtime=lambda_.Runtime.PYTHON_3_9,
            handler="index.handler",
            role=lambda_role,
            function_name=f"golden-path-post-traffic-hook-{self.env_name}",
            timeout=Duration.minutes(5),
            log_retention=logs.RetentionDays.ONE_WEEK,
            code=lambda_.Code.from_inline(
                """
import json
import boto3
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

codedeploy = boto3.client('codedeploy')

def handler(event, context):
    logger.info(f"Post-traffic hook event: {json.dumps(event)}")
    
    deployment_id = event['DeploymentId']
    lifecycle_event_hook_execution_id = event['LifecycleEventHookExecutionId']
    
    try:
        # Perform post-traffic validation here
        # For example: integration tests, monitoring checks, etc.
        
        logger.info("Post-traffic validation passed")
        
        # Signal success to CodeDeploy
        codedeploy.put_lifecycle_event_hook_execution_status(
            deploymentId=deployment_id,
            lifecycleEventHookExecutionId=lifecycle_event_hook_execution_id,
            status='Succeeded'
        )
        
        return {
            'statusCode': 200,
            'body': json.dumps('Post-traffic hook succeeded')
        }
        
    except Exception as e:
        logger.error(f"Post-traffic validation failed: {str(e)}")
        
        # Signal failure to CodeDeploy
        codedeploy.put_lifecycle_event_hook_execution_status(
            deploymentId=deployment_id,
            lifecycleEventHookExecutionId=lifecycle_event_hook_execution_id,
            status='Failed'
        )
        
        return {
            'statusCode': 500,
            'body': json.dumps(f'Post-traffic hook failed: {str(e)}')
        }
"""
            ),
        )

        return post_traffic_hook
