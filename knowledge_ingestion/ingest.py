from pathlib import Path
import re
import boto3
from langchain_aws import BedrockEmbeddings
from langchain_core.documents import Document
from langchain_community.vectorstores import OpenSearchVectorSearch
from opensearchpy import AWSV4SignerAuth, OpenSearch, RequestsHttpConnection
from opensearchpy.exceptions import NotFoundError

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

cred = boto3.session.Session().get_credentials()

if cred is None:
    raise RuntimeError("AWS credentials not found.")

aoss_auth = AWSV4SignerAuth(
    cred,
    REGION,
    SERVICE,
)

opensearch_host = OPENSEARCH_URL.removeprefix("https://").rstrip("/")

aoss_client = OpenSearch(
    hosts=[{"host": opensearch_host, "port": 443}],
    http_auth=aoss_auth,
    use_ssl=True,
    verify_certs=True,
    connection_class=RequestsHttpConnection,
    timeout=300,
)

embeddings = BedrockEmbeddings(
    model_id = MODEL_ID,
    client = bedrock,
    model_kwargs={
        "dimensions": DIMENSIONS,
        "normalize": NORMALIZE
    }
)

kb_path = Path(__file__).parent / "data/knowledge-base/"


def extract_section(content: str, heading: str) -> str:
    pattern = (
        rf"^##[ \t]+{re.escape(heading)}[ \t]*\r?\n"
        rf"[ \t\r\n]*(.*?)(?=^##[ \t]+|\Z)"
    )

    match = re.search(
        pattern,
        content,
        flags=re.MULTILINE | re.DOTALL,
    )

    if not match:
        raise ValueError(f"Missing heading: {heading}")

    return match.group(1).strip().replace("\\n", "\n")

def parse_ticket(file_path) -> dict:
    content = Path(file_path).read_text(encoding="utf-8")

    ticket = {
        "document_id": extract_section(content, "Document ID"),
        "subject": extract_section(content, "Subject"),
        "ticket_description": extract_section(
            content, "Ticket Description"
        ),
        "resolution": extract_section(content, "Resolution"),
    }

    classification_text = extract_section(content, "Classification")

    for line in classification_text.splitlines():
        line = line.strip()

        if not line.startswith("- "):
            continue

        key, separator, value = line[2:].partition(":")

        if not separator:
            raise ValueError(
                f"Invalid classification line in {file_path}: {line}"
            )

        normalized_key = key.strip().lower().replace(" ", "_")
        ticket[normalized_key] = value.strip()
    required_fields = {
        "document_id",
        "subject",
        "ticket_description",
        "resolution",
        "type",
        "queue",
        "priority",
        "language",
    }
    missing_fields = required_fields - ticket.keys()
    if missing_fields:
        raise ValueError(
            f"Missing fields in {file_path}: {sorted(missing_fields)}"
        )
    return ticket

def create_embed_ticket(content: dict) -> str:
    embedding_text = (
             f"Subject: {content['subject']}\n\n"
            f"Ticket Description:\n{content['ticket_description']}\n\n"
             f"Resolution:\n{content['resolution']}"
        )
    return embedding_text

def create_metadata_ticket(content: dict) -> dict:
    metadata = {
        "document_id": content["document_id"],
        "type": content["type"],
        "queue": content["queue"],
        "priority": content["priority"],
        "language": content["language"],
    }
    return metadata

documents = []

for file in sorted(kb_path.glob("*.md")):
    print (f"Processing file : {file.name}")
    content = parse_ticket(file)
    embedding_text = create_embed_ticket(content)
    metadata = create_metadata_ticket(content)
    metadata["source"]= file.name

    document = Document(
        page_content=embedding_text,
        metadata=metadata,
    )
    documents.append(document)

if not documents:
    raise RuntimeError("No documents found in the knowledge base.")

nextgen_index_mapping = {
    "settings": {
        "index.knn": True,
    },
    "mappings": {
        "properties": {
            "vector_field": {
                "type": "knn_vector",
                "dimension": DIMENSIONS,
                "space_type": "cosinesimil",
                "method": {
                    "name": "hnsw",
                },
            },
            "text": {
                "type": "text",
            },
            "metadata": {
                "type": "object",
                "properties": {
                    "document_id": {"type": "keyword"},
                    "type": {"type": "keyword"},
                    "queue": {"type": "keyword"},
                    "priority": {"type": "keyword"},
                    "language": {"type": "keyword"},
                    "source": {"type": "keyword"},
                },
            },
        }
    },
}

try:
    aoss_client.indices.get(index=INDEX_NAME)
    print(f"Index already exists: {INDEX_NAME}")
except NotFoundError:
    aoss_client.indices.create(
        index=INDEX_NAME,
        body=nextgen_index_mapping,
    )
    print(f"Created NextGen index: {INDEX_NAME}")

print(f"Creating OpenSearchVectorSearch index: {INDEX_NAME} for {len(documents)} documents.")

vector_store = OpenSearchVectorSearch.from_documents(
    documents=documents,
    embedding=embeddings,
    opensearch_url=OPENSEARCH_URL,
    index_name=INDEX_NAME,
    http_auth=aoss_auth,
    connection_class=RequestsHttpConnection,
    engine="faiss",
    space_type="cosinesimil",
    use_ssl=True,
    verify_certs=True,
    timeout=300,
    bulk_size=100,
    http_compress=True,
)

print(f"successfully created OpenSearchVectorSearch index: {INDEX_NAME} for {len(documents)} documents. ")
