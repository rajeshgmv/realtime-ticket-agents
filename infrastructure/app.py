import os

import aws_cdk as cdk

from infrastructure.infrastructure_stack import InfrastructureStack


app = cdk.App()

InfrastructureStack(
    app,
    "AgenticTicketSupportProd",
    env=cdk.Environment(
        account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
        region="us-east-1",
    ),
    tags={
        "Project": "agentic-ticket-support",
        "Environment": "production",
        "ManagedBy": "aws-cdk",
    },
)

app.synth()