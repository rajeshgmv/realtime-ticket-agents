
from typing import Literal, TypedDict
from pydantic import BaseModel, ConfigDict, Field
import logging


log = logging.getLogger(__name__)

class TicketInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticket_id: str = Field(min_length=1, max_length=100)
    subject: str = Field(min_length=1, max_length=500)
    body: str = Field(min_length=1, max_length=10_000)


class TicketClassification(BaseModel):
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


class RoutingDecision(BaseModel):
    destination: str
    used_default_route: bool

class RAGResponse(BaseModel):
    response: str
    partial_answer: Literal["yes", "no"]
    human_routing_ind: Literal["yes", "no"]

class TicketState(TypedDict, total=False):
    ticket: TicketInput
    classification: TicketClassification
    routing: RoutingDecision
    rag_response: RAGResponse