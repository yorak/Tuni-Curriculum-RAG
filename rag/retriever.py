
def create_retriever(index, top_k: int = 5):
    """
    Create a retriever from the vector index.
    """
    retriever = index.as_retriever(similarity_top_k=top_k)
    return retriever


def retrieve_naive(retriever, query: str):
    """
    Perform naive retrieval using the original query.
    """
    nodes = retriever.retrieve(query)
    return nodes
