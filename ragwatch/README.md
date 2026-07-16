# ragwatch-sdk

**ragwatch** is a lightweight, zero-friction Python SDK for evaluating, monitoring, detecting regressions, and diagnosing root causes in RAG (Retrieval-Augmented Generation) pipelines.

Think of it as a self-hosted [LangSmith](https://smith.langchain.com/) — built from scratch, no API keys, no cloud, runs entirely on your machine.

---

## What's New in v0.2.0 — Forensics Module

v0.2.0 adds `ragwatch.forensics`: an automated root-cause diagnosis engine for RAG failures.

When your RAG pipeline gives a bad answer, forensics tells you **exactly why** — was it the retriever's fault or the LLM's fault? — and gives you a one-click path to fix it.

---

## Features

| Feature | Description |
|---|---|
| `@monitor` decorator | Drop on any function for instant latency & trace logging |
| `Evaluator` class | Run evaluations against a golden dataset in one call |
| Regression Detection | Auto-alerts when metrics drop below baseline thresholds |
| **Forensics (NEW)** | Root-cause diagnosis with 5-category failure taxonomy |
| **Feedback Loop (NEW)** | Human-confirmed failures auto-added to golden dataset |
| Dashboard UI | Visual dashboard for evaluations, traces, and forensics |
| SQLite Storage | Zero-dependency local storage, CI-friendly |

---

## Installation

```bash
pip install ragwatch-sdk
```

Or install from source (editable mode):

```bash
git clone https://github.com/mohammedsohel2052-png/Model-regression-detection
pip install -e ./ragwatch
```

---

## Quick Start

### 1. Zero-Friction Monitoring with `@monitor`

```python
from ragwatch import monitor

@monitor(project_name="my-rag-bot")
def generate_answer(query, docs):
    # Your existing RAG generation code — unchanged
    return {"answer": "...", "latency_ms": 120}
```

Every call now logs a trace to `ragwatch.db` and prints:
```
[RAGWatch] ✓ Traced 'generate_answer' | 452ms | project='my-rag-bot'
```

### 2. Full Evaluation Pipeline

```python
from ragwatch import Evaluator

evaluator = Evaluator(db_path="eval_results.db", embed_fn=my_embed_fn)

summary = evaluator.evaluate(
    golden_dataset=dataset,           # list of {"question": ..., "expected_answer": ..., ...}
    retrieval_fn=my_retrieval_fn,     # fn(query) -> list[dict]
    generation_fn=my_generation_fn,   # fn(query, docs) -> {"answer": str, "latency_ms": float}
)
```

### 3. Regression Detection

```python
# Check current run against the stored baseline
alerts = evaluator.check_regressions(summary)

if alerts:
    print("Regression detected! CI should fail here.")

# If happy with results, promote as the new baseline
evaluator.promote_to_baseline(summary["run_id"])
```

### 4. Forensics — Root-Cause Diagnosis (NEW in v0.2.0)

```python
from ragwatch.forensics import run_diagnosis

# Diagnose a specific failing trace by its ID
diagnosis = run_diagnosis(trace_id="<uuid>", db_path="ragwatch.db")

print(diagnosis.category)    # e.g. "GENERATION_HALLUCINATION"
print(diagnosis.confidence)  # e.g. 0.9
print(diagnosis.evidence.judge_reasoning_generation)  # human-readable explanation
```

**The 5 failure categories:**

| Category | What it means |
|---|---|
| `RETRIEVAL_MISS` | Right docs existed in the DB, but the retriever failed to find them |
| `RETRIEVAL_NOISE` | Retriever returned irrelevant chunks |
| `GENERATION_HALLUCINATION` | Good context was retrieved, but LLM made things up |
| `GENERATION_MISUSE` | Good context was retrieved, but LLM gave a bad answer anyway |
| `AMBIGUOUS_GOLDEN` | Pipeline was correct, but the test data itself was wrong |

### 5. Human Feedback Loop (NEW in v0.2.0)

```python
from ragwatch.forensics import append_to_golden_dataset

# After a human confirms the correct answer, inject it into the golden dataset
append_to_golden_dataset(
    trace_id="<uuid>",
    human_corrected_answer="The correct answer is...",
    db_path="ragwatch.db"
)
# This writes a new entry to golden_dataset.json automatically
```

### 6. RAGWatch Dashboard

Visualize evaluations, live telemetry, and forensics in one place:

```bash
python -m ragwatch.ui
```

Open `http://localhost:5050` in your browser.

- **Evaluations Tab**: Track Precision, Recall, Relevancy, and Faithfulness over time.
- **Live Traces Tab**: See every `@monitor` call in real-time. Click **Diagnose** to trigger forensics.
- **Forensics View**: Side-by-side view of retrieved context vs. generated answer with LLM judge reasoning.

---

## Metrics Explained

| Metric | What it measures |
|---|---|
| **Context Precision** | Of retrieved chunks, what % were actually relevant? |
| **Context Recall** | Of all needed chunks, what % did we retrieve? |
| **Answer Relevancy** | Semantic similarity between generated & expected answer |
| **Faithfulness** | Did the model stick to the retrieved context or hallucinate? |

---

## CLI Usage

```bash
# Run evaluation + check for regressions
python eval_runner.py

# Promote this run to baseline
python eval_runner.py --set-baseline

# Simulate broken retrieval (regression demo)
python eval_runner.py --top-k 0

# Run forensics diagnosis on a specific trace from CLI
python eval_runner.py --diagnose <trace_id>
```

---

## Project Structure

```
ragwatch/
├── ragwatch/
│   ├── __init__.py          # Public API: Evaluator, monitor
│   ├── evaluator.py         # Main Evaluator class
│   ├── scorer.py            # Metric calculation (precision, recall, faithfulness, relevancy)
│   ├── storage.py           # SQLite persistence (runs, traces, forensics)
│   ├── monitor.py           # @monitor decorator
│   ├── regression.py        # Regression alert logic
│   ├── ui.py                # Flask dashboard server
│   ├── templates/
│   │   ├── index.html       # Main dashboard (evaluations + live traces)
│   │   └── forensics.html   # Root-cause diagnosis view
│   └── forensics/           # NEW in v0.2.0
│       ├── __init__.py      # Public API: run_diagnosis, append_to_golden_dataset
│       ├── models.py        # Pydantic schemas (Diagnosis, Evidence)
│       ├── judge.py         # LLM-as-a-judge for retrieval + generation
│       ├── diagnose.py      # Full diagnosis pipeline
│       └── feedback.py      # Human feedback → golden dataset loop
└── pyproject.toml
```

---

## Changelog

### v0.2.0
- **NEW**: `ragwatch.forensics` subpackage — automated root-cause diagnosis
- **NEW**: 5-category failure taxonomy (RETRIEVAL_MISS, RETRIEVAL_NOISE, GENERATION_HALLUCINATION, GENERATION_MISUSE, AMBIGUOUS_GOLDEN)
- **NEW**: LLM-as-a-judge for human-readable failure explanations
- **NEW**: Human feedback loop — confirmed failures auto-injected into golden dataset
- **NEW**: Forensics view in the dashboard with side-by-side evidence display
- **NEW**: `POST /api/forensics/<trace_id>` and `POST /api/forensics/<trace_id>/confirm` API endpoints
- **UPDATED**: `storage.py` — new `forensics` table + `save_diagnosis` method
- **UPDATED**: `eval_runner.py` — new `--diagnose <trace_id>` CLI flag
- **UPDATED**: Dependencies — added `pydantic>=2.0`, `flask`

### v0.1.1
- Initial release
- `@monitor` decorator
- `Evaluator` class with evaluation pipeline
- Regression detection against stored baseline
- SQLite storage for runs and traces
- Basic Flask dashboard

---

## Built By

Mohammed Sohel Patwari — [GitHub](https://github.com/mohammedsohel2052-png)

Inspired by [RAGAS](https://docs.ragas.io/), [LangSmith](https://smith.langchain.com/), and [Braintrust](https://www.braintrustdata.com/).
