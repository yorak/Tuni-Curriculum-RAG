# Tuni-Curriculum-RAG

## AI-Powered Curriculum Explorer (Advanced RAG Prototype)
Overview

This project implements an AI-powered curriculum exploration system for Tampere University.
The system allows users to query curriculum data using natural language and retrieve grounded answers based on course, module, and staff information.

The prototype demonstrates an Advanced Retrieval-Augmented Generation (RAG) architecture that integrates:

semantic vector search

LLM-based query expansion

multi-query retrieval

grounded answer generation

The system is designed to explore the feasibility of AI-assisted academic information retrieval using structured curriculum data.

## Project Goals

The main objectives of this prototype are:

Build a semantic search system over university curriculum data

Implement a RAG pipeline that grounds LLM responses in retrieved evidence

Demonstrate how query expansion improves retrieval quality

Provide a simple interactive interface for curriculum exploration

Show a modular architecture suitable for further research and experimentation

## Data Source

The intended source for curriculum data is the TUNI SISU Kori API.

Swagger UI:

https://sisu.tuni.fi/kori/swagger-ui

During development, several endpoints required authentication or were rate-limited.
To allow continued experimentation, a schema-aligned synthetic dataset was created that mirrors the relevant Kori data structures.

The dataset includes:

60 courses

25 study modules

12 staff contacts

Entities include fields such as:

course codes

module relationships

topic keywords

learning outcomes

staff research areas

estimated student counts

This allows the system to answer questions such as:

Industry 4.0 student participation

operations research expertise

safety-critical software testing modules

The dataset is located at:

root kori_synthetic_data.json




## System Architecture

The system follows a modular Advanced RAG architecture.

User Query
    │
    ▼
Query Expansion (LLM)
    │
    ▼
Semantic Retrieval
(LlamaIndex Retriever → Qdrant Vector Store)
    │
    ▼
Evidence Aggregation
    │
    ▼
Grounded Answer Generation (LLM)
    │
    ▼
Final Answer


# Core Components
## Document Builder

Converts curriculum JSON data into structured documents for embedding.

rag/document_builder.py

Each entity type is converted into a textual representation:

Courses

Modules

Staff contacts

Example document structure:

ENTITY TYPE: COURSE
Course Code: COMP.SAFE.301
Course Name: Functional Safety and IEC 61508
Credits: 5
Keywords: functional safety, safety-critical systems

## Vector Index

Documents are embedded and stored in a Qdrant vector database.

rag/index_builder.py

Embedding model:

sentence-transformers/all-MiniLM-L6-v2

Benefits:

efficient semantic similarity search

scalable vector retrieval

lightweight local deployment

## Retrieval Layer

Semantic retrieval is implemented using LlamaIndex.

rag/retriever.py

The retriever finds the most relevant curriculum documents based on the user query.

## Query Expansion

To improve retrieval quality, the system expands the user query using an LLM.

rag/query_expansion.py

Example:

User query:

software testing for safety critical systems

Expanded queries:

safety critical software testing
verification of safety critical systems
IEC 61508 testing methods
software quality assurance for embedded systems

This improves recall by retrieving relevant curriculum content expressed using different terminology.

## RAG Pipeline

The complete RAG orchestration is implemented in:

rag/rag_pipeline.py

Pipeline steps:

Expand user query

Perform multi-query retrieval

Collect and deduplicate evidence

Build evidence context

Generate final grounded answer using the LLM

The final prompt instructs the model to:

only use retrieved evidence

avoid hallucinating courses or staff

reference specific curriculum entities when possible

## LLM Integration

The system uses GPT-Lab hosted Ollama models.

Example API:

https://gptlab.rd.tuni.fi/students/ollama/v1/chat/completions

Model used:

llama3.2:3b

The LLM is used for:

query expansion

final answer generation


# Running the Project

Install Dependencies
pip install -r requirements.txt
Run CLI Version
python main.py
Run Web Interface
streamlit run streamlit_app.py

## Docker Deployment

The project can also run in a containerized environment.

Build the image:

docker build -t curriculum-rag .

Run the container:

docker run -p 8501:8501 \
  -e GPTLAB_API_KEY="Bearer <your_key>" \
  curriculum-rag

Then open:

http://localhost:8501

# Limitations

The dataset is synthetic, though schema-aligned with Kori.

Student counts are estimates used for demonstration purposes.

Some API endpoints could not be accessed due to authentication constraints.


# Future Improvements

Live Kori API ingestion and caching

Hybrid retrieval (vector + keyword/BM25)

More rigorous retrieval evaluation

Real enrolment data instead of synthetic student estimates

Richer staff and organization metadata

Better UI with evidence highlighting and citations

Persistent vector database and improved deployment

Enrichment with thesis topics and programme information
