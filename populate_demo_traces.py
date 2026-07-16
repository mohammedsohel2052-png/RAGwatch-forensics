import sqlite3
import json
import uuid
import time
import os

# Ensure DB exists and has traces table
DB_PATH = "ragwatch.db" # match ui.py default for traces

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS traces (
            trace_id TEXT PRIMARY KEY,
            project TEXT,
            function_name TEXT,
            timestamp REAL,
            latency_ms REAL,
            output_preview TEXT
        )
    ''')
    conn.commit()
    conn.close()

def insert_trace(question, answer, chunks):
    trace_id = str(uuid.uuid4())
    
    # Store full data as JSON so diagnose.py can read it
    full_data = {
        "query": question,
        "answer": answer,
        "context": [{"text": c} for c in chunks]
    }
    
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''
        INSERT INTO traces (trace_id, project, function_name, timestamp, latency_ms, output_preview)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (trace_id, "insurance-demo", "generate_answer", time.time(), 450, json.dumps(full_data)))
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    
    # Trace 1: Hallucination (Good chunks, bad answer)
    insert_trace(
        "What does comprehensive auto insurance cover?",
        "Comprehensive auto insurance covers your car when you take it to the mechanic for oil changes and regular maintenance. It also covers you if your car breaks down on the highway.",
        ["Comprehensive auto insurance covers damage from theft, vandalism, natural disasters, fire, falling objects, and animal collisions."]
    )
    
    # Trace 2: Retrieval Miss (Bad chunks, no answer)
    insert_trace(
        "How does a deductible affect my premium?",
        "I don't know, this is not covered in the provided context.",
        ["Liability insurance covers the costs when you are legally responsible for injuring someone.", "Roadside assistance covers towing."]
    )
    
    print("Populated demo traces into eval_results.db")
