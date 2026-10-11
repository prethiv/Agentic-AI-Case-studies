# AQuA Reference Implementation: Executable Outer-Loop Engine

This directory provides a production-grade Python reference implementation of the **Ambient Quality Agent (AQuA)** architecture, demonstrating continuous telemetry sweeps, failure clustering, adversarial verification, immutable snapshot line-anchored diagnosis, and closed-loop replay generation.

---

## 📁 File Structure

```text
examples/
├── README.md               # Architecture documentation & execution guide
├── aqua_engine.py          # Complete reference engine implementation
└── test_aqua.py            # Automated unit test suite (10 test cases)
```

---

## 🚀 Key Modules & Capabilities

| Module / Class | Production Responsibility | Mathematical / System Concept |
|---|---|---|
| `SpanRecord`, `SessionTrajectory` | Telemetry representation conforming to OpenTelemetry GenAI semantic conventions | Multi-turn conversational POMDP state ledger |
| `SourceSnapshot` | In-memory mirror of deploy-time Git repository tree keyed by `revision_id` | Immutable source versioning & AST citation boundaries |
| `TelemetrySampler` | Pulls bounded random samples ($N \le 1,000$) from BigQuery / Cloud Trace | Cost-bounded uniform sampling |
| `SinglePassReviewer` | Evaluates sessions against a 9-point rubric checklist and plain-text `goal.md` | $O(1)$ single-pass LLM judge with structured `actual/expected` diffs |
| `FailureClusterer` | Aggregates findings sharing identical causal mechanisms | Semantic loss signature grouping |
| `AdversarialVerifier` | Spot-checks candidate clusters against up to 3 full session transcripts | Sequential hypothesis testing; Type I false-positive elimination |
| `InsightLedger` | Manages lifecycle states: `NEW`, `RECURRING`, `RESOLVED`, `DISMISSED` | State machine persistence with 14-day TTL auto-resolution |
| `SourceAnchoredDiagnoser` | Traces failure signatures to `<path>:<start>-<end>` lines and computes diffs | Verified line-anchored causal attribution & unified diff synthesis |
| `ReplaySynthesizer` | Extracts user queries and environment states from failing traces | Closed-loop test synthesis for `adk run --replay` |

---

## 🧪 Running the Test Suite

Execute the test suite from this directory:

```bash
python -m unittest test_aqua.py
```

Expected output:
```text
..........
----------------------------------------------------------------------
Ran 10 tests in 0.002s

OK
```
