# rag/rag_pipeline.py

from rag.retriever import create_retriever, retrieve_naive
from rag.query_expansion import expand_query


def build_context_from_nodes(nodes, max_chars=5000):

    parts = []
    total_len = 0

    for i, node in enumerate(nodes, 1):

        node_text = node.text if hasattr(node, "text") else node.get_text()

        chunk = f"[Evidence {i}]\n{node_text}\n"

        if total_len + len(chunk) > max_chars:
            break

        parts.append(chunk)
        total_len += len(chunk)

    return "\n\n".join(parts)


def retrieve_advanced(index, query, call_llm):

    retriever = create_retriever(index)

    expanded_queries = expand_query(query, call_llm)

    seen = set()
    collected_nodes = []

    for q in expanded_queries:

        nodes = retrieve_naive(retriever, q)

        for node in nodes:

            node_text = node.text if hasattr(node, "text") else node.get_text()
            key = node_text[:200]

            if key not in seen:
                seen.add(key)
                collected_nodes.append(node)

    return collected_nodes[:8]


def generate_answer(query, nodes, call_llm):

    context = build_context_from_nodes(nodes)

    prompt = f"""
You are a curriculum assistant.

Answer the user's question using ONLY the evidence below.

Question:
{query}

Evidence:
{context}
"""

    return call_llm(prompt)


def answer_query(index, query, call_llm):

    nodes = retrieve_advanced(index, query, call_llm)

    answer = generate_answer(query, nodes, call_llm)

    return answer, nodes
