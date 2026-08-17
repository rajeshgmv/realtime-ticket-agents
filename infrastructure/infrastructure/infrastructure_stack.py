from constructs import Construct
from aws_cdk import (
    CfnOutput,
    CfnParameter,
    Duration,
    Fn,
    RemovalPolicy,
    Stack,
    aws_dynamodb as dynamodb,
    aws_iam as iam,
    aws_lambda as lambda_,
    aws_lambda_event_sources as lambda_event_sources,
    aws_s3 as s3,
    aws_sqs as sqs,
)
from pathlib import Path

class InfrastructureStack(Stack):

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        agent_runtime_arn = CfnParameter(
            self,
            "AgentRuntimeArn",
            type="String",
            description=(
                "Base ARN of the deployed ticket_workflow AgentCore runtime "
                "(without /runtime-endpoint/...)"
            ),
            allowed_pattern=(
                r"^arn:[^:]+:bedrock-agentcore:[a-z0-9-]+:[0-9]{12}:"
                r"runtime/[^/]+$"
            ),
            constraint_description=(
                "Must be a base AgentCore runtime ARN without an endpoint suffix"
            ),
        )
        agent_runtime_arn_value = agent_runtime_arn.value_as_string
        default_runtime_endpoint_arn = Fn.join(
            "",
            [agent_runtime_arn_value, "/runtime-endpoint/DEFAULT"],
        )
        lambda_code_path = (
            Path(__file__).parent
            / "lambda_functions"
            / "ticket_processor"
        )

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

        processor_lambda = lambda_.Function(
            self,
            "TicketProcessorFunction",
            function_name="agentic-ticket-processor-prod",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="handler.lambda_handler",
            code=lambda_.Code.from_asset(
                path=str(lambda_code_path),
            ),
            memory_size=512,
            timeout=Duration.minutes(2),
            environment={
                "AGENT_RUNTIME_ARN": agent_runtime_arn_value,
                "TICKET_TABLE_NAME": ticket_table.table_name,
            },
        )

        processor_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "dynamodb:PutItem",
                ],
                resources=[
                    ticket_table.table_arn,
                ],
            )
        )

        processor_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "bedrock-agentcore:InvokeAgentRuntime",
                ],
                resources=[
                    agent_runtime_arn_value,
                    default_runtime_endpoint_arn,
                ],
            )
        )
        processor_lambda.add_event_source(
            lambda_event_sources.SqsEventSource(
                ticket_queue,
                batch_size=1,
                report_batch_item_failures=True,
            )
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
