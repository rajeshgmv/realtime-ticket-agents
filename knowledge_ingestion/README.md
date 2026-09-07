# Knowledge Ingestion

This component converts the sample support documents in `data/knowledge-base` into vector embeddings and loads them into an Amazon OpenSearch Serverless index. It also includes a script for running a similarity-search check against the populated index.

## Contents

- `data/knowledge-base/` contains the Markdown support documents used as source data.
- `ingest.py` parses each document, creates Amazon Titan embeddings through Amazon Bedrock, creates the index when necessary, and uploads the documents.
- `index_verify.py` runs a sample similarity query against the existing index and prints the top matches.
- `requirements.txt` lists the Python dependencies.

## Prerequisites

- Python 3
- AWS credentials available through the standard AWS credential chain
- Permission to invoke the configured Amazon Bedrock embedding model
- Network and IAM access to the configured OpenSearch Serverless collection
- The OpenSearch data-access policy required to create and write to the index

The current scripts are configured for `us-east-1`, the `amazon.titan-embed-text-v2:0` model, 1,024-dimensional vectors, and the `ticket-knowledge-v1` index. Review the `OPENSEARCH_URL`, region, index name, and model settings in both scripts before running them in another environment.

## Setup

From this folder:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Ingest the documents

```bash
python ingest.py
```

Every source Markdown file must contain the headings expected by `ingest.py`, including `Document ID`, `Subject`, `Ticket Description`, `Resolution`, and `Classification`. The classification section must provide type, queue, priority, and language values.

## Verify the index

After ingestion completes:

```bash
python index_verify.py
```

The script embeds its sample query, retrieves the three closest documents, and prints their metadata and content. Change the query in `index_verify.py` to test other support scenarios.
