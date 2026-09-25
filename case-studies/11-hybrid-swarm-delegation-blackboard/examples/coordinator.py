"""
Hierarchical Mission Coordinator & Contract Net Auction Engine.
Manages strategic planning, DAG-based task delegation, cycle/deadlock prevention, and auction resolution.
"""

from __future__ import annotations
import asyncio
import uuid
import time
from typing import Dict, List, Optional, Set, Tuple
from protocol import TaskSpec, Bid, Award, HandoffToken
from blackboard import StigmergicBlackboard


class CyclicDelegationError(Exception):
    """Raised when a proposed delegation would introduce a directed cycle."""
    pass


class MaxDepthExceededError(Exception):
    """Raised when delegation depth exceeds maximum configured threshold."""
    pass


class MissionCoordinator:
    """
    Strategic Layer: Oversees high-level mission goals, enforces strict DAG invariants,
    conducts Contract Net Protocol (CNP) auctions, and synthesizes swarm output.
    """

    def __init__(
        self,
        coordinator_id: str,
        blackboard: StigmergicBlackboard,
        max_delegation_depth: int = 3,
        total_token_budget: int = 50000,
        w_conf: float = 0.6,
        w_latency: float = 0.2,
        w_cost: float = 0.2,
    ):
        self.coordinator_id = coordinator_id
        self.blackboard = blackboard
        self.max_delegation_depth = max_delegation_depth
        self.total_token_budget = total_token_budget
        self.consumed_tokens = 0

        # Weights for Contract Net bid scoring
        self.w_conf = w_conf
        self.w_latency = w_latency
        self.w_cost = w_cost

        # Delegation tracking graph: parent_agent -> set of child_agents
        self.delegation_graph: Dict[str, Set[str]] = {}
        # Task tracking
        self.tasks: Dict[str, TaskSpec] = {}
        self.task_assignments: Dict[str, str] = {}  # task_id -> worker_id

    def register_delegation(self, from_agent: str, to_agent: str, current_depth: int) -> None:
        """
        Record and validate a delegation edge.
        Enforces DAG invariant (no cycles) and depth ceiling.
        """
        if current_depth >= self.max_delegation_depth:
            raise MaxDepthExceededError(
                f"Delegation from {from_agent} to {to_agent} at depth {current_depth} "
                f"exceeds max depth ceiling of {self.max_delegation_depth}."
            )

        # Check if adding edge (from_agent -> to_agent) would introduce a cycle
        if self._would_create_cycle(from_agent, to_agent):
            raise CyclicDelegationError(
                f"Cyclic delegation rejected: {from_agent} -> {to_agent} would create an infinite delegation loop."
            )

        if from_agent not in self.delegation_graph:
            self.delegation_graph[from_agent] = set()
        self.delegation_graph[from_agent].add(to_agent)

    def _would_create_cycle(self, from_agent: str, to_agent: str) -> bool:
        """DFS reachability test: if to_agent can reach from_agent, adding edge causes cycle."""
        if from_agent == to_agent:
            return True

        visited: Set[str] = set()
        stack = [to_agent]

        while stack:
            curr = stack.pop()
            if curr == from_agent:
                return True
            if curr not in visited:
                visited.add(curr)
                neighbors = self.delegation_graph.get(curr, set())
                stack.extend(neighbors - visited)
        return False

    def conduct_auction(self, task: TaskSpec, bids: List[Bid]) -> Optional[Award]:
        """
        Evaluate bids submitted by worker agents according to the multi-criteria valuation function:
        BidScore = w_conf * Conf - w_lat * (Lat / MaxLat) - w_cost * (Cost / MaxCost)
        """
        if not bids:
            return None

        valid_bids = [b for b in bids if b.task_id == task.task_id and b.capability_confidence > 0.0]
        if not valid_bids:
            return None

        # Sort descending by bid_score
        valid_bids.sort(key=lambda b: b.bid_score, reverse=True)
        winner = valid_bids[0]

        award = Award(
            award_id=str(uuid.uuid4())[:8],
            task_id=task.task_id,
            worker_id=winner.worker_id,
            winning_bid_score=winner.bid_score,
            agreed_cost_tokens=winner.estimated_cost_tokens,
        )

        self.task_assignments[task.task_id] = winner.worker_id
        self.consumed_tokens += winner.estimated_cost_tokens
        task.status = "ASSIGNED"
        return award

    def mint_handoff_token(
        self,
        mission_id: str,
        source_agent_id: str,
        target_agent_id: str,
        task_id: str,
        depth: int,
        allowed_tools: List[str],
        epistemic_summary: str,
        immutable_constraints: List[str],
    ) -> HandoffToken:
        """Create a cryptographically verifiable token representing authorized subagent delegation."""
        token = HandoffToken(
            token_id=str(uuid.uuid4())[:8],
            mission_id=mission_id,
            source_agent_id=source_agent_id,
            target_agent_id=target_agent_id,
            task_id=task_id,
            depth=depth,
            allowed_tools=allowed_tools,
            epistemic_summary=epistemic_summary,
            immutable_constraints=immutable_constraints,
        )
        return token
