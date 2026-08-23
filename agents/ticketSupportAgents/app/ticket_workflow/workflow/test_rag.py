import asyncio

from .ragdatasearch import rag_resolution_node
from .schemas import TicketInput, TicketState


async def main() -> None:
    state: TicketState = {
        "ticket": TicketInput(
            ticket_id="TEST-001",
            subject="Billing amount discrepancies and delayed payment confirmations",

            body=(
             """The billed amounts on my account appear inconsistent, and confirmations 
                for my recent payments have been delayed. What information should I 
                provide so the billing team can investigate these transactions?"""
            )
        )
    }

    update = await rag_resolution_node(state)

    rag_response = update["rag_response"]
    print(rag_response.model_dump_json(indent=2))


if __name__ == "__main__":
    asyncio.run(main())