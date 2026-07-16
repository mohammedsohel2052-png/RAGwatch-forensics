"""
eval_runner.py — Main Evaluation Pipeline

Runs the full RAG evaluation:
  1. Loads knowledge base (doc.md) and embeds it
  2. Loads the golden dataset (golden_dataset.json)
  3. For each Q&A pair: retrieves relevant chunks, generates an answer, scores it
  4. Saves the run summary to SQLite (eval_results.db)
  5. Compares against the stored baseline and alerts on regressions
  6. Optionally promotes the run to baseline with --set-baseline flag

Usage:
  python eval_runner.py                  # Run eval + check regressions
  python eval_runner.py --set-baseline   # Run eval + promote result to baseline
  python eval_runner.py --top-k 0        # Simulate broken retrieval (regression demo)
"""

import argparse
import json
import os
import sys

# Allow running from project root without installing the package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "ragwatch"))

from ragwatch import Evaluator
from ragwatch.forensics.diagnose import run_diagnosis
from rag_core import load_chunks, embed_chunks, retrieve, embed_fn
from generator import generate

# ── Slack Alerter ─────────────────────────────────────────────────────────────

def send_slack_alert(alerts: list[str], run_id: str) -> None:
    webhook_url = os.getenv("SLACK_WEBHOOK_URL")
    if not webhook_url:
        return  # Slack not configured, skip silently

    import json as _json
    import urllib.request

    message = {
        "text": f":rotating_light: *RAGWatch Regression Detected* (run `{run_id[:8]}...`)",
        "blocks": [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "🚨 RAGWatch: Regression Detected"},
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "\n".join(f"• {a}" for a in alerts),
                },
            },
        ],
    }

    data = _json.dumps(message).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status == 200:
                print(f"[Slack] Alert sent successfully.")
            else:
                print(f"[Slack] Unexpected status: {resp.status}")
    except Exception as e:
        print(f"[Slack] Failed to send alert: {e}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="RAGWatch Evaluation Runner")
    parser.add_argument("--set-baseline", action="store_true", help="Promote this run to baseline after evaluation")
    parser.add_argument("--top-k", type=int, default=2, help="Number of chunks to retrieve per query (set 0 to simulate broken retrieval)")
    parser.add_argument("--golden-dataset", default="golden_dataset.json", help="Path to golden dataset JSON file")
    parser.add_argument("--doc", default="doc.md", help="Path to knowledge base markdown file")
    parser.add_argument("--db", default="eval_results.db", help="Path to SQLite results database")
    parser.add_argument("--diagnose", type=str, help="Run forensics diagnosis on a specific trace_id")
    args = parser.parse_args()

    if args.diagnose:
        print(f"[Runner] Running forensics diagnosis for trace: {args.diagnose}")
        try:
            diagnosis = run_diagnosis(args.diagnose, db_path=args.db)
            print("\n--- Diagnosis Result ---")
            print(diagnosis.model_dump_json(indent=2))
        except Exception as e:
            print(f"[Runner] Diagnosis failed: {e}")
            sys.exit(1)
        sys.exit(0)

    top_k = args.top_k

    # ── Step 1: Build the knowledge base ──────────────────────────────────────
    print("=" * 60)
    print("RAGWatch Evaluation Pipeline")
    print("=" * 60)

    chunks = load_chunks(args.doc)
    chunks, chunk_embeddings = embed_chunks(chunks)

    # ── Step 2: Load golden dataset ───────────────────────────────────────────
    with open(args.golden_dataset, "r", encoding="utf-8") as f:
        golden_dataset = json.load(f)
    print(f"[Runner] Loaded {len(golden_dataset)} items from golden dataset.")

    if top_k == 0:
        print("[Runner] WARNING: top_k=0 — retrieval is disabled (regression simulation mode).")

    # ── Step 3: Define retrieval and generation functions ─────────────────────
    def retrieval_fn(query: str) -> list[dict]:
        return retrieve(query, chunks, chunk_embeddings, top_k=top_k)

    def generation_fn(query: str, docs: list[dict]) -> dict:
        return generate(query, docs)

    # ── Step 4: Run evaluation via ragwatch SDK ───────────────────────────────
    evaluator = Evaluator(db_path=args.db, embed_fn=embed_fn)
    summary = evaluator.evaluate(golden_dataset, retrieval_fn, generation_fn)

    # ── Step 5: Check for regressions ─────────────────────────────────────────
    alerts = evaluator.check_regressions(summary)
    if alerts:
        send_slack_alert(alerts, summary["run_id"])
        print(f"\n[Runner] {len(alerts)} regression(s) detected. Exiting with code 1.")
        sys.exit(1)

    # ── Step 6: Optionally promote to baseline ────────────────────────────────
    if args.set_baseline:
        evaluator.promote_to_baseline(summary["run_id"])
        print(f"[Runner] Run {summary['run_id'][:8]}... promoted to baseline.")
    else:
        print("\n[Runner] Run complete. Use --set-baseline to promote this run to baseline.")

    print(f"[Runner] Results saved to '{args.db}'.")
    print(f"[Runner] Run ID: {summary['run_id']}")


if __name__ == "__main__":
    main()
