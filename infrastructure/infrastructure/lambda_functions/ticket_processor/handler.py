import json
import os
import uuid
from datetime import UTC, datetime
import boto3


AGENT_RUNTIME_ARN = os.environ["AGENT_RUNTIME_ARN"]
TICKET_TABLE_NAME = os.environ["TICKET_TABLE_NAME"]

agentcore = boto3.client("bedrock-agentcore")
ticket_table = boto3.resource("dynamodb").Table(TICKET_TABLE_NAME)


def lambda_handler(event, context):
    failures = []

    for record in event["Records"]:
        try:
            ticket = json.loads(record["body"])

            required_fields = {"ticket_id", "subject", "body"}
            missing_fields = required_fields - ticket.keys()

            if missing_fields:
                raise ValueError(
                    f"Missing fields: {sorted(missing_fields)}"
                )

            response = agentcore.invoke_agent_runtime(
                agentRuntimeArn=AGENT_RUNTIME_ARN,
                qualifier="DEFAULT",
                runtimeSessionId=str(uuid.uuid4()),
                contentType="application/json",
                accept="application/json",
                payload=json.dumps(ticket).encode("utf-8"),
            )

            result = json.loads(
                response["response"].read().decode("utf-8")
            )

            # Handle an AgentCore response wrapped in {"result": ...}.
            if "result" in result:
                result = result["result"]

            if isinstance(result, str):
                result = json.loads(result)

            timestamp = datetime.now(UTC).isoformat()

            ticket_table.put_item(
                Item={
                    "ticket_id": ticket["ticket_id"],
                    "status": "Queued",
                    "type": result["type"],
                    "queue": result["queue"],
                    "priority": result["priority"],
                    "reason": result["reason"],
                    "routing":result["routing"],
                    "prompt_version": result["prompt_version"],
                    "created_at": timestamp,
                    "updated_at": timestamp,
                }
            )

        except Exception as error:
            print(
                f"Failed to process message "
                f"{record['messageId']}: {error}"
            )

            failures.append(
                {"itemIdentifier": record["messageId"]}
            )

    return {"batchItemFailures": failures}