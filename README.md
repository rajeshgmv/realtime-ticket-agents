# Realtime Ticket Agents

This repository contains an AWS-based ticket-support system that classifies incoming support requests, searches a vector knowledge base for relevant resolutions, and routes each ticket through an Amazon Bedrock AgentCore workflow.

## Project structure

| Folder | Purpose |
| --- | --- |
| [`agents/`](agents/) | AgentCore configuration and the LangGraph ticket-support workflow. |
| [`infrastructure/`](infrastructure/) | AWS CDK stack for the ticket queue, processing Lambda, status table, and supporting storage. |
| [`knowledge_ingestion/`](knowledge_ingestion/) | Scripts and sample documents used to build and verify the OpenSearch Serverless vector index. |

Each top-level folder has its own README with component-specific setup and usage instructions.

## System flow

1. A ticket is sent to the Amazon SQS processing queue.
2. The ticket-processor Lambda invokes the deployed AgentCore runtime.
3. The workflow classifies and routes the ticket and searches the OpenSearch knowledge index when supporting context is needed.
4. The processing result is stored in the DynamoDB ticket-status table.
5. Messages that repeatedly fail are moved to the dead-letter queue.

## Prerequisites

- An AWS account with credentials configured locally
- Python 3.13 for the agent workflow
- Python 3 and AWS CDK for the infrastructure project
- Node.js 20 or later and the AgentCore CLI for local agent development and deployment
- Access to Amazon Bedrock and Amazon OpenSearch Serverless in `us-east-1`

## Suggested setup order

1. Follow [`knowledge_ingestion/README.md`](knowledge_ingestion/README.md) to prepare the vector knowledge index.
2. Follow [`agents/README.md`](agents/README.md) to configure, run, and deploy the ticket workflow.
3. Follow [`infrastructure/README.md`](infrastructure/README.md) to deploy the event-driven processing resources with the AgentCore runtime ARN.

Review resource names, regions, endpoints, and IAM permissions before deploying to an AWS account.
