# rag/index_builder.py

import json
from qdrant_client import QdrantClient

from llama_index.core import StorageContext, VectorStoreIndex
from llama_index.vector_stores.qdrant import QdrantVectorStore
from llama_index.embeddings.huggingface import HuggingFaceEmbedding

from rag.document_builder import build_documents


def build_index(data_path: str):
    """
    Build a Qdrant-backed vector index from the curriculum dataset.
    """

    # Load dataset
    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Convert to LlamaIndex documents
    documents = build_documents(data)

    print(f"Documents created: {len(documents)}")

    # Embedding model
    embed_model = HuggingFaceEmbedding(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )

    # Qdrant client (local in-memory)
    qdrant_client = QdrantClient(location=":memory:")

    vector_store = QdrantVectorStore(
        client=qdrant_client,
        collection_name="curriculum_index",
    )

    storage_context = StorageContext.from_defaults(vector_store=vector_store)

    # Build index
    index = VectorStoreIndex.from_documents(
        documents,
        storage_context=storage_context,
        embed_model=embed_model,
    )

    print("Vector index created successfully.")

    return index
