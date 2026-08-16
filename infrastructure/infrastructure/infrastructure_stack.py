from constructs import Construct

from aws_cdk import (
    CfnOutput,
    Duration,
    RemovalPolicy,
    Stack,
    aws_dynamodb as dynamodb,
    aws_s3 as s3,
    aws_sqs as sqs,
)


class InfrastructureStack(Stack):

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Stores raw tickets, knowledge documents, results and evaluation data.
        ticket_bucket = s3.Bucket(
            self,
            "TicketDataBucket",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            versioned=True,
            removal_policy=RemovalPolicy.RETAIN,
        )

        # Messages that repeatedly fail processing are moved here.
        dead_letter_queue = sqs.Queue(
            self,
            "TicketDeadLetterQueue",
            queue_name="agentic-ticket-processing-dlq-prod",
            encryption=sqs.QueueEncryption.SQS_MANAGED,
            enforce_ssl=True,
            retention_period=Duration.days(14),
            removal_policy=RemovalPolicy.RETAIN,
        )

        # Incoming tickets wait here before the processing Lambda handles them.
        ticket_queue = sqs.Queue(
            self,
            "TicketProcessingQueue",
            queue_name="agentic-ticket-processing-prod",
            encryption=sqs.QueueEncryption.SQS_MANAGED,
            enforce_ssl=True,
            visibility_timeout=Duration.minutes(15),
            retention_period=Duration.days(4),
            receive_message_wait_time=Duration.seconds(20),
            dead_letter_queue=sqs.DeadLetterQueue(
                queue=dead_letter_queue,
                max_receive_count=3,
            ),
            removal_policy=RemovalPolicy.RETAIN,
        )

        # Tracks each ticket from receipt through final agent decision.
        ticket_table = dynamodb.TableV2(
            self,
            "TicketStatusTable",
            table_name="agentic-ticket-status-prod",
            partition_key=dynamodb.Attribute(
                name="ticket_id",
                type=dynamodb.AttributeType.STRING,
            ),
            billing=dynamodb.Billing.on_demand(),
            point_in_time_recovery_specification=(
                dynamodb.PointInTimeRecoverySpecification(
                    point_in_time_recovery_enabled=True,
                )
            ),
            removal_policy=RemovalPolicy.RETAIN,
        )

        CfnOutput(
            self,
            "TicketBucketName",
            value=ticket_bucket.bucket_name,
            description="S3 bucket for ticket and knowledge-base data",
        )

        CfnOutput(
            self,
            "TicketQueueUrl",
            value=ticket_queue.queue_url,
            description="SQS queue for incoming tickets",
        )

        CfnOutput(
            self,
            "TicketQueueArn",
            value=ticket_queue.queue_arn,
            description="ARN of the ticket-processing queue",
        )

        CfnOutput(
            self,
            "DeadLetterQueueUrl",
            value=dead_letter_queue.queue_url,
            description="SQS dead-letter queue",
        )

        CfnOutput(
            self,
            "TicketTableName",
            value=ticket_table.table_name,
            description="DynamoDB ticket-status table",
        )