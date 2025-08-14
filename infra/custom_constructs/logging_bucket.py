from aws_cdk import aws_s3 as s3, aws_kms as kms, RemovalPolicy, Duration
from constructs import Construct
import hashlib


class LoggingBucket(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        env_name: str,
        kms_key: kms.Key,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.bucket = s3.Bucket(
            self,
            "Bucket",
            bucket_name=f"golden-alb-logs-{env_name}-{hashlib.md5(self.node.addr.encode()).hexdigest()[:8]}",
            encryption=s3.BucketEncryption.KMS,
            encryption_key=kms_key,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            versioned=True,
            removal_policy=RemovalPolicy.DESTROY,  # Set to RETAIN for production
            auto_delete_objects=True,  # Set to False for production
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="ALBLogsLifecycle",
                    enabled=True,
                    transitions=[
                        s3.Transition(
                            storage_class=s3.StorageClass.INFREQUENT_ACCESS,
                            transition_after=Duration.days(30),
                        ),
                        s3.Transition(
                            storage_class=s3.StorageClass.GLACIER,
                            transition_after=Duration.days(90),
                        ),
                        s3.Transition(
                            storage_class=s3.StorageClass.DEEP_ARCHIVE,
                            transition_after=Duration.days(365),
                        ),
                    ],
                    expiration=Duration.days(2555),  # 7 years
                )
            ],
        )

        # Grant ALB service access to write logs
        # The ALB service account varies by region
        region_to_alb_account = {
            "us-east-1": "127311923021",
            "us-east-2": "033677994240",
            "us-west-1": "027434742980",
            "us-west-2": "797873946194",
            "eu-west-1": "156460612806",
            "eu-west-2": "652711504416",
            "eu-west-3": "009996457667",
            "eu-central-1": "054676820928",
            "ap-southeast-1": "114774131450",
            "ap-southeast-2": "783225319266",
            "ap-northeast-1": "582318560864",
            "ap-northeast-2": "600734575887",
            "ap-south-1": "718504428378",
            "sa-east-1": "507241528517",
        }

        # Get the current region
        region = self.node.try_get_context("@aws-cdk/core:target-partitions") or "aws"

        # For now, we'll use a more generic approach that works across regions
        from aws_cdk import aws_iam as iam

        self.bucket.add_to_resource_policy(
            iam.PolicyStatement(
                sid="ALBLogDelivery",
                effect=iam.Effect.ALLOW,
                principals=[iam.ServicePrincipal("elasticloadbalancing.amazonaws.com")],
                actions=["s3:PutObject"],
                resources=[f"{self.bucket.bucket_arn}/AWSLogs/*"],
            )
        )

        self.bucket.add_to_resource_policy(
            iam.PolicyStatement(
                sid="ALBLogDeliveryWrite",
                effect=iam.Effect.ALLOW,
                principals=[iam.ServicePrincipal("elasticloadbalancing.amazonaws.com")],
                actions=["s3:PutObject"],
                resources=[f"{self.bucket.bucket_arn}/*"],
                conditions={
                    "StringEquals": {"s3:x-amz-acl": "bucket-owner-full-control"}
                },
            )
        )

        self.bucket.add_to_resource_policy(
            iam.PolicyStatement(
                sid="ALBLogDeliveryAclCheck",
                effect=iam.Effect.ALLOW,
                principals=[iam.ServicePrincipal("elasticloadbalancing.amazonaws.com")],
                actions=["s3:GetBucketAcl"],
                resources=[self.bucket.bucket_arn],
            )
        )
