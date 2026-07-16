import os
import sys
import sqlite3
import json
import numpy as np
from .models import Diagnosis, Evidence
from .judge import judge_retrieval, judge_generation
from ..scorer import score_run
from ..storage import Storage

# Always resolve paths relative to the project root (3 levels up from this file)
# forensics/diagnose.py -> forensics/ -> ragwatch/ -> ragwatch/ (package) -> project root
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
DEFAULT_GOLDEN_PATH = os.path.join(PROJECT_ROOT, "golden_dataset.json")

# Try to import embed_fn from rag_core
import sys
sys.path.insert(0, PROJECT_ROOT)
try:
    from rag_core import embed_fn
except ImportError:
    embed_fn = None

def get_trace_from_db(trace_id: str, db_path: str = "eval_results.db") -> dict:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT output_preview FROM traces WHERE trace_id = ?", (trace_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return json.loads(row[0])
    return None

def get_golden_record(query: str, dataset_path: str = None) -> dict:
    if dataset_path is None:
        dataset_path = DEFAULT_GOLDEN_PATH
    try:
        with open(dataset_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for record in data:
            # golden_dataset may use either 'question' or 'query' as the key
            if record.get("question") == query or record.get("query") == query:
                return record
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return {}

def run_diagnosis(trace_id: str, db_path: str = "eval_results.db") -> Diagnosis:
    # 1. Fetch trace
    trace_data = get_trace_from_db(trace_id, db_path)
    if not trace_data:
        raise ValueError(f"Trace {trace_id} not found in {db_path}")

    query = trace_data.get("query", "Unknown Query")
    generated_answer = trace_data.get("answer", "")
    retrieved_docs = trace_data.get("context", [])
    retrieved_chunks = [d["text"] for d in retrieved_docs]

    # 2. Fetch expected golden record
    golden_record = get_golden_record(query)
    expected_answer = golden_record.get("expected_answer")

    # 3. Calculate deterministic scores using scorer.py
    # Use a zero-vector embed_fn if none is available so score_run never crashes
    safe_embed_fn = embed_fn if embed_fn is not None else (lambda text: np.zeros((1, 384)))
    scores = score_run(golden_record, retrieved_docs, generated_answer, safe_embed_fn)

    # 4. Apply taxonomy rules
    threshold = float(os.getenv("FORENSICS_THRESHOLD", "0.7"))
    
    category = "UNKNOWN"
    if scores["context_recall"] < threshold:
        category = "RETRIEVAL_MISS"
    elif scores["context_precision"] < threshold:
        category = "RETRIEVAL_NOISE"
    elif scores["faithfulness"] < threshold:
        category = "GENERATION_HALLUCINATION"
    elif scores["answer_relevancy"] < threshold:
        category = "GENERATION_MISUSE"
    else:
        category = "AMBIGUOUS_GOLDEN"

    # 5. Get LLM Judge reasoning
    reasoning_retrieval = judge_retrieval(query, retrieved_chunks)
    reasoning_generation = judge_generation(retrieved_chunks, generated_answer)

    # 6. Build evidence and diagnosis
    evidence = Evidence(
        query=query,
        retrieved_chunks=retrieved_chunks,
        generated_answer=generated_answer,
        expected_answer=expected_answer,
        judge_reasoning_retrieval=reasoning_retrieval,
        judge_reasoning_generation=reasoning_generation
    )

    # For simplicity, calculate confidence as the inverse of the lowest failing score, 
    # or a fixed value for AMBIGUOUS_GOLDEN
    confidence = 0.9 if category != "AMBIGUOUS_GOLDEN" else 0.5

    diagnosis = Diagnosis(
        trace_id=trace_id,
        category=category,
        confidence=confidence,
        evidence=evidence
    )

    # Save to storage
    storage = Storage(db_path)
    storage.save_diagnosis(diagnosis)

    return diagnosis
