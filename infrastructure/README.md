
# Ticket Processing Infrastructure

This AWS CDK project provisions the event-driven resources that receive tickets and invoke the deployed Amazon Bedrock AgentCore ticket workflow.

## Resources

The `AgenticTicketSupportProd` stack creates:

- An encrypted, versioned S3 bucket for ticket and knowledge-base data
- An encrypted SQS queue for incoming tickets
- An encrypted dead-letter queue for messages that fail three processing attempts
- An on-demand DynamoDB table for ticket-processing status
- A Python 3.12 Lambda function that consumes one ticket at a time and invokes the AgentCore runtime
- IAM permissions for the Lambda function to invoke the runtime and write ticket results

The queues, table, and bucket use retain removal policies. Deleting the CloudFormation stack does not automatically delete those retained resources.

## Setup

From this folder, create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Configure AWS credentials, bootstrap the target account if needed, and synthesize the template:

```bash
cdk bootstrap
cdk synth --parameters AgentRuntimeArn=<agentcore-runtime-arn>
```

`AgentRuntimeArn` must be the base deployed AgentCore runtime ARN, without the `/runtime-endpoint/DEFAULT` suffix.

## Deploy

Review the generated changes before deployment:

```bash
cdk diff --parameters AgentRuntimeArn=<agentcore-runtime-arn>
```

Deploy the stack:

```bash
cdk deploy --parameters AgentRuntimeArn=<agentcore-runtime-arn>
```

The stack targets `us-east-1` and uses the AWS account selected by the active CDK credentials.

## Test

Install development requirements and run the unit tests:

```bash
python -m pip install -r requirements-dev.txt
pytest
```

## Useful commands

| Command | Description |
| --- | --- |
| `cdk ls` | List stacks in the application. |
| `cdk synth` | Generate the CloudFormation template. |
| `cdk diff` | Compare the local stack with the deployed stack. |
| `cdk deploy` | Deploy the stack to AWS. |
