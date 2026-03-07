# rag/query_expansion.py

import ast
import re


def _parse_expansion_output(raw_text: str) -> list[str]:
    """
    Parse LLM output into a list of search phrases.
    """

    if not raw_text:
        return []

    text = raw_text.strip()

    try:
        parsed = ast.literal_eval(text)
        if isinstance(parsed, list):
            return [str(x).strip() for x in parsed if str(x).strip()]
    except Exception:
        pass

    lines = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        line = re.sub(r"^[-*•]\s*", "", line)
        line = re.sub(r"^\d+[\).\s-]*", "", line)
        line = line.strip(" \"'")

        if line:
            lines.append(line)

    if lines:
        return lines

    parts = [p.strip(" \"'") for p in text.split(",") if p.strip()]
    return parts


def expand_query(query: str, call_llm) -> list[str]:
    """
    Expand the user query into related academic phrases.
    """

    prompt = f"""
You are helping an advanced RAG system retrieve university curriculum content.

Task:
Expand the user's query into short academic search phrases.

Rules:
Return 6-8 phrases.
Return ONLY a Python list.

Query:
{query}
"""

    raw = call_llm(prompt)

    expanded = _parse_expansion_output(raw)

    final_queries = [query]

    for item in expanded:
        if item and item.lower() != query.lower():
            final_queries.append(item)

    return final_queries[:8]
