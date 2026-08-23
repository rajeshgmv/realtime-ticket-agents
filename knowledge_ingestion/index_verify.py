import boto3
from langchain_aws import BedrockEmbeddings
from langchain_community.vectorstores import OpenSearchVectorSearch
from opensearchpy import AWSV4SignerAuth, RequestsHttpConnection


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

query = """The billed amounts on my account appear inconsistent, and confirmations 
                for my recent payments have been delayed. What information should I 
                provide so the billing team can investigate these transactions?"""

results = vector_store.similarity_search(
    query=query,
    k=3,
)

print(f"Query: {query}")

for position, result in enumerate(results, start=1):
    print("-" * 80)
    print(f"Result: {position}")
    print(f"Document ID: {result.metadata['document_id']}")
    print(f"Type: {result.metadata['type']}")
    print(f"Queue: {result.metadata['queue']}")
    print(f"Priority: {result.metadata['priority']}")
    print(f"Language: {result.metadata['language']}")
    print(f"Source File: {result.metadata['source']}")
    print(f"Content:\n{result.page_content}")

print("-" * 80)
