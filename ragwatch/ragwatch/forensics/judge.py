import os

# Force stub backend so diagnosis always works offline (no Ollama/OpenAI needed)
os.environ.setdefault("GENERATOR_BACKEND", "stub")

import sys
# Path to project root — where generator.py lives
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))
try:
    from generator import generate
except ImportError:
    def generate(query, docs):
        return {"answer": "[Judge unavailable - generator not found]"}


def judge_retrieval(query: str, retrieved_chunks: list[str]) -> str:
    """
    Asks the LLM to explain if the retrieved chunks are relevant to the query.
    """
    judge_query = (
        f"You are a judge evaluating a retrieval system.\n"
        f"QUESTION: {query}\n"
        f"Do the provided chunks contain enough information to answer the question? "
        f"Provide a brief 1-2 sentence explanation."
    )
    docs = [{"text": chunk} for chunk in retrieved_chunks]
    result = generate(judge_query, docs)
    return result["answer"]

def judge_generation(retrieved_chunks: list[str], generated_answer: str) -> str:
    """
    Asks the LLM to explain if the generated answer is faithful to the chunks.
    """
    judge_query = (
        f"You are a judge evaluating an LLM's answer.\n"
        f"GENERATED ANSWER: {generated_answer}\n"
        f"Is the generated answer faithful to the provided context chunks? "
        f"Does it hallucinate facts not in the context? "
        f"Provide a brief 1-2 sentence explanation."
    )
    docs = [{"text": chunk} for chunk in retrieved_chunks]
    result = generate(judge_query, docs)
    return result["answer"]
