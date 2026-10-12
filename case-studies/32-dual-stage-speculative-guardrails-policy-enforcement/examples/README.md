# Speculative Policy Guardrails: Executable Reference Architecture

This directory provides a production-grade Python reference implementation of the **Dual-Stage Speculative Guardrail & Non-Blocking Policy Enforcement Engine**, demonstrating sub-15ms fast-path deterministic screening, action risk stratification, asynchronous deep semantic evaluation, and transactional Two-Phase Commit (2PC) quarantine buffers.

---

## 📁 File Structure

```text
examples/
├── README.md                          # Execution guide & architectural blueprint
├── speculative_guardrail_engine.py    # Complete core engine implementation
└── test_speculative_guardrails.py     # Automated unit test suite (10 test cases)
```

---

## 🚀 Key Modules & Capabilities

| Class / Component | Production Responsibility | Operational Invariant |
|---|---|---|
| `FastPathFilter` | Deterministic regex, Bloom filter keyword detection, base64/unicode normalization & entropy scanning | Guaranteed $< 15\text{ms}$ execution budget; drops high-confidence violations before compute waste |
| `BloomFilter` | Space-efficient probabilistic set membership screening for blacklisted tokens | $O(k)$ sub-millisecond screening for exfiltration terms |
| `ActionRiskClassifierGate` | Classifies actions into `LOW_IDEMPOTENT` vs `HIGH_MUTATING` | Strictly fails safe: uncertified tools default to `HIGH_MUTATING` |
| `DeepSemanticEvaluator` | Asynchronous semantic policy engine (simulating LLM-as-a-judge / formal OPA) with cryptographic HMAC-SHA256 clearance receipts | Evaluates contextual licensing, indirect prompt injections, and data sovereignty rules |
| `SpeculativeStagingBuffer` | Transactional in-memory quarantine buffer holding uncommitted tool observations | Complete state isolation until 2PC clearance is emitted |
| `SpeculativePolicyEngine` | Runtime orchestrator managing synchronous barriers, parallel speculative dispatch, and fail-closed timeout handlers | Slashes perceived guardrail latency to zero for low-risk actions while strictly enforcing safety |

---

## 🧪 Running the Unit Test Suite

Execute the test suite from this directory:

```bash
python -m unittest test_speculative_guardrails.py
```

Expected output:
```text
..........
----------------------------------------------------------------------
Ran 10 tests in 0.35s

OK
```
