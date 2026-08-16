import json
import os
import re
from pathlib import Path
from typing import Any, Literal, TypedDict

import yaml
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from langchain_aws import ChatBedrockConverse
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from opentelemetry.instrumentation.langchain import LangchainInstrumentor
from pydantic import BaseModel, ConfigDict, Field


LangchainInstrumentor().instrument()

app = BedrockAgentCoreApp()
log = app.logger


class TicketInput(BaseModel):
    """Validated input contract for one support ticket."""

    model_config = ConfigDict(extra="forbid")

    ticket_id: str = Field(min_length=1, max_length=100)
    subject: str = Field(min_length=1, max_length=500)
    body: str = Field(min_length=1, max_length=10_000)


class TicketClassification(BaseModel):
    """Allowed classifier output contract."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["Incident", "Request", "Problem", "Change"]
    queue: Literal[
        "Technical Support",
        "IT Support",
        "Customer Service",
        "Product Support",
        "Billing and Payments",
    ]
    priority: Literal["high", "medium", "low"]
    reason: str = Field(min_length=1, max_length=500)


class TicketState(TypedDict, total=False):
    ticket: TicketInput
    classification: TicketClassification


def load_classifier_prompt() -> tuple[str, str]:
    prompt_path = Path(__file__).parent / "prompts" / "classifier.yaml"

    with prompt_path.open("r", encoding="utf-8") as prompt_file:
        prompt_config = yaml.safe_load(prompt_file)

    return (
        str(prompt_config["version"]),
        str(prompt_config["system_prompt"]),
    )


PROMPT_VERSION, CLASSIFIER_SYSTEM_PROMPT = load_classifier_prompt()

_llm: ChatBedrockConverse | None = None


def get_model() -> ChatBedrockConverse:
    """Create the Bedrock client once per AgentCore runtime process."""

    global _llm

    if _llm is None:
        _llm = ChatBedrockConverse(
            model=os.getenv(
                "BEDROCK_MODEL_ID",
                "amazon.nova-lite-v1:0",
            ),
            region_name=os.getenv("AWS_REGION", "us-east-1"),
            temperature=0,
            max_tokens=350,
            max_retries=2,
        )

    return _llm


def get_response_text(content: Any) -> str:
    """Extract text from either string or Bedrock content-block responses."""

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        text_blocks = []

        for block in content:
            if isinstance(block, dict) and isinstance(block.get("text"), str):
                text_blocks.append(block["text"])

        if text_blocks:
            return "".join(text_blocks)

    raise ValueError("The model response did not contain text")


def parse_classification(content: Any) -> TicketClassification:
    """Extract and validate the JSON returned by the model."""

    response_text = get_response_text(content).strip()

    response_text = re.sub(
        r"^```(?:json)?\s*",
        "",
        response_text,
        flags=re.IGNORECASE,
    )
    response_text = re.sub(r"\s*```$", "", response_text)

    json_start = response_text.find("{")
    json_end = response_text.rfind("}")

    if json_start == -1 or json_end == -1:
        raise ValueError("The model did not return a JSON object")

    json_text = response_text[json_start : json_end + 1]

    return TicketClassification.model_validate_json(json_text)


async def classifier_node(state: TicketState) -> TicketState:
    """Classify one ticket using Amazon Nova Lite through LangChain."""

    ticket = state["ticket"]

    ticket_content = json.dumps(
        {
            "subject": ticket.subject,
            "body": ticket.body,
        },
        ensure_ascii=False,
    )

    response = await get_model().ainvoke(
        [
            SystemMessage(content=CLASSIFIER_SYSTEM_PROMPT),
            HumanMessage(content=f"Classify this ticket:\n{ticket_content}"),
        ]
    )

    try:
        classification = parse_classification(response.content)
    except Exception as first_error:
        log.warning(
            "Invalid classifier output for ticket_id=%s; retrying once",
            ticket.ticket_id,
        )

        repair_response = await get_model().ainvoke(
            [
                SystemMessage(content=CLASSIFIER_SYSTEM_PROMPT),
                HumanMessage(
                    content=(
                        f"Classify this ticket:\n{ticket_content}\n\n"
                        "Your previous response failed schema validation. "
                        f"Validation error: {first_error}. "
                        "Return only a corrected JSON object."
                    )
                ),
            ]
        )

        classification = parse_classification(repair_response.content)

    log.info(
        "Classified ticket_id=%s queue=%s priority=%s",
        ticket.ticket_id,
        classification.queue,
        classification.priority,
    )

    return {"classification": classification}


graph_builder = StateGraph(TicketState)
graph_builder.add_node("classifier", classifier_node)
graph_builder.add_edge(START, "classifier")
graph_builder.add_edge("classifier", END)

ticket_graph = graph_builder.compile()


def parse_ticket(payload: dict[str, Any]) -> TicketInput:
    """Support production input and convenient local CLI input."""

    if isinstance(payload.get("ticket"), dict):
        ticket_data = payload["ticket"]
    elif all(key in payload for key in ("ticket_id", "subject", "body")):
        ticket_data = payload
    elif isinstance(payload.get("prompt"), str):
        ticket_data = {
            "ticket_id": payload.get("ticket_id", "manual-test"),
            "subject": payload.get("subject", "Manual test ticket"),
            "body": payload["prompt"],
        }
    else:
        raise ValueError(
            "Payload must contain a ticket object with "
            "ticket_id, subject, and body"
        )

    return TicketInput.model_validate(ticket_data)


@app.entrypoint
async def invoke(payload, context):
    ticket = parse_ticket(payload)

    log.info(
        "Starting classification ticket_id=%s prompt_version=%s",
        ticket.ticket_id,
        PROMPT_VERSION,
    )

    result = await ticket_graph.ainvoke({"ticket": ticket})
    classification = result["classification"]

    return {
        "ticket_id": ticket.ticket_id,
        **classification.model_dump(),
        "prompt_version": PROMPT_VERSION,
    }


if __name__ == "__main__":
    app.run()