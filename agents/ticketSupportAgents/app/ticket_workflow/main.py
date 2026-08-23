from typing import Any
from unittest import result
import yaml


from bedrock_agentcore.runtime import BedrockAgentCoreApp
from langgraph.graph import END, START, StateGraph
from opentelemetry.instrumentation.langchain import LangchainInstrumentor

from workflow.ticketrouter import route_ticket
from workflow.classifier import (
    PROMPT_VERSION as CLASSIFIER_PROMPT_VERSION,
    classifier_node,
)
from workflow.ragdatasearch import (
    PROMPT_VERSION as KB_PROMPT_VERSION,
    rag_resolution_node,
)
from workflow.schemas import TicketInput, TicketState


LangchainInstrumentor().instrument()

app = BedrockAgentCoreApp()
log = app.logger


graph_builder = StateGraph(TicketState)

graph_builder.add_node("classifier", classifier_node)
graph_builder.add_node("router", route_ticket)
graph_builder.add_node("rag_resolver", rag_resolution_node)

graph_builder.add_edge(START, "classifier")
graph_builder.add_edge("classifier","router")
graph_builder.add_edge("router", "rag_resolver")
graph_builder.add_edge("rag_resolver", END)

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
        "Starting classification ticket_id=%s ",
        ticket.ticket_id,
    )

    result = await ticket_graph.ainvoke({"ticket": ticket})
    classification = result["classification"]
    routing = result["routing"]
    rag_response = result["rag_response"]


    return {
        "ticket_id": ticket.ticket_id,
        **classification.model_dump(),
        "routing": routing.model_dump(),
        "rag_response": rag_response.model_dump(),
        "prompt_versions": {
            "classifier": CLASSIFIER_PROMPT_VERSION,
            "kb_search": KB_PROMPT_VERSION,
        },
    }


if __name__ == "__main__":
    app.run()
