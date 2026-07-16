import sqlite3
import json
import os

class Storage:
    def __init__(self, db_path="ragwatch.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS runs (
            run_id TEXT PRIMARY KEY,
            timestamp TEXT,
            commit_hash TEXT,
            is_baseline BOOLEAN DEFAULT 0,
            avg_context_precision REAL,
            avg_context_recall REAL,
            avg_answer_relevancy REAL,
            faithfulness_score REAL,
            avg_latency_ms REAL,
            total_cost_usd REAL,
            details_json TEXT
        )
        ''')
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS traces (
            trace_id TEXT PRIMARY KEY,
            project TEXT,
            function_name TEXT,
            timestamp REAL,
            latency_ms REAL,
            output_preview TEXT
        )
        ''')
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS forensics (
            trace_id TEXT PRIMARY KEY,
            query TEXT,
            retrieval_score REAL,
            generation_score REAL,
            category TEXT,
            confidence REAL,
            evidence_json TEXT,
            human_confirmed BOOLEAN DEFAULT 0,
            human_correction TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        conn.commit()
        conn.close()

    def save_run(self, summary: dict):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        m = summary["metrics"]
        cursor.execute('''
        INSERT INTO runs (
            run_id, timestamp, commit_hash, is_baseline,
            avg_context_precision, avg_context_recall, avg_answer_relevancy,
            faithfulness_score, avg_latency_ms, total_cost_usd, details_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            summary["run_id"], summary["timestamp"], summary["commit_hash"], False,
            m["avg_context_precision"], m["avg_context_recall"],
            m["avg_answer_relevancy"], m["faithfulness_score"],
            m["avg_latency_ms"], m.get("total_cost_usd", 0.0),
            json.dumps(summary.get("details", []))
        ))
        conn.commit()
        conn.close()

    def get_baseline_run(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM runs WHERE is_baseline = 1 ORDER BY timestamp DESC LIMIT 1')
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
            
        return {
            "run_id": row[0],
            "timestamp": row[1],
            "commit_hash": row[2],
            "metrics": {
                "avg_context_precision": row[4],
                "avg_context_recall": row[5],
                "avg_answer_relevancy": row[6],
                "faithfulness_score": row[7],
                "avg_latency_ms": row[8],
                "total_cost_usd": row[9]
            }
        }

    def save_trace(self, trace: dict):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
        INSERT OR IGNORE INTO traces (trace_id, project, function_name, timestamp, latency_ms, output_preview)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            trace["trace_id"], trace["project"], trace["function"],
            trace["timestamp"], trace["latency_ms"], trace["output_preview"]
        ))
        conn.commit()
        conn.close()

    def promote_to_baseline(self, run_id: str):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('UPDATE runs SET is_baseline = 0')
        cursor.execute('UPDATE runs SET is_baseline = 1 WHERE run_id = ?', (run_id,))
        conn.commit()
        conn.close()
        print(f"Run {run_id} promoted to baseline.")

    def save_diagnosis(self, diagnosis):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
        INSERT OR REPLACE INTO forensics (
            trace_id, query, retrieval_score, generation_score,
            category, confidence, evidence_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            diagnosis.trace_id,
            diagnosis.evidence.query,
            0.0, # Will update these if we decide to store raw metric scores in the future
            0.0,
            diagnosis.category,
            diagnosis.confidence,
            diagnosis.evidence.model_dump_json()
        ))
        conn.commit()
        conn.close()
