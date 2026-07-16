# Model Regression Detection System

A CI/CD-integrated evaluation pipeline for RAG-based Q&A systems. Automatically scores an LLM pipeline against a fixed golden dataset on every commit and nightly, tracking historical metrics and alerting on regressions before they reach production.

## Why This Exists

LLMs are non-deterministic, and providers silently update models. Without automated regression testing, quality drops — hallucinations, latency spikes, or bad retrievals — are caught by angry users, not engineers. This system runs on













 every push and nightly to catch regressions automatically.

---

## Project Structure

```
.
├── doc.md                  # Knowledge base (10 insurance document chunks)
├── golden_dataset.json     # 25 Q&A pairs for evaluation (includes 2 trick questions)
├── rag_core.py             # RAG retrieval: loads doc.md, embeds with sentence-transformers
├── generator.py            # LLM generation: Ollama → OpenAI → stub fallback
├── eval_runner.py          # Main evaluation pipeline (run this in CI and locally)
├── demo.py                 # Self-contained regression demo (no API key needed)
├── requirements.txt        # Python dependencies
├── .env.example            # Environment variable template
├── ragwatch/               # The ragwatch SDK (installable Python package)
│   └── ragwatch/
│       ├── evaluator.py    # Evaluator class
│       ├── scorer.py       # RAGAS-style metrics
│       ├── regression.py   # Regression comparison logic
│       ├── monitor.py      # @monitor decorator for production tracing
│       ├── storage.py      # SQLite persistence
│       └── ui.py           # Flask dashboard (http://localhost:5050)
└── .github/workflows/
    └── eval.yml            # GitHub Actions: runs eval on every push + nightly
```

---

## Metrics Tracked

| Metric | What it measures |
|---|---|
| **Context Precision** | Of retrieved chunks, what % were actually relevant? |
| **Context Recall** | Of all needed chunks, what % did the retriever find? |
| **Answer Relevancy** | Semantic similarity between generated and expected answer |
| **Faithfulness** | Did the model hallucinate? Does it correctly say "I don't know"? |
| **Latency (ms)** | End-to-end time per query |

---

## Quick Start

### 1. Install dependencies

```bash
python -m venv venv
.\venv\Scripts\activate      # Windows
# source venv/bin/activate   # Mac/Linux
pip install -r requirements.txt
pip install -e ./ragwatch
```

### 2. Configure (optional)

```bash
cp .env.example .env
# Edit .env — set OPENAI_API_KEY or install Ollama for local LLMs
# If neither is set, the system uses a stub backend (works offline)
```

### 3. Run the demo (no API key required)

```bash
python demo.py
```

This will:
- Load the knowledge base and embed it locally
- Establish a healthy baseline
- Simulate a regression (broken retrieval)
- Show regression alerts firing

### 4. Run the full evaluation

```bash
python eval_runner.py --set-baseline   # First run: evaluate and set as baseline
python eval_runner.py                  # Subsequent runs: evaluate and compare
```

### 5. View the dashboard

```bash
python -m ragwatch.ui
# Open http://localhost:5050
```

---

## Demo: Catching a Regression in 3 Steps

```bash
# Step 1: Set a healthy baseline
python eval_runner.py --set-baseline

# Step 2: Simulate a regression (break retrieval)
python eval_runner.py --top-k 0

# The system will:
# → Detect the precision/recall drop
# → Post a Slack alert (if SLACK_WEBHOOK_URL is set)
# → Exit with code 1 (blocks CI pipeline)
```

---

## Using the `@monitor` Decorator in Production

```python
from ragwatch import monitor

@monitor(project_name="insurance-rag")
def generate_answer(query, docs):
    # Your existing RAG function — unchanged
    return {"answer": "..."}
```

Every call automatically logs latency and output previews to `ragwatch.db`, visible in the dashboard.

---

## Tech Stack

| Technology | Role |
|---|---|
| `sentence-transformers` | Local text embeddings (no API needed) |
| `numpy` | Cosine similarity for retrieval |
| `sqlite3` | Lightweight run history storage |
| `openai` SDK | Works with both OpenAI and Ollama (same API format) |
| `flask` | Local evaluation dashboard |
| `python-dotenv` | Environment variable management |
| GitHub Actions | CI/CD: runs eval on every push + nightly |

---

Built by **Mohammed Sohel Patwari**

Inspired by [RAGAS](https://docs.ragas.io/), [LangSmith](https://smith.langchain.com/), and [Braintrust](https://www.braintrustdata.com/).
