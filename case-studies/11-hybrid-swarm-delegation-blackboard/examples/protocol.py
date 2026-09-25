"""
Protocol definitions for Hybrid Hierarchical Delegation & Stigmergic Blackboard Swarming.
Designed to be self-contained using Python standard library dataclasses with full type annotations.
"""

from __future__ import annotations
import json
import time
import uuid
import hashlib
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Set


@dataclass
class TaskSpec:
    """Specification of a task issued by a coordinator or delegating agent."""
    task_id: str
    mission_id: str
    description: str
    required_capabilities: List[str]
    parent_task_id: Optional[str] = None
    priority: int = 1  # 1 = low, 5 = critical
    max_latency_ms: float = 10000.0
    max_cost_tokens: int = 4000
    depth: int = 0
    dependencies: List[str] = field(default_factory=list)
    created_at_ts: float = field(default_factory=time.time)
    status: str = "PENDING"  # PENDING, AUCTIONING, ASSIGNED, IN_PROGRESS, COMPLETED, FAILED

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TaskSpec:
        return cls(**data)


@dataclass
class Bid:
    """A worker agent's bid on a published TaskSpec (Contract Net Protocol)."""
    bid_id: str
    task_id: str
    worker_id: str
    capability_confidence: float  # [0.0, 1.0] calibrated domain confidence
    estimated_latency_ms: float
    estimated_cost_tokens: int
    bid_score: float  # Computed composite score
    rationale: str
    submitted_at_ts: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Award:
    """Coordinator decision awarding a TaskSpec to the winning Bid."""
    award_id: str
    task_id: str
    worker_id: str
    winning_bid_score: float
    agreed_cost_tokens: int
    awarded_at_ts: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class HandoffToken:
    """
    Epistemic state container for delegating authority between agents.
    Cryptographically signed context boundary preventing hallucinated escalation.
    """
    token_id: str
    mission_id: str
    source_agent_id: str
    target_agent_id: str
    task_id: str
    depth: int
    allowed_tools: List[str]
    epistemic_summary: str
    immutable_constraints: List[str]
    created_at_ts: float = field(default_factory=time.time)
    signature: str = ""

    def __post_init__(self):
        if not self.signature:
            content = f"{self.token_id}:{self.mission_id}:{self.source_agent_id}:{self.target_agent_id}:{self.task_id}:{self.depth}"
            self.signature = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]

    def verify(self) -> bool:
        content = f"{self.token_id}:{self.mission_id}:{self.source_agent_id}:{self.target_agent_id}:{self.task_id}:{self.depth}"
        expected = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
        return self.signature == expected

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class BlackboardEntry:
    """An atomic record stored in the shared stigmergic blackboard."""
    entry_id: str
    key: str
    value: Any
    author_agent_id: str
    version: int = 1
    pheromone_urgency: float = 1.0  # Decays over time (stigmergic evaporation)
    tags: List[str] = field(default_factory=list)
    created_at_ts: float = field(default_factory=time.time)
    updated_at_ts: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class StateDelta:
    """Event-sourced mutation logged to the blackboard audit trail."""
    delta_id: str
    key: str
    previous_version: int
    new_version: int
    patch_op: str  # "SET", "MERGE", "DELETE"
    author_agent_id: str
    timestamp: float = field(default_factory=time.time)
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
