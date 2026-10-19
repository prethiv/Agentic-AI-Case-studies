# Agentic Saga Orchestration: Executable Reference Architecture

This directory provides a production-grade Python reference implementation of the **Agentic Saga Orchestration & Distributed Compensating Actions Engine**, demonstrating Write-Ahead Intent Ledgers, LIFO inverse unwinding, dynamic output parameter binding, idempotency fencing, and dead-letter queue freeze.

---

## 📁 File Structure

```text
examples/
├── README.md                      # Architecture guide & execution instructions
├── saga_orchestration_engine.py   # Complete Saga Coordinator, Ledger, & Interceptor Engine
└── test_saga_orchestration.py     # Automated unit & integration test suite (11 test cases)
```

---

## 🚀 Key Modules & Capabilities

| Class / Component | Production Responsibility | Operational Invariant |
|---|---|---|
| `WriteAheadIntentLedger` | Append-only journal recording forward actions, output snapshots, and compensation contracts | Writes intent to persistent memory before dispatching external mutations |
| `CompensatingActionSpec` | Explicit inverse contract schema with dynamic parameter mapping and idempotency tokens | Guarantees reversible operations declare deterministic inverse semantics |
| `AgenticSagaCoordinator` | Orchestrator controlling step commitments and deterministic reverse (LIFO) unwinding | Neutralizes side effects in strict reverse chronological order upon trajectory failure |
| `RuntimeMutatingToolGate` | Pre-execution registration gate and post-execution output binder | Intercepts agent tool dispatch, enforcing transactional safety boundaries |
| `DeadLetterEntry` & DLQ | Critical incident escalation queue capturing unrecoverable rollback attempts | Halts automated rollback on compensation failure to prevent cascading corruption |
| `CleanStateReconciliationReport` | Cryptographic audit trail and clean-state attestation | Emits SHA-256 state integrity digests and full chronological timeline |

---

## 🧪 Running the Test Suite

Execute the test suite from this directory or repository root:

```bash
python case-studies/33-agentic-saga-orchestration-distributed-compensating-actions/examples/test_saga_orchestration.py
```

Expected output:
```text
...........
----------------------------------------------------------------------
Ran 11 tests in 0.113s

OK
```
