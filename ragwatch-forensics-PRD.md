# PRD: Forensics Module for `ragwatch`
### Root-cause diagnosis layer, integrated into the existing Model-regression-detection repo

---

## 1. Context

`ragwatch` (repo: `Model-regression-detection`) already does regression **detection**:
it scores a RAG pipeline against a golden dataset on every push/nightly, across
4 RAGAS-style metrics (context precision, context recall, answer relevancy,
faithfulness), stores history in SQLite, alerts on drops, and exposes a Flask
dashboard on `:5050`.

What it does **not** do yet: when a regression or a single bad output is flagged,
tell you *which step* in the pipeline caused it and *why*.

This PRD adds that missing piece — a **forensics module** — as a new subpackage
inside the existing `ragwatch/` package. It is not a new repo, not a new database,
not a new dashboard. It extends what's already there.

**Do not build:** a new frontend, a new storage backend, a new CLI tool separate
from `eval_runner.py`. Everything below plugs into existing files.

---

## 2. Problem statement

Right now, when `eval_runner.py` reports a regression (e.g. faithfulness score
drops on a run), the developer has to manually inspect `rag_core.py` and
`generator.py` output to figure out whether the retriever pulled bad chunks or
the generator hallucinated on top of good chunks. That manual triage is the
gap. The forensics module automates it: given a failing query, it walks the
pipeline backward, scores each step's output against its input using an
LLM-as-judge, and returns a structured diagnosis instead of a raw score drop.

---

## 3. Goals / Non-goals

**Goals**
- Given a `trace_id` (or a raw query that currently fails), identify which
  pipeline stage is the root cause: retrieval or generation.
- Categorize the failure using a fixed taxonomy (below).
- Produce a structured, human-readable explanation with the specific
  input/output evidence.
- On human confirmation, auto-append the case to `golden_dataset.json` so the
  next `eval_runner.py` run includes it — closing the loop.
- Surface all of this in the existing Flask dashboard (`ui.py`) as a new view,
  not a new app.

**Non-goals**
- No new pipeline stages (the RAG pipeline stays: retrieve → generate).
- No new persistence layer — extend the existing SQLite schema in `storage.py`.
- No red-teaming / adversarial testing — that's a separate, later project.
- No support for arbitrary multi-step pipelines beyond the current 2-stage
  retrieve→generate flow, unless Phase 3 explicitly extends it.

---

## 4. Failure taxonomy

Adapted to this specific pipeline (retrieve → generate), not the generic
4-step version:

| Category | Definition |
|---|---|
| `RETRIEVAL_MISS` | Correct chunks existed in `doc.md` but weren't retrieved (low context recall). |
| `RETRIEVAL_NOISE` | Retrieved chunks are irrelevant to the query (low context precision). |
| `GENERATION_HALLUCINATION` | Retrieved context was fine; the generator invented facts not present in it (low faithfulness). |
| `GENERATION_MISUSE` | Retrieved context was fine and relevant, but the generator ignored or misused it (low answer relevancy despite good retrieval). |
| `AMBIGUOUS_GOLDEN` | The golden answer itself is questionable for this query (flag for human review, don't auto-blame the pipeline). |

---

## 5. Architecture

```
ragwatch/
├── ragwatch/
│   ├── evaluator.py       (existing)
│   ├── scorer.py          (existing — 4 RAGAS-style metrics)
│   ├── regression.py      (existing)
│   ├── monitor.py         (existing — @monitor decorator)
│   ├── storage.py         (existing — SQLite; EXTEND schema)
│   ├── ui.py              (existing — Flask dashboard; ADD route)
│   └── forensics/         <-- NEW subpackage
│       ├── __init__.py
│       ├── judge.py        # LLM-as-judge step scoring
│       ├── diagnose.py     # backward walk + taxonomy classification
│       ├── feedback.py     # writes confirmed cases back to golden_dataset.json
│       └── models.py       # Pydantic models: StepSpan, Diagnosis, Evidence
├── eval_runner.py          (EXTEND: --diagnose flag)
├── golden_dataset.json     (existing — feedback target)
```

**Data flow for a diagnosis request:**

1. `eval_runner.py --diagnose <trace_id>` or a "Flag as bad" button in `ui.py`
   triggers `forensics.diagnose.run(trace_id)`.
2. `diagnose.py` pulls the stored spans for that trace from `storage.py`
   (retrieval step: query + retrieved chunks; generation step: chunks + answer).
3. `judge.py` calls the LLM twice:
   - Judge A: "Given the query, are these retrieved chunks relevant and
     sufficient?" → scores retrieval step.
   - Judge B: "Given these chunks, is this answer a faithful, correct use of
     them?" → scores generation step.
4. `diagnose.py` applies the taxonomy rules (below) to the two scores and
   returns a `Diagnosis` object with category, confidence, and the specific
   evidence (chunk text, generated span) that supports it.
5. If a human confirms the diagnosis in `ui.py`, `feedback.py` appends a new
   entry to `golden_dataset.json` with: original query, correct answer
   (human-corrected if provided), failure category, and a timestamp.

**Classification rule (deterministic, not LLM-decided):**

```
if context_recall_score < threshold: RETRIEVAL_MISS
elif context_precision_score < threshold: RETRIEVAL_NOISE
elif faithfulness_score < threshold: GENERATION_HALLUCINATION
elif answer_relevancy_score < threshold and above two are fine: GENERATION_MISUSE
else: AMBIGUOUS_GOLDEN
```

Reuse `scorer.py`'s existing metric functions for these four scores instead of
reimplementing them — this is the main integration point with existing code.

---

## 6. Data model additions (`storage.py`)

Add one table to the existing SQLite schema:

```sql
CREATE TABLE IF NOT EXISTS forensics (
    trace_id TEXT PRIMARY KEY,
    query TEXT,
    retrieval_score REAL,
    generation_score REAL,
    category TEXT,
    confidence REAL,
    evidence_json TEXT,      -- serialized Evidence object
    human_confirmed BOOLEAN DEFAULT 0,
    human_correction TEXT,   -- optional corrected answer
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

`Evidence` (Pydantic model in `forensics/models.py`):
```python
class Evidence(BaseModel):
    query: str
    retrieved_chunks: list[str]
    generated_answer: str
    expected_answer: str | None
    judge_reasoning_retrieval: str
    judge_reasoning_generation: str
```

---

## 7. UI additions (`ui.py`)

Do not build a new frontend. Add to the existing Flask dashboard:
- A "Flag" button next to each run/query in the existing results table.
- A new route `/forensics/<trace_id>` rendering the `Diagnosis` — category,
  confidence, retrieved chunks vs. generated answer side by side, and a
  Confirm / Override button.
- On confirm, call `feedback.py` to append to `golden_dataset.json`.

---

## 8. `eval_runner.py` extension

Add a CLI flag:
```
python eval_runner.py --diagnose <trace_id>
```
Runs the forensics pipeline standalone (no server needed) and prints the
`Diagnosis` to stdout as JSON — needed for CI use and for scripting the demo.

---

## 9. Phased implementation (for the coding agent)

**Phase 1 — Core diagnosis (no UI)**
- `forensics/models.py`, `judge.py`, `diagnose.py`
- Wire into `storage.py` schema
- `eval_runner.py --diagnose` CLI flag
- Test: run against 3–5 known-bad queries from `golden_dataset.json`'s trick
  questions, confirm correct category assigned

**Phase 2 — Feedback loop**
- `feedback.py`: append confirmed diagnoses to `golden_dataset.json`
- Re-run `eval_runner.py` and confirm the new case is scored on subsequent runs

**Phase 3 — Dashboard integration**
- Flag button + `/forensics/<trace_id>` route in `ui.py`
- Confirm/override wired to `feedback.py`

**Phase 4 — Demo**
- Take 3 of the intentionally-broken scenarios already in the repo (or add
  2–3 new ones to `doc.md`/`golden_dataset.json` if needed)
- Record: regression detected by existing `eval_runner.py` → forensics
  diagnosis identifies root cause with evidence → human confirms → golden
  dataset grows → re-run shows the case now passing or correctly tracked

---

## 10. Acceptance criteria

- [ ] Running `--diagnose` on a known retrieval-failure case returns
      `RETRIEVAL_MISS` or `RETRIEVAL_NOISE` with supporting evidence
- [ ] Running `--diagnose` on a known hallucination case returns
      `GENERATION_HALLUCINATION` with the specific unsupported claim quoted
      from the generated answer
- [ ] Confirming a diagnosis via the dashboard adds a new row to
      `golden_dataset.json` with correct schema matching existing entries
- [ ] `eval_runner.py` still runs and passes with the new table present
      (no breaking changes to existing eval flow)
- [ ] No new top-level dependencies beyond what an LLM-as-judge call requires
      (reuse `generator.py`'s existing OpenAI/Ollama/stub fallback pattern)

---

## 11. Notes for the coding agent

- Before writing any code, read `scorer.py`, `monitor.py`, and `storage.py` in
  full — reuse their existing metric functions and DB connection pattern
  rather than reimplementing.
- `generator.py` already has an OpenAI → Ollama → stub fallback chain for
  LLM calls — the judge calls in `judge.py` should reuse that same fallback
  logic, not add a second one.
- Keep `forensics/` a self-contained subpackage so it can be `pip install -e`'d
  independently later if needed, consistent with how `ragwatch` itself is
  packaged.
- Threshold values for the classification rule (Section 5) should be
  configurable via `.env`, matching the existing config pattern in
  `.env.example`.

---

## 12. Resume framing (once Phases 1–2 are done)

> Extended a CI-integrated LLM eval system with a root-cause forensics module
> that diagnoses whether pipeline failures originate in retrieval or
> generation, using LLM-as-judge scoring against a fixed taxonomy, and feeds
> confirmed failures back into the golden evaluation dataset — closing the
> loop from detection to diagnosis to regression coverage.
