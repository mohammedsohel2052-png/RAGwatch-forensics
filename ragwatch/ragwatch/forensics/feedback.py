import json
import os
from datetime import datetime
import sqlite3

# Always resolve paths relative to the project root
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
DEFAULT_GOLDEN_PATH = os.path.join(PROJECT_ROOT, "golden_dataset.json")

def append_to_golden_dataset(
    trace_id: str, 
    human_corrected_answer: str,
    db_path: str = "eval_results.db",
    dataset_path: str = None
):

    """
    Appends a confirmed diagnosis to the golden dataset so the system can be evaluated against it.
    """
    if dataset_path is None:
        dataset_path = DEFAULT_GOLDEN_PATH
    # 1. Fetch the diagnosis from the DB
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT query, category, evidence_json FROM forensics WHERE trace_id = ?", (trace_id,))
    row = cursor.fetchone()
    
    if not row:
        conn.close()
        raise ValueError(f"No forensics record found for trace {trace_id}")
        
    query, category, evidence_json = row
    evidence = json.loads(evidence_json)
    
    # Update the human_confirmed flag
    cursor.execute("UPDATE forensics SET human_confirmed = 1, human_correction = ? WHERE trace_id = ?", 
                  (human_corrected_answer, trace_id))
    conn.commit()
    conn.close()

    # 2. Prepare the new golden record
    # Note: For RETRIEVAL_MISS or RETRIEVAL_NOISE, we don't know the exact "expected_source_chunk_ids" 
    # without human intervention, but the human_corrected_answer acts as the new ground truth.
    new_record = {
        "question": query,
        "expected_answer": human_corrected_answer,
        "expected_source_chunk_ids": [], # In a real system, the UI would let the human pick these
        "failure_category": category,
        "added_at": datetime.utcnow().isoformat() + "Z"
    }

    # 3. Append to golden_dataset.json
    if os.path.exists(dataset_path):
        with open(dataset_path, "r", encoding="utf-8") as f:
            try:
                dataset = json.load(f)
            except json.JSONDecodeError:
                dataset = []
    else:
        dataset = []

    # Avoid exact duplicates
    if not any(r.get("question") == query for r in dataset):
        dataset.append(new_record)
        with open(dataset_path, "w", encoding="utf-8") as f:
            json.dump(dataset, f, indent=2)
        print(f"[Feedback] Added new golden record for query: '{query}'")
    else:
        print(f"[Feedback] Query already exists in golden dataset: '{query}'. Skipping append.")
