import boto3
from langchain_aws import BedrockEmbeddings, ChatBedrockConverse
from langchain_community.vectorstores import OpenSearchVectorSearch
from opensearchpy import AWSV4SignerAuth, RequestsHttpConnection
import json
import os
import re
import yaml
from pathlib import Path
from typing import Any
from langchain_core.messages import HumanMessage, SystemMessage
from .schemas import RAGResponse, TicketClassification, TicketState
import logging

log = logging.getLogger(__name__)

def load_kb_prompt() -> tuple[str, str]:
    prompt_path = Path(__file__).parent / "prompts" / "kb-search.yaml"
    with prompt_path.open("r", encoding="utf-8") as prompt_file:
        prompt_config = yaml.safe_load(prompt_file)

    return (
        str(prompt_config["version"]),
        str(prompt_config["system_prompt"]),
    )

PROMPT_VERSION, KB_SYSTEM_PROMPT = load_kb_prompt()

MODEL_ID = "amazon.titan-embed-text-v2:0"
DIMENSIONS = 1024
NORMALIZE = True
REGION = "us-east-1"
SERVICE = "aoss"
OPENSEARCH_URL = (
    "https://jeo6ievbgbfag3swdplj.aoss.us-east-1.on.aws"
)
INDEX_NAME = "ticket-knowledge-v1"

bedrock = boto3.client(
    "bedrock-runtime",
    region_name=REGION,
)

credentials = boto3.Session().get_credentials()

if credentials is None:
    raise RuntimeError("AWS credentials not found.")

aoss_auth = AWSV4SignerAuth(
    credentials,
    REGION,
    SERVICE,
)

embeddings = BedrockEmbeddings(
    model_id=MODEL_ID,
    client=bedrock,
    model_kwargs={
        "dimensions": DIMENSIONS,
        "normalize": NORMALIZE,
    },
)

# Connect to the existing index. This does not ingest any documents.
vector_store = OpenSearchVectorSearch(
    opensearch_url=OPENSEARCH_URL,
    index_name=INDEX_NAME,
    embedding_function=embeddings,
    http_auth=aoss_auth,
    connection_class=RequestsHttpConnection,
    engine="faiss",
    space_type="cosinesimil",
    use_ssl=True,
    verify_certs=True,
    timeout=300,
    http_compress=True,
)

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



def rag_pipeline(query: str, top_k: int = 3):
    """Perform a RAG search using the OpenSearch vector store."""
    return vector_store.similarity_search(query=query, k=top_k) 


def extract_context_from_results(results: list[Any]) -> str:
    """Extract context from the RAG search results."""
    context_parts_text = []

    for i, doc in enumerate(results, start=1):
        context_parts_text.append(
            f"<document_{i}>Document ID: {doc.metadata.get('document_id', 'unknown')}\n {doc.page_content}</document_{i}>"
        )
    return "\n".join(context_parts_text)

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

def parse_rag_response(content: Any) -> RAGResponse:
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

    return RAGResponse.model_validate_json(json_text)

async def rag_resolution_node(state: TicketState) -> TicketState:
    """Classify one ticket using Amazon Nova Lite through LangChain."""

    ticket = state["ticket"]

    query = (
        f"Subject: {ticket.subject.strip()}\n\n"
        f"Ticket Description:\n{ticket.body.strip()}"
    )
    results = rag_pipeline(query=query, top_k=3)

    context = extract_context_from_results(results)
    response = await get_model().ainvoke(
        [
            SystemMessage(content=KB_SYSTEM_PROMPT),
            HumanMessage(content=f"""Current ticket:\n{query}\n\n
                                knowledge-base context for the ticket:\n{context}"""),
        ]
    )

    try:
        rag_response = parse_rag_response(response.content)
    except Exception as first_error:
        log.warning(
            "Invalid rag resolution output for ticket_id=%s; retrying once",
            ticket.ticket_id,
        )

        repair_response = await get_model().ainvoke(
            [
                SystemMessage(content=KB_SYSTEM_PROMPT),
                HumanMessage(
                    content=(
                        f"""Current ticket:\n{query}\n\n
                                knowledge-base context for the ticket:\n{context}"""
                        "Your previous response failed schema validation. "
                        f"Validation error: {first_error}. "
                        "Return only a corrected JSON object."
                    )
                ),
            ]
        )

        rag_response = parse_rag_response(repair_response.content)

    log.info(
        "Classified ticket_id=%s response=%s partial_answer=%s human_routing_ind=%s",
        ticket.ticket_id,
        rag_response.response,
        rag_response.partial_answer,
        rag_response.human_routing_ind,
    )

    return {"rag_response": rag_response}

