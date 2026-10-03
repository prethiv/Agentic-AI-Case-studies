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
    ├── 15-deterministic-event-sourced-replay/            # Case Study 15: Deterministic Event-Sourced Agent Replay
    │   └── README.md                                     # Causal state ledgers, time-travel debugging & counterfactual branch forking
    ├── 16-opencode-native-ide-harness-architecture/      # Case Study 16: Harnessing OpenCode as Native IDE Plugins
    │   └── README.md                                     # Headless daemon RPC, LSP telemetry sync, virtual diff staging & agent swarms
    ├── 17-agentic-enterprise-governance-mcp-api/         # Case Study 17: Agentic AI-Driven Enterprise Governance
    │   └── README.md                                     # Automated policy enforcement, custom tool mesh, OPA/ABAC gating & red-teaming
    ├── 18-laya-system1-decision-engine/                  # Case Study 18: Open-Source System 1 Decision Engines via Laya
    │   └── README.md                                     # Non-autoregressive ModernBERT decision heads, dual-process ReAct, embedding shortlists & local governance
    ├── 19-async-hitl-distributed-durable-suspension/     # Case Study 19: Asynchronous HITL via Durable Coroutines & Epoch Re-anchoring
    │   └── README.md                                     # Distributed workflow engines, non-blocking coroutine suspension, Merkle state snapshots & drift reconciliation
    ├── 20-token-budget-circuit-breakers-adaptive-decay/  # Case Study 20: Runaway Reasoning Circuit Breakers & Dynamic Context Decay
    │   └── README.md                                     # Three-state circuit breakers (Closed/Open/Half-Open), velocity ceilings, exponential context decay & loop guards
    ├── 21-a2a-zero-trust-capability-tokens/              # Case Study 21: Zero-Trust Agent-to-Agent (A2A) Capability Mesh & Macaroons
    │   └── README.md                                     # Monotonic offline caveat attenuation, delegation chains, HMAC verification & Confused Deputy neutralization
    ├── 22-ephemeral-microvm-agentic-sandbox/             # Case Study 22: Ephemeral MicroVM & eBPF Sandboxing for Dynamic Tool Execution
    │   └── README.md                                     # Hardware-assisted KVM isolation, sub-5ms Copy-on-Write snapshots, eBPF host syscall probes & network gating
    ├── 23-active-inference-entropy-directed-backtracking/# Case Study 23: Active Inference & Free-Energy Minimization in Agent Backtracking
    │   └── README.md                                     # Expected Free Energy (EFE) minimization, epistemic vs pragmatic value decomposition & entropy search pruning
    ├── 24-speculative-pre-computation-multi-mcp/         # Case Study 24: Speculative Tool Pipelining & Branch-Prediction across MCP Nodes
    │   └── README.md                                     # Streaming prefix branch prediction, speculative shadow leases, atomic commits & side-effect rollback isolation
    ├── 25-byzantine-fault-tolerant-consensus-swarms/     # Case Study 25: Byzantine-Fault-Tolerant (BFT) Multi-Agent Consensus Verification
    │   └── README.md                                     # 3f + 1 quorum thresholds, confidence-weighted voting, cryptographic commit ledgers & adversarial mitigation
    ├── 26-agentic-meta-reasoning-thinking-before-thinking/# Case Study 26: Thinking Before Thinking — Agentic Meta-Reasoning & Inference Scaling
    │   ├── README.md                                     # Decoupled 4-stage metacognitive control (Assess, Propose, Evaluate, Dispatch), DAG artifact memory & Type-2 AUC
    │   └── examples/                                     # Fully executable reference pipeline and metrics verification runner
    └── 27-autonomous-reflection-loops-graph-backtracking/# Case Study 27: Autonomous Reflection Loops & Directed Graph Backtracking
        ├── README.md                                     # Trajectory DAGs, causal error categorization, clean context pruning, and negative constraint ledgers
        └── examples/                                     # Fully executable reference pipeline with anti-loop budgeting and saga compensation
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
| **16** | [Harnessing OpenCode as Native IDE Plugins](case-studies/16-opencode-native-ide-harness-architecture/README.md) | Headless daemon RPC runtime, live LSP & cursor telemetry sync, in-memory virtual diff staging (`opencode-diff://`), hierarchical subagents & model routing | 💡 Conceptualized |
| **17** | [Agentic Enterprise Governance for API & MCP](case-studies/17-agentic-enterprise-governance-mcp-api/README.md) | Autonomous Sentinel Proxy, inline OPA / ABAC gating, real-time PII scrubbing, continuous adversarial red-teaming & schema drift auto-remediation | 💡 Conceptualized |
| **18** | [Open-Source System 1 Decision Engines via Laya](case-studies/18-laya-system1-decision-engine/README.md) | Non-autoregressive ModernBERT decision heads, dual-process ReAct primitives (Noul, Choice, Score), embedding shortlists, and local self-hosted governance | 💡 Conceptualized |
| **19** | [Asynchronous HITL via Durable Coroutines](case-studies/19-async-hitl-distributed-durable-suspension/README.md) | Durable coroutine suspension across unbounded delays, Merkle state versioning, epoch drift reconciliation, and non-blocking human escrow | 💡 Conceptualized |
| **20** | [Runaway Reasoning Circuit Breakers & Adaptive Decay](case-studies/20-token-budget-circuit-breakers-adaptive-decay/README.md) | Finite token budget telemetry, Closed/Open/Half-Open state machines, instantaneous velocity ceilings, and exponential scratchpad decay | 💡 Conceptualized |
| **21** | [Zero-Trust A2A Capability Mesh & Macaroons](case-studies/21-a2a-zero-trust-capability-tokens/README.md) | Monotonic cryptographic attenuation, delegation chains ($A \rightarrow B \rightarrow C$), caveat enforcement, and Confused Deputy neutralization | 💡 Conceptualized |
| **22** | [Ephemeral MicroVM & eBPF Sandboxing](case-studies/22-ephemeral-microvm-agentic-sandbox/README.md) | Firecracker hardware-assisted KVM isolation, sub-5ms Copy-on-Write memory snapshots, host eBPF syscall tracing, and network egress gating | 💡 Conceptualized |
| **23** | [Active Inference & Free-Energy Minimization](case-studies/23-active-inference-entropy-directed-backtracking/README.md) | Variational Free Energy, Expected Free Energy (EFE) decomposing into epistemic and instrumental value, and entropy-directed tree backtracking | 💡 Conceptualized |
| **24** | [Speculative Tool Pipelining across Multi-MCP](case-studies/24-speculative-pre-computation-multi-mcp/README.md) | Breaking the sequential execution wall: streaming token prefix branch prediction, speculative shadow leases, and transactional rollback | 💡 Conceptualized |
| **25** | [Byzantine-Fault-Tolerant Consensus Swarms](case-studies/25-byzantine-fault-tolerant-consensus-swarms/README.md) | $3f + 1$ quorum thresholds, confidence-weighted Self-Anchored Consensus (SAC), cryptographic vote aggregation, and adversarial filtering | 💡 Conceptualized |
| **26** | [Thinking Before Thinking: Agentic Meta-Reasoning](case-studies/26-agentic-meta-reasoning-thinking-before-thinking/README.md) | Decoupled 4-stage metacognitive control loop (Assess, Propose, Evaluate, Dispatch), persistent DAG artifact memory, Type-2 AUC self-monitoring, and inference scaling | 💡 Conceptualized |
| **27** | [Autonomous Reflection Loops & Directed Graph Backtracking](case-studies/27-autonomous-reflection-loops-graph-backtracking/README.md) | Trajectory DAGs, causal error categorization, clean context pruning, and negative constraint ledgers | 💡 Conceptualized |
---

## 🧭 Upcoming Case Study Brainstorms

- **Multi-Agent Orchestration & Protocol Handoffs**: Standardized protocols (A2A) vs shared blackboard state machines.
- **Human-in-the-Loop (HITL) Gateways**: Non-blocking asynchronous approvals and safety checkpoints.
- **Hierarchical Self-Play & Synthetic Trajectory Distillation**: Automated bootstrapping of specialized worker policies.
- **Agentic Sandboxing & Tool Boundary Security**: Isolating arbitrary code and CLI execution in local/edge runtimes.

---

## 📄 License

MIT License.
