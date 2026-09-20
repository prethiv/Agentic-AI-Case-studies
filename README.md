# Agentic AI Case Studies

A curated repository of deep-dive **architectural case studies**, brainstorms, and repeatable design patterns across the Agentic AI lifecycle.

---

## 🎯 Aim & Vision

As Autonomous Agents and Multi-Agent Systems (MAS) transition from laboratory prototypes to production enterprise software, teams encounter recurring friction points across:
- **Observability & Trajectory Tracing**: Multi-step reasoning loops and tool-calling validation.
- **Continuous Evaluation & CI/CD**: Preventing regressions in tool calls, planning, and task completion before code ships.
- **Resilience & Governance**: Handling drift, tool execution failures, safety constraints, and latency.

This repository catalogs **brainstorms and case study blueprints** focusing on identifying architectural opportunities to build **repeatable patterns** in Agentic AI.

---

## 📂 Repository Structure

```text
.
├── README.md                                             # Repository overview & index of case studies
└── case-studies/
    ├── 01-agentic-evaluation-pattern/                    # Case Study 1: Agentic Evaluation Pattern
    │   └── README.md                                     # In-depth architectural brainstorm & pattern analysis
    ├── 02-context-compaction-rag-memory/                 # Case Study 2: Context Compaction & RAG Memory Pattern
    │   └── README.md                                     # Architectural blueprint for constrained local LLMs (8k limit)
    ├── 03-google-adk-local-llm-wrapper/                  # Case Study 3: Google ADK to Local LLM via OpenAI Wrappers
    │   └── README.md                                     # Decoupling ADK from Vertex/GCP using OpenAI-compatible wrappers
    └── 04-resilient-react-production-architecture/       # Case Study 4: Resilient ReAct Production Architecture & Blueprint
        └── README.md                                     # Enterprise ReAct loop engine, cycle detection & context control
```

---

## 📚 Case Studies Index

| # | Case Study | Core Opportunity & Pattern Focus | Status |
|---|---|---|---|
| **01** | [Agentic Evaluation & CI/CD Pattern](case-studies/01-agentic-evaluation-pattern/README.md) | LangSmith-based trajectory evaluation for tools & multi-agent systems, LLM-as-a-judge verification, CI/CD automated gates | 💡 Conceptualized |
| **02** | [Context Compaction & RAG Memory Pattern](case-studies/02-context-compaction-rag-memory/README.md) | Solving context saturation in local LLMs (DeepSeek-R1:7B in LM Studio under 8k limit) via entity compaction, <think> pruning, and episodic RAG | 💡 Conceptualized |
| **03** | [Google ADK to Local LLMs via OpenAI Wrappers](case-studies/03-google-adk-local-llm-wrapper/README.md) | Decoupling Google Agent Development Kit (ADK) from Vertex AI / GCP to run locally on Ollama/LM Studio using OpenAI-compatible adapters | 💡 Conceptualized |
| **04** | [Resilient ReAct Production Architecture & Blueprint](case-studies/04-resilient-react-production-architecture/README.md) | Enterprise ReAct systems: trajectory fingerprinting for cycle detection, scratchpad distillation, Pydantic guardrails, and OpenTelemetry | 💡 Conceptualized |

---

## 🧭 Upcoming Case Study Brainstorms

- **Multi-Agent Orchestration & Protocol Handoffs**: Standardized protocols (A2A) vs shared blackboard state machines.
- **Human-in-the-Loop (HITL) Gateways**: Non-blocking asynchronous approvals and safety checkpoints.
- **Self-Correction & Autonomous Reflection Loops**: When and how agents backtrack reliably without runaway token burn.
- **Agentic Sandboxing & Tool Boundary Security**: Isolating arbitrary code and CLI execution in local/edge runtimes.

---

## 📄 License

MIT License.
