from .schemas import RoutingDecision, TicketState

ROUTING_MAP = {
    "Technical Support": "technical-support-queue",
    "IT Support": "it-support-queue",
    "Customer Service": "customer-service-queue",
    "Product Support": "product-support-queue",
    "Billing and Payments": "billing-and-payments-queue",
}

DEFAULT_DESTINATION = "it-support-queue"


def route_ticket(state: TicketState) -> TicketState:
    classification = state["classification"]
    classified_queue = classification.queue

    destination = ROUTING_MAP.get(
        classified_queue,
        DEFAULT_DESTINATION,
    )

    routing = RoutingDecision(
        destination=destination,
        used_default_route=classification.queue not in ROUTING_MAP,
    )
    return {"routing": routing}
    