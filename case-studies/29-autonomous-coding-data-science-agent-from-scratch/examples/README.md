# Case Study 29: Reference Architecture Implementation

This folder contains a fully functional, zero-framework reference implementation of an **Autonomous Coding (SWE) and Data Science (DS) Agent Core** built from first principles.

---

## 🚀 Quickstart

Run the demonstration immediately using Python 3.8+ (no API keys or external services required):

```bash
python agent_core.py
```

### What the Demo Executes:
1. **Autonomous SWE Agent Run**:
   - Spawns an isolated mock workspace containing an authentication service with an unhandled exception bug.
   - Decomposes the task into an execution DAG.
   - Reads the target file using `read_file`.
   - Attempts a patch that triggers an AST syntax error (`SyntaxError: expected ':'`).
   - The **AST Verification Gate** intercepts and blocks the destructive filesystem mutation.
   - The agent ingests the syntax error, reflects, repairs the patch, and applies the verified fix.
2. **Autonomous Data Science Agent Run**:
   - Launches a **Stateful In-Memory Kernel Session**.
   - Ingests raw data with missing values, printing shape and null counts.
   - Retains state across turns without re-running data loaders.
   - Imputes null values, tracks active variables in the memory namespace, and saves an analytical report artifact to disk.

---

## 📁 Architecture Overview

```text
examples/
├── agent_core.py        # Core autonomous agent runtime (Zero-framework)
│   ├── State Models     # PlanStep, ToolCall, AgentMessage, AgentMode
│   ├── Token Economics  # ObservationCompactor (traceback and stdout truncation)
│   ├── Toolboxes        # SWEToolbox (Surgical search/replace + AST verification)
│   ├── Sandboxed Kernel # StatefulDataScienceKernel (ZeroMQ-style namespace & artifacts)
│   ├── LLM Provider     # MockAutonomousAgentLLM + OpenAICompatibleProvider interface
│   └── Agent Engine     # AutonomousAgent dual-loop state machine
└── README.md            # Execution and extension guide
```

---

## 🛠️ Extending to Live LLMs (Ollama / vLLM / OpenAI)

To connect `agent_core.py` to a live model (e.g., local `deepseek-r1`, `qwen2.5-coder:32b`, or OpenAI `gpt-4o`), implement the `LLMProvider` interface:

```python
import json
import urllib.request
from agent_core import LLMProvider, AgentMessage, ToolCall

class LiveOpenAICompatibleProvider(LLMProvider):
    def __init__(self, base_url: str = "http://localhost:11434/v1", api_key: str = "ollama", model: str = "qwen2.5-coder"):
        self.base_url = base_url
        self.api_key = api_key
        self.model = model

    def generate(self, messages, tools):
        # Format payload conforming to OpenAI /v1/chat/completions
        payload = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": 0.0
        }
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"}
        )
        with urllib.request.urlopen(req) as response:
            res_data = json.loads(response.read().decode())
            content = res_data["choices"][0]["message"]["content"]
            return AgentMessage(role="assistant", content=content)
```
