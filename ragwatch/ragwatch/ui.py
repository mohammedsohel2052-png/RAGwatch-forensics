import os
import sqlite3
import json
from flask import Flask, render_template, jsonify, request

import sys
# Add the parent directory (ragwatch/) to path so we can import ragwatch as a package
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from ragwatch.forensics.diagnose import run_diagnosis
from ragwatch.forensics.feedback import append_to_golden_dataset


template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
app = Flask(__name__, template_folder=template_dir)

# Try to find databases in the current working directory
EVAL_DB = "eval_results.db"
RAGWATCH_DB = "ragwatch.db"

def get_db_connection(db_path):
    if not os.path.exists(db_path):
        return None
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/runs")
def get_runs():
    conn = get_db_connection(EVAL_DB)
    if not conn:
        return jsonify([])
    try:
        runs = conn.execute("SELECT * FROM runs ORDER BY timestamp DESC LIMIT 50").fetchall()
        return jsonify([dict(r) for r in runs])
    except Exception as e:
        print(f"Error reading eval runs: {e}")
        return jsonify([])
    finally:
        conn.close()

@app.route("/api/traces")
def get_traces():
    conn = get_db_connection(RAGWATCH_DB)
    if not conn:
        return jsonify([])
    try:
        traces = conn.execute("SELECT * FROM traces ORDER BY timestamp DESC LIMIT 100").fetchall()
        return jsonify([dict(t) for t in traces])
    except Exception as e:
        print(f"Error reading traces: {e}")
        return jsonify([])
    finally:
        conn.close()

@app.route("/forensics/<trace_id>")
def forensics_view(trace_id):
    return render_template("forensics.html", trace_id=trace_id)

@app.route("/api/forensics/<trace_id>", methods=["POST"])
def api_run_diagnosis(trace_id):
    try:
        # First check if the trace exists in EVAL_DB, then RAGWATCH_DB
        db_to_use = EVAL_DB
        conn = get_db_connection(EVAL_DB)
        if conn:
            row = conn.execute("SELECT 1 FROM traces WHERE trace_id=?", (trace_id,)).fetchone()
            conn.close()
            if not row:
                db_to_use = RAGWATCH_DB
        
        diagnosis = run_diagnosis(trace_id, db_path=db_to_use)
        return jsonify({"success": True, "data": diagnosis.model_dump()})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/forensics/<trace_id>/confirm", methods=["POST"])
def api_confirm_diagnosis(trace_id):
    try:
        data = request.json or {}
        human_correction = data.get("human_correction", "")
        # forensics records are saved to RAGWATCH_DB by save_diagnosis
        append_to_golden_dataset(trace_id, human_correction, db_path=RAGWATCH_DB)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

def run():
    print("[RAGWatch UI] Starting RAGWatch Local Dashboard on http://localhost:5050")
    print("Press CTRL+C to quit.")
    app.run(host="0.0.0.0", port=5050, debug=False)

if __name__ == "__main__":
    run()
