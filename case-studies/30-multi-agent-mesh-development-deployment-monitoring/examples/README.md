# Case Study 30: Reference Architecture Implementation

This folder contains the complete, zero-dependency reference implementation of a **Decentralized Multi-Agent Mesh (Agentic Service Fabric)** demonstrating peer-to-peer cognitive routing, Contract Net Protocol (CNP) auctions, sidecar proxy guardrails, and OpenTelemetry GenAI distributed tracing.

---

## 🚀 Quickstart

Run the self-contained demonstration immediately using Python 3.8+ (no third-party packages or external services required):

```bash
# Execute the end-to-end incident response mesh simulation
python mesh_core.py

# Execute the automated unit and integration test suite
python -m unittest test_mesh.py
```

### What the Simulation Demonstrates:
1. **Dynamic Intent Routing**:
   - The `Sentinel` receives an unhandled root SSH intrusion alert.
   - Computes intent embeddings and queries the `CapabilityRegistry`.
   - Autonomously delegates forensic correlation to `ForensicInvestigator` without any central orchestrator bottleneck.
2. **Parallel Peer Sub-Delegation**:
   - `ForensicInvestigator` delegates the firewall remediation to `PatchSynthesizer`.
   - Concurrently delegates blast radius assessment to `ComplianceAuditor`.
3. **OpenTelemetry Causal DAG Generation**:
   - Emits structured distributed spans across all 4 peer agents sharing a single W3C `TraceId`.
   - Automatically renders the interactive causal execution tree in standard Mermaid syntax.
4. **Resilient Mesh Guardrails**:
   - **Cycle Prevention**: Blocks attempted cyclic delegation loops ($A \to B \to A$) before token burn.
   - **Monotonic TTL**: Terminates requests exceeding the configured hop limit.
   - **Circuit Breakers**: Transitions between `CLOSED`, `OPEN`, and `HALF_OPEN` states under simulated peer failures.

---

## 📁 Architecture Overview

```text
examples/
├── mesh_core.py     # Core Multi-Agent Mesh runtime
│   ├── OpenTelemetry Distributed Tracing (OTelSpan, DistributedTraceCollector)
│   ├── A2A Wire Protocol & Envelopes (A2AMessageEnvelope, Attenuated Macaroons)
│   ├── Semantic Capability Registry (CapabilityProfile, Multi-attribute Intent Routing)
│   ├── Contract Net Protocol Engine (RFPAnnouncement, CNPBid, Surplus Scoring)
│   ├── Cognitive Sidecar Proxy (Hop Limiter, Cycle Breaker, Circuit Breakers)
│   └── Autonomous AgentNode (P2P Handlers, Inboxes, Attenuated Delegation)
├── test_mesh.py     # Unit test suite verifying all mesh primitives
└── README.md        # Execution guide and architecture documentation
```

---

## 🛠️ Key Classes and Interfaces

| Class | Role | Core Responsibility |
|---|---|---|
| `AgentNode` | Sovereign Peer Node | Houses agent DID, capability profile, local memory, and handles inbound/outbound A2A messages. |
| `A2AMessageEnvelope` | Wire Protocol | Standard envelope encapsulating W3C Trace Context, monotonic hop limiters, and delegation history. |
| `CapabilityRegistry` | Discovery Plane | Matches semantic intents to peer nodes via Pareto utility optimization (Cosine Similarity, Trust, Latency, Cost). |
| `ContractNetEngine` | Market Auction | Orchestrates Request-for-Proposal (RFP) broadcasts, collects bids, and awards subtask contracts. |
| `CognitiveSidecarProxy` | Boundary Security | Intercepts all peer traffic, decrements hop limits, halts cyclic loops, and trips circuit breakers on repeated errors. |
| `DistributedTraceCollector`| Observability | Records OpenTelemetry GenAI spans and exports causal DAGs in Mermaid and JSON formats. |
