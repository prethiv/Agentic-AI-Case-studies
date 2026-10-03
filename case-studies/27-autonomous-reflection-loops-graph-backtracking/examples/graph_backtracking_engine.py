"""
Executable Reference Implementation for Case Study 27:
Autonomous Reflection Loops & Directed Graph Backtracking (Anti-Loop Budgeting).

Demonstrates:
- Trajectory Tree DAG with node checkpointing and causal ancestry
- Semantic Error Classification (Transient, Syntactic, Semantic Dead-End, Permission Denied)
- Causal Graph Backtracking with subtree pruning and negative constraint ledger injection
- Anti-Loop Budgeting (step budget + global cumulative token tracking)
- Circuit Breaker against backtracking thrashing (depth and rollback frequency limits)
- Compensating undo actions (Saga-pattern rollback for state-mutating external tools)
- Clean context window reconstruction without token bloat or stack trace poisoning
"""

from __future__ import annotations

import dataclasses
from enum import Enum
import hashlib
import json
import logging
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
import uuid
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("GraphBacktrackingEngine")


class ErrorClass(str, Enum):
    TRANSIENT = "TRANSIENT"
    SYNTACTIC = "SYNTACTIC"
    SEMANTIC_DEAD_END = "SEMANTIC_DEAD_END"
    PERMISSION_DENIED = "PERMISSION_DENIED"


class CompensatingAction(BaseModel):
    """Represents a compensation or undo operation for external mutations."""
    tool_name: str
    arguments: Dict[str, Any]
    description: str


class NegativeConstraint(BaseModel):
    """An immutable invalidation vector preventing the agent from retrying failed branches."""
    invalidated_hypothesis: str
    failed_tool: str
    invalid_argument_patterns: Dict[str, Any]
    argument_hash: str
    causal_reason: str
    invalidation_scope: str = "EXACT_ARGUMENTS"  # 'EXACT_ARGUMENTS' or 'TOOL_TARGET'
    timestamp: float = Field(default_factory=time.time)

    def matches(self, tool_name: str, arguments: Dict[str, Any]) -> bool:
        """Determines whether a proposed action violates this negative constraint."""
        if tool_name != self.failed_tool:
            return False
        if self.invalidation_scope == "TOOL_TARGET":
            return True
        arg_hash = hashlib.sha256(json.dumps(arguments, sort_keys=True).encode("utf-8")).hexdigest()[:16]
        return arg_hash == self.argument_hash


class TrajectoryNode(BaseModel):
    """An immutable node in the trajectory execution graph."""
    node_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    parent_id: Optional[str] = None
    step_depth: int = 0
    hypothesis: str
    action_tool_name: str
    action_arguments: Dict[str, Any]
    observation: Optional[str] = None
    error_class: Optional[ErrorClass] = None
    cumulative_tokens: int = 0
    step_tokens: int = 0
    is_terminal: bool = False
    is_pruned: bool = False
    children_ids: List[str] = Field(default_factory=list)
    compensating_actions: List[CompensatingAction] = Field(default_factory=list)
    timestamp: float = Field(default_factory=time.time)


class TrajectoryTreeEngine:
    """
    Manages the Directed Acyclic Graph (DAG) of agent states, enforcing anti-loop budgeting,
    causal backtracking, negative constraint generation, and clean context reconstruction.
    """

    def __init__(
        self,
        max_step_budget: int = 15,
        max_cost_tokens: int = 25_000,
        max_rollbacks_per_ancestor: int = 3,
        max_global_rollbacks: int = 5,
    ):
        self.nodes: Dict[str, TrajectoryNode] = {}
        self.negative_constraints: List[NegativeConstraint] = []
        self.active_leaf_id: Optional[str] = None
        self.max_step_budget = max_step_budget
        self.max_cost_tokens = max_cost_tokens
        self.max_rollbacks_per_ancestor = max_rollbacks_per_ancestor
        self.max_global_rollbacks = max_global_rollbacks
        
        # Telemetry and circuit breakers
        self.rollback_counts: Dict[str, int] = {}
        self.total_rollbacks: int = 0
        self.total_tokens_consumed: int = 0
        self.tokens_wasted_on_pruned_branches: int = 0
        self.compensation_log: List[str] = []

    def register_step(
        self,
        hypothesis: str,
        tool: str,
        arguments: Dict[str, Any],
        step_token_cost: int = 350,
        compensating_action: Optional[CompensatingAction] = None,
    ) -> str:
        """
        Registers a new state node in the trajectory tree under the active leaf.
        Validates anti-loop budgets and negative constraints before creating the node.
        """
        # 1. Check against active negative constraints
        for constraint in self.negative_constraints:
            if constraint.matches(tool, arguments):
                raise ValueError(
                    f"Blocked by Negative Constraint: Proposed action {tool}({arguments}) violates invalidation vector "
                    f"derived from failed hypothesis '{constraint.invalidated_hypothesis}'. Reason: {constraint.causal_reason}"
                )

        parent = self.nodes.get(self.active_leaf_id) if self.active_leaf_id else None
        parent_depth = parent.step_depth if parent else 0
        cumulative = (parent.cumulative_tokens if parent else 0) + step_token_cost
        self.total_tokens_consumed += step_token_cost

        # 2. Enforce Anti-Loop Budget thresholds
        if parent_depth + 1 > self.max_step_budget:
            raise RuntimeError(
                f"Anti-Loop Step Budget Exceeded: Max depth {self.max_step_budget} reached. Halting trajectory to prevent runaways."
            )

        if self.total_tokens_consumed > self.max_cost_tokens:
            raise RuntimeError(
                f"Anti-Loop Token Cost Ceiling Exceeded: Cumulative tokens {self.total_tokens_consumed} > {self.max_cost_tokens}. Halting execution."
            )

        node = TrajectoryNode(
            parent_id=self.active_leaf_id,
            step_depth=parent_depth + 1,
            hypothesis=hypothesis,
            action_tool_name=tool,
            action_arguments=arguments,
            cumulative_tokens=cumulative,
            step_tokens=step_token_cost,
        )

        if compensating_action:
            node.compensating_actions.append(compensating_action)

        self.nodes[node.node_id] = node
        if parent:
            parent.children_ids.append(node.node_id)
        self.active_leaf_id = node.node_id

        logger.info(
            "Registered Node [%s] (Depth %d, Cumulative Tokens: %d): Action '%s'",
            node.node_id,
            node.step_depth,
            cumulative,
            tool,
        )
        return node.node_id

    def record_observation(
        self,
        node_id: str,
        observation: str,
        error_class: Optional[ErrorClass] = None,
        tool_executor_callback: Optional[Callable[[str, Dict[str, Any]], Any]] = None,
        distilled_reason: Optional[str] = None,
    ) -> bool:
        """
        Records the environment response for a given node.
        If a SEMANTIC_DEAD_END is detected, triggers immediate causal graph backtracking.
        Returns True if trajectory continues normally, False if backtracked.
        """
        node = self.nodes[node_id]
        node.observation = observation
        node.error_class = error_class

        if error_class == ErrorClass.SEMANTIC_DEAD_END:
            logger.warning(
                "Semantic Dead-End detected on Node [%s]. Initiating Causal Graph Backtrack.",
                node_id,
            )
            reason = distilled_reason or observation.split("\n")[0][:120]
            self.backtrack(node_id, reason=reason, tool_executor_callback=tool_executor_callback)
            return False
        
        return True

    def backtrack(
        self,
        failed_node_id: str,
        reason: str,
        tool_executor_callback: Optional[Callable[[str, Dict[str, Any]], Any]] = None,
    ):
        """
        Rewinds the active trajectory to the nearest valid ancestor node.
        Prunes the failed subtree, executes compensating actions (undo), records negative constraints,
        and checks circuit breakers against thrashing.
        """
        failed_node = self.nodes[failed_node_id]
        ancestor_id = failed_node.parent_id

        # 1. Circuit breaker: Check rollback count for this ancestor
        rollback_key = ancestor_id or "ROOT"
        curr_rollbacks = self.rollback_counts.get(rollback_key, 0) + 1
        self.rollback_counts[rollback_key] = curr_rollbacks
        self.total_rollbacks += 1

        if curr_rollbacks > self.max_rollbacks_per_ancestor:
            raise RuntimeError(
                f"Backtracking Thrashing Detected: Ancestor [{rollback_key}] has exhausted its rollback limit "
                f"({curr_rollbacks} > {self.max_rollbacks_per_ancestor}). Agent is cycling without viable alternatives."
            )

        if self.total_rollbacks > self.max_global_rollbacks:
            raise RuntimeError(
                f"Global Backtracking Limit Exceeded: {self.total_rollbacks} rollbacks performed across all branches. Trajectory terminated."
            )

        # 2. Prune the failed subtree and execute compensating actions
        pruned_nodes = self._prune_subtree(failed_node_id, tool_executor_callback)

        # 3. Calculate wasted tokens on pruned branch
        wasted = sum(n.step_tokens for n in pruned_nodes)
        self.tokens_wasted_on_pruned_branches += wasted

        # 4. Generate structured Negative Constraint with exact argument hashing
        arg_hash = hashlib.sha256(
            json.dumps(failed_node.action_arguments, sort_keys=True).encode("utf-8")
        ).hexdigest()[:16]

        constraint = NegativeConstraint(
            invalidated_hypothesis=failed_node.hypothesis,
            failed_tool=failed_node.action_tool_name,
            invalid_argument_patterns=failed_node.action_arguments,
            argument_hash=arg_hash,
            causal_reason=reason,
            invalidation_scope="EXACT_ARGUMENTS",
        )
        self.negative_constraints.append(constraint)

        # 5. Rewind active leaf pointer to ancestor
        self.active_leaf_id = ancestor_id

        logger.info(
            "Backtracked from [%s] to ancestor [%s]. Pruned %d nodes (%d wasted tokens). Active constraints: %d",
            failed_node_id,
            ancestor_id,
            len(pruned_nodes),
            wasted,
            len(self.negative_constraints),
        )

    def _prune_subtree(
        self,
        root_node_id: str,
        tool_executor_callback: Optional[Callable[[str, Dict[str, Any]], Any]] = None,
    ) -> List[TrajectoryNode]:
        """Recursively marks all nodes in the subtree as pruned and executes undo actions in reverse order."""
        pruned: List[TrajectoryNode] = []
        queue = [root_node_id]

        while queue:
            nid = queue.pop(0)
            node = self.nodes[nid]
            node.is_pruned = True
            pruned.append(node)
            queue.extend(node.children_ids)

        # Execute compensating actions in reverse topological order (LIFO)
        for node in reversed(pruned):
            for comp in reversed(node.compensating_actions):
                msg = f"Executing Compensation: {comp.tool_name}({comp.arguments}) - {comp.description}"
                logger.info(msg)
                self.compensation_log.append(msg)
                if tool_executor_callback:
                    tool_executor_callback(comp.tool_name, comp.arguments)

        return pruned

    def build_clean_context_window(self, system_instruction: str = "") -> List[Dict[str, str]]:
        """
        Reconstructs the active prompt context from the root to the active leaf.
        Only unpruned, valid ancestor nodes are retained—completely eliminating stack trace bloat.
        Appends the synthesized Negative Constraint Ledger as an authoritative system guard.
        """
        active_path: List[TrajectoryNode] = []
        curr_id = self.active_leaf_id

        while curr_id:
            node = self.nodes[curr_id]
            if not node.is_pruned:
                active_path.append(node)
            curr_id = node.parent_id

        active_path.reverse()

        messages: List[Dict[str, str]] = []

        # Autoritative system instruction
        base_system = system_instruction or "You are an autonomous problem-solving agent with causal graph backtracking."
        
        # Inject Negative Constraint Ledger into system prompt
        if self.negative_constraints:
            ledger_lines = [
                f"- AVOID tool '{c.failed_tool}' with args {c.invalid_argument_patterns} | Failure: {c.causal_reason}"
                for c in self.negative_constraints
            ]
            constraint_text = "\n".join(ledger_lines)
            full_system = (
                f"{base_system}\n\n"
                f"### CRITICAL NEGATIVE CONSTRAINT LEDGER (PRUNED DEAD-ENDS):\n"
                f"The following execution trajectories were formally disproven. Do not attempt them:\n"
                f"{constraint_text}"
            )
        else:
            full_system = base_system

        messages.append({"role": "system", "content": full_system})

        # Reconstruct clean linear history of verified steps only
        for step in active_path:
            messages.append({
                "role": "assistant",
                "content": f"Thought: {step.hypothesis}\nAction: {step.action_tool_name}({json.dumps(step.action_arguments)})",
            })
            if step.observation:
                messages.append({
                    "role": "user",
                    "content": f"Observation: {step.observation}",
                })

        return messages

    def get_summary_metrics(self) -> Dict[str, Any]:
        """Returns runtime telemetry for anti-loop budgeting and backtracking performance."""
        return {
            "total_nodes_created": len(self.nodes),
            "active_path_length": len([n for n in self.nodes.values() if not n.is_pruned]),
            "pruned_nodes_count": len([n for n in self.nodes.values() if n.is_pruned]),
            "total_rollbacks": self.total_rollbacks,
            "negative_constraints_active": len(self.negative_constraints),
            "total_tokens_consumed": self.total_tokens_consumed,
            "tokens_wasted_on_pruned_branches": self.tokens_wasted_on_pruned_branches,
            "context_token_saving_ratio": (
                round(self.tokens_wasted_on_pruned_branches / max(1, self.total_tokens_consumed), 3)
            ),
            "compensation_actions_executed": len(self.compensation_log),
        }


def run_database_migration_backtracking_scenario():
    """
    Simulates a production scenario:
    An agent tasked with running an enterprise database migration encounters:
    1. Step 1 (Safe): Inspect database schema (Success)
    2. Step 2 (Flawed): Drop foreign key index directly without lock release (Dead-End Error)
       -> Triggers Causal Graph Backtrack, prunes node, stores Negative Constraint.
    3. Step 3 (Blocked): Agent tries repeating near-identical dropped index (Constraint prevents execution!)
    4. Step 4 (Correct Alternate Branch): Acquire advisory lock, create shadow copy, safely swap pointer (Success)
    """
    logger.info("================================================================================")
    logger.info("STARTING CASE STUDY 27 VERIFICATION: AUTONOMOUS REFLECTION & GRAPH BACKTRACKING")
    logger.info("================================================================================")

    engine = TrajectoryTreeEngine(
        max_step_budget=10,
        max_cost_tokens=15_000,
        max_rollbacks_per_ancestor=3,
        max_global_rollbacks=5,
    )

    # Simulated external tool callback for compensations
    external_state = {"locks": [], "tables": ["users", "orders"], "shadow_tables": []}

    def tool_callback(tool_name: str, args: Dict[str, Any]):
        if tool_name == "release_advisory_lock":
            lock_id = args.get("lock_id")
            if lock_id in external_state["locks"]:
                external_state["locks"].remove(lock_id)
                logger.info("--> [Tool Executor] Successfully released lock: %s", lock_id)
        elif tool_name == "drop_table":
            table = args.get("table")
            if table in external_state["shadow_tables"]:
                external_state["shadow_tables"].remove(table)
                logger.info("--> [Tool Executor] Cleaned up shadow table: %s", table)

    # ---------------------------------------------------------
    # STEP 1: Inspect DB Schema (Deterministic Success)
    # ---------------------------------------------------------
    step1_id = engine.register_step(
        hypothesis="Inspect current table constraints on 'orders' table to prepare index rebuild.",
        tool="inspect_schema",
        arguments={"table": "orders"},
        step_token_cost=420,
    )
    engine.record_observation(
        node_id=step1_id,
        observation="Table 'orders' has foreign key constraint 'fk_user_id' referencing 'users(id)'. Active write load detected.",
        error_class=None,
    )

    # ---------------------------------------------------------
    # STEP 2: Flawed Action - In-Place Index Drop without lock
    # ---------------------------------------------------------
    step2_id = engine.register_step(
        hypothesis="Drop foreign key constraint 'fk_user_id' directly to speed up batch re-indexing.",
        tool="drop_constraint",
        arguments={"table": "orders", "constraint": "fk_user_id", "cascade": False},
        step_token_cost=650,
        compensating_action=CompensatingAction(
            tool_name="release_advisory_lock",
            arguments={"lock_id": "migration_phase_1"},
            description="Release partial migration lock if aborted",
        ),
    )
    external_state["locks"].append("migration_phase_1")

    # Tool execution returns a fatal dead-end error (deadlock / entity busy)
    engine.record_observation(
        node_id=step2_id,
        observation="FATAL DEADLOCK: PostgresException 40P01: Deadlock detected while waiting for ExclusiveLock on relation 'orders'. "
                    "Cannot drop active foreign key under live write load.",
        error_class=ErrorClass.SEMANTIC_DEAD_END,
        distilled_reason="ExclusiveLock deadlock on relation 'orders' under live write load",
        tool_executor_callback=tool_callback,
    )

    # Verify that the active leaf rewound back to Step 1
    assert engine.active_leaf_id == step1_id, f"Expected active leaf {step1_id}, got {engine.active_leaf_id}"
    assert len(engine.negative_constraints) == 1, "Expected exactly 1 negative constraint recorded"
    logger.info("Verification Passed: Engine successfully rewound active leaf to [%s]", step1_id)

    # ---------------------------------------------------------
    # STEP 3: Degenerative Loop Prevention Test
    # If the model naively proposes the exact same failing action again, the engine halts it!
    # ---------------------------------------------------------
    try:
        engine.register_step(
            hypothesis="Retry dropping foreign key constraint with same parameters.",
            tool="drop_constraint",
            arguments={"table": "orders", "constraint": "fk_user_id", "cascade": False},
            step_token_cost=500,
        )
        raise AssertionError("Engine failed to block prohibited negative constraint action!")
    except ValueError as e:
        logger.info("Verified Degenerative Loop Interception: %s", str(e))

    # ---------------------------------------------------------
    # STEP 4: Fresh Alternate Solution Branch
    # Explore valid non-blocking shadow table strategy
    # ---------------------------------------------------------
    step4_id = engine.register_step(
        hypothesis="Create concurrent shadow index 'orders_idx_user_concurrent' without exclusive locking.",
        tool="create_index_concurrently",
        arguments={"table": "orders", "column": "user_id", "index_name": "orders_idx_user_concurrent"},
        step_token_cost=480,
    )
    engine.record_observation(
        node_id=step4_id,
        observation="Index 'orders_idx_user_concurrent' created concurrently in 1.42s without table lock. Migration complete.",
        error_class=None,
    )

    # ---------------------------------------------------------
    # STEP 5: Validate Clean Context Reconstruction
    # Verify that the failed attempt's 500-token stack trace is NOT in the prompt!
    # ---------------------------------------------------------
    clean_context = engine.build_clean_context_window(
        system_instruction="You are an enterprise SRE autonomous database migration agent."
    )

    logger.info("\n--- RECONSTRUCTED CLEAN CONTEXT WINDOW ---")
    for idx, msg in enumerate(clean_context):
        logger.info("[%d] Role: %s | Content Length: %d chars", idx, msg["role"], len(msg["content"]))
        logger.info("    Excerpt: %s", msg["content"][:180].replace("\n", " "))

    # Verify context integrity
    system_msg = clean_context[0]["content"]
    assert "CRITICAL NEGATIVE CONSTRAINT LEDGER" in system_msg
    assert "AVOID tool 'drop_constraint'" in system_msg
    
    # Assert that no failed stack trace is in assistant or user messages
    dialog_messages = [msg["content"] for msg in clean_context if msg["role"] != "system"]
    assert not any("FATAL DEADLOCK" in m for m in dialog_messages), "Error: Stack trace leaked into active conversation history!"
    assert not any("drop_constraint" in m for m in dialog_messages), "Error: Pruned action leaked into active conversation history!"
    assert step2_id not in [msg["content"] for msg in clean_context]

    metrics = engine.get_summary_metrics()
    logger.info("\n--- RUNTIME TELEMETRY METRICS ---")
    logger.info(json.dumps(metrics, indent=2))

    assert metrics["total_nodes_created"] == 3
    assert metrics["pruned_nodes_count"] == 1
    assert metrics["total_rollbacks"] == 1
    assert metrics["tokens_wasted_on_pruned_branches"] == 650
    assert len(external_state["locks"]) == 0, "Compensating action failed to release external lock!"

    logger.info("================================================================================")
    logger.info("ALL GRAPH BACKTRACKING VERIFICATION ASSERTIONS PASSED SUCCESSFULLY!")
    logger.info("================================================================================")


if __name__ == "__main__":
    run_database_migration_backtracking_scenario()
