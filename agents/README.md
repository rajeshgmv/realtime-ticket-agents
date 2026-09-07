# Ticket Support Agents

This folder contains the Amazon Bedrock AgentCore project that implements the ticket-support workflow.

## Contents

- [`ticketSupportAgents/`](ticketSupportAgents/) contains the AgentCore project configuration, deployment CDK application, and Python workflow.
- [`ticketSupportAgents/app/ticket_workflow/`](ticketSupportAgents/app/ticket_workflow/) contains the runtime entry point, model loader, prompts, schemas, classifier, ticket router, and knowledge-base search logic.

## Getting started

From `agents/ticketSupportAgents`:

```bash
agentcore dev
```

Invoke the local development server from another terminal:

```bash
agentcore invoke --dev "How can you help with this support ticket?"
```

Deploy the configured runtime after validating the AWS account, region, permissions, and OpenSearch settings:

```bash
agentcore deploy
```

See [`ticketSupportAgents/README.md`](ticketSupportAgents/README.md) for AgentCore prerequisites, configuration, and the full command reference. See the workflow's [`README.md`](ticketSupportAgents/app/ticket_workflow/README.md) for runtime-specific development notes.
