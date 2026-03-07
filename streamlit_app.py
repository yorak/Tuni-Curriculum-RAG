import os
import streamlit as st

from rag.index_builder import build_index
from rag.rag_pipeline import answer_query


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


@st.cache_resource
def load_index():
    return build_index("data/kori_synthetic_60_25_12_v2.json")


st.title("Tampere Curriculum AI")

index = load_index()

query = st.text_area("Ask a curriculum question")

if st.button("Search"):

    answer, nodes = answer_query(index, query, call_llm)

    st.subheader("Answer")
    st.write(answer)

    st.subheader("Evidence")

    for n in nodes:
        st.text(n.text[:1000])
