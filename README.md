# Agentic AI Case Studies

A curated repository of deep-dive **architectural case studies**, brainstorms, and repeatable design patterns across the Agentic AI lifecycle.

📖 **Documentation Site**: [https://prethiv.github.io/Agentic-AI-Case-studies/](https://prethiv.github.io/Agentic-AI-Case-studies/)

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
    ├── 04-resilient-react-production-architecture/       # Case Study 4: Resilient ReAct Production Architecture & Blueprint
    │   └── README.md                                     # Enterprise ReAct loop engine, cycle detection & context control
    ├── 05-slm-edge-device-harnessing/                    # Case Study 5: Harnessing Small Language Models on Edge Devices
    │   └── README.md                                     # On-device SLM execution harness, GBNF function calling & edge routing
    ├── 06-git-prehooks-slm-judge/                        # Case Study 6: SLM-as-a-Judge via Git Pre-Hooks & llama-cli
    │   └── README.md                                     # Zero-daemon local code review, GBNF schema gating & diff linting
    ├── 07-agentic-observability-patterns/                # Case Study 7: Semantic Observability & Telemetry for Autonomous Agents
    │   └── README.md                                     # Hierarchical OTel GenAI span trees, state-delta ledgers & circuit breakers
    ├── 08-agentic-distributed-job-scheduler-mcp/         # Case Study 8: Distributed Job Scheduler via MCP, RAG & HITL
    │   └── README.md                                     # Meta-MCP batch orchestration, SLM pre-hooks & state-mutating HITL gates
    ├── 09-matrix-reasoning-latent-agent-state/           # Case Study 9: Matrix-Based Agentic Reasoning & Continuous Latent States
    │   └── README.md                                     # Replacing text scratchpads with adjacency matrix operations & GEMM planning
    ├── 10-jev-structured-react-systems/                  # Case Study 10: Structured ReAct Systems via Jev (TypeSafe AI)
    │   └── README.md                                     # Fast System 1 primitives, dynamic model routing, risk gating & observation compaction
    ├── 11-hybrid-swarm-delegation-blackboard/            # Case Study 11: Hybrid Hierarchical Delegation & Stigmergic Blackboard Swarming
    │   ├── README.md                                     # In-depth architectural blueprint, formal models, failure matrix & OTel spans
    │   └── examples/                                     # Complete executable reference architecture & unit tests
    ├── 12-agentic-test-time-compute-mcts/                # Case Study 12: Agentic Test-Time Compute (MCTS & PRMs)
    │   └── README.md                                     # Scaling test-time compute, Process Reward Models, and UCT shadow rollouts
    ├── 13-speculative-agent-execution/                   # Case Study 13: Speculative Agent Execution
    │   └── README.md                                     # Multi-draft edge SLMs, causal dependency DAG staging & frontier verification
    ├── 14-dynamic-tool-genesis-jit-synthesis/            # Case Study 14: Dynamic Tool Genesis & JIT Synthesis
    │   └── README.md                                     # Autonomous micro-tool generation, ephemeral sandboxing & runtime MCP hot-reload
    └── 15-deterministic-event-sourced-replay/            # Case Study 15: Deterministic Event-Sourced Agent Replay
        └── README.md                                     # Causal state ledgers, time-travel debugging & counterfactual branch forking
```

---

## 📚 Case Studies Index

| # | Case Study | Core Opportunity & Pattern Focus | Status |
|---|---|---|---|
| **01** | [Agentic Evaluation & CI/CD Pattern](case-studies/01-agentic-evaluation-pattern/README.md) | LangSmith-based trajectory evaluation for tools & multi-agent systems, LLM-as-a-judge verification, CI/CD automated gates | 💡 Conceptualized |
| **02** | [Context Compaction & RAG Memory Pattern](case-studies/02-context-compaction-rag-memory/README.md) | Solving context saturation in local LLMs (DeepSeek-R1:7B in LM Studio under 8k limit) via entity compaction, <think> pruning, and episodic RAG | 💡 Conceptualized |
| **03** | [Google ADK to Local LLMs via OpenAI Wrappers](case-studies/03-google-adk-local-llm-wrapper/README.md) | Decoupling Google Agent Development Kit (ADK) from Vertex AI / GCP to run locally on Ollama/LM Studio using OpenAI-compatible adapters | 💡 Conceptualized |
| **04** | [Resilient ReAct Production Architecture & Blueprint](case-studies/04-resilient-react-production-architecture/README.md) | Enterprise ReAct systems: trajectory fingerprinting for cycle detection, scratchpad distillation, Pydantic guardrails, and OpenTelemetry | 💡 Conceptualized |
| **05** | [Harnessing SLMs on Edge Devices](case-studies/05-slm-edge-device-harnessing/README.md) | On-device SLMs (Gemma 2B, Qwen 2.5 1.5B/3B, Llama 3.2 1B): GBNF-constrained function calling, edge semantic routing, and SBC/NPU optimization | 💡 Conceptualized |
| **06** | [SLM-as-a-Judge via Git Pre-Hooks & llama-cli](case-studies/06-git-prehooks-slm-judge/README.md) | Local semantic code review via Git pre-commit hooks, zero-daemon llama-cli auto-bootstrapping, and GBNF JSON Schema enforcement | 💡 Conceptualized |
| **07** | [Semantic Observability & Telemetry Patterns](case-studies/07-agentic-observability-patterns/README.md) | Cognitive loop tracing (OTel GenAI), event-sourced state-delta ledgers, budget circuit breakers, and async LLM-as-a-judge pipelines | 💡 Conceptualized |
| **08** | [Distributed Job Scheduler via MCP & HITL](case-studies/08-agentic-distributed-job-scheduler-mcp/README.md) | Meta-MCP intelligent batch engine, asynchronous multi-hop RAG, edge SLM pre-hook sanitization, and HITL authorization gates | 💡 Conceptualized |
| **09** | [Matrix-Based Agentic Reasoning](case-studies/09-matrix-reasoning-latent-agent-state/README.md) | Replacing discrete text scratchpads with continuous state matrices, causal adjacency tensors, and GPU GEMM reachability | 💡 Conceptualized |
| **10** | [Structured ReAct Systems via Jev](case-studies/10-jev-structured-react-systems/README.md) | Fast System 1 decision primitives (Noul, Choice, Score), dynamic model routing, pre-action risk gating, observation compaction & Pydantic AI TypeSafeModel | 💡 Conceptualized |
| **11** | [Hybrid Swarm Delegation & Stigmergic Blackboard](case-studies/11-hybrid-swarm-delegation-blackboard/README.md) | Hybrid hierarchical routing + stigmergic shared memory, Contract Net Protocol (CNP) task auctioning, DAG cycle & depth guards, and scoped Handoff Tokens | 💡 Conceptualized |
| **12** | [Agentic Test-Time Compute (MCTS & PRMs)](case-studies/12-agentic-test-time-compute-mcts/README.md) | Scaling test-time compute, Process Reward Models (PRMs), UCT exploration-exploitation, and backtracking over dead-end tool states | 💡 Conceptualized |
| **13** | [Speculative Agent Execution](case-studies/13-speculative-agent-execution/README.md) | Multi-draft edge SLM planning, causal dependency DAG staging, parallel shadow pre-execution, and single-pass frontier verification | 💡 Conceptualized |
| **14** | [Dynamic Tool Genesis & JIT Synthesis](case-studies/14-dynamic-tool-genesis-jit-synthesis/README.md) | Autonomous micro-tool synthesis, ephemeral sandbox unit-testing, and live Model Context Protocol (MCP) hot-registration | 💡 Conceptualized |
| **15** | [Deterministic Event-Sourced Agent Replay](case-studies/15-deterministic-event-sourced-replay/README.md) | Causal event ledgers, zero-cost offline reproduction, time-travel debugging, and counterfactual trajectory forking | 💡 Conceptualized |

---

## 🧭 Upcoming Case Study Brainstorms

- **Multi-Agent Orchestration & Protocol Handoffs**: Standardized protocols (A2A) vs shared blackboard state machines.
- **Human-in-the-Loop (HITL) Gateways**: Non-blocking asynchronous approvals and safety checkpoints.
- **Self-Correction & Autonomous Reflection Loops**: When and how agents backtrack reliably without runaway token burn.
- **Agentic Sandboxing & Tool Boundary Security**: Isolating arbitrary code and CLI execution in local/edge runtimes.

---

## 📄 License

MIT License.
