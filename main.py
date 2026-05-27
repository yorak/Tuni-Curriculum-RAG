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


def _data_path() -> str:
    import os
    # Prefer real data if it has been fetched; fall back to synthetic dataset.
    candidates = [
        os.environ.get("KORI_DATA_FILE", ""),
        "kori_real_data.json",
        "kori_synthetic_data.json",
    ]
    for p in candidates:
        if p and os.path.exists(p):
            return p
    raise FileNotFoundError("No curriculum data file found. Run fetch_kori_data.py first.")


def main():

    data_path = _data_path()
    print(f"Loading index from {data_path} …")

    index = build_index(data_path)

    print("Index ready")

    query = input("\nAsk a curriculum question:\n")

    answer, nodes = answer_query(index, query, call_llm)

    print("\nAnswer:\n")
    print(answer)


if __name__ == "__main__":
    main()
