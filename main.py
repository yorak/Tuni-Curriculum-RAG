import os
from rag.index_builder import build_index
from rag.rag_pipeline import answer_query

# GPT-Lab API
def call_llm(prompt: str):

    import requests

    headers = {
        "Authorization": os.environ["GPTLAB_API_KEY"],
        "Content-Type": "application/json"
    }

    url = "https://gptlab.rd.tuni.fi/students/ollama/v1/chat/completions"

    payload = {
        "model": "llama3.2:3b",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2
    }

    r = requests.post(url, headers=headers, json=payload)
    r.raise_for_status()

    return r.json()["choices"][0]["message"]["content"]


def main():

    print("Loading index...")

    index = build_index("data/kori_synthetic_60_25_12_v2.json")

    print("Index ready")

    query = input("\nAsk a curriculum question:\n")

    answer, nodes = answer_query(index, query, call_llm)

    print("\nAnswer:\n")
    print(answer)


if __name__ == "__main__":
    main()
