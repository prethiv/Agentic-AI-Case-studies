"""
Autonomous Specialist Worker Agent Implementation.
Features calibrated bidding on Contract Net tasks, scoped tool execution with HandoffTokens,
and stigmergic interaction via the shared blackboard.
"""

from __future__ import annotations
import asyncio
import time
import uuid
from typing import Any, Callable, Dict, List, Optional
from protocol import TaskSpec, Bid, Award, HandoffToken
from blackboard import StigmergicBlackboard, ConcurrencyConflictError


class SpecialistWorker:
    """
    Autonomous worker specialized in specific cognitive domains.
    Reacts to blackboard updates and bids on tasks matching its capability profile.
    """

    def __init__(
        self,
        worker_id: str,
        domain_name: str,
        capabilities: Dict[str, float],  # capability_name -> calibrated confidence [0.0, 1.0]
        blackboard: StigmergicBlackboard,
        base_latency_ms: float = 800.0,
        base_token_cost: int = 1200,
        allowed_tools: Optional[List[str]] = None,
    ):
        self.worker_id = worker_id
        self.domain_name = domain_name
        self.capabilities = capabilities
        self.blackboard = blackboard
        self.base_latency_ms = base_latency_ms
        self.base_token_cost = base_token_cost
        self.allowed_tools = allowed_tools or ["read_blackboard", "write_blackboard"]
        self.active_tasks: Dict[str, TaskSpec] = {}

    def compute_bid(self, task: TaskSpec, w_conf: float = 0.6, w_lat: float = 0.2, w_cost: float = 0.2) -> Bid:
        """
        Evaluate a TaskSpec against specialized capabilities and return a Contract Net Bid.
        """
        # Determine capability match: average confidence across requested capabilities
        matched_scores = [self.capabilities.get(req, 0.0) for req in task.required_capabilities]
        avg_conf = sum(matched_scores) / len(matched_scores) if matched_scores else 0.0

        # Estimate latency and cost based on priority and capability
        complexity_mult = 1.0 + (task.priority * 0.15)
        est_lat = self.base_latency_ms * complexity_mult
        est_cost = int(self.base_token_cost * complexity_mult)

        # Normalize components against task max bounds
        norm_lat = min(1.0, est_lat / max(1.0, task.max_latency_ms))
        norm_cost = min(1.0, est_cost / max(1, task.max_cost_tokens))

        # Composite valuation
        score = (w_conf * avg_conf) - (w_lat * norm_lat) - (w_cost * norm_cost)

        rationale = (
            f"{self.worker_id} ({self.domain_name}): avg_conf={avg_conf:.2f}, "
            f"est_lat={est_lat:.0f}ms, est_cost={est_cost}tok"
        )

        return Bid(
            bid_id=str(uuid.uuid4())[:8],
            task_id=task.task_id,
            worker_id=self.worker_id,
            capability_confidence=round(avg_conf, 3),
            estimated_latency_ms=round(est_lat, 1),
            estimated_cost_tokens=est_cost,
            bid_score=round(score, 4),
            rationale=rationale,
        )

    async def execute_task(
        self,
        task: TaskSpec,
        handoff_token: Optional[HandoffToken] = None,
        execution_payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute task, validating authority via HandoffToken if provided.
        Publishes observations and artifacts to the shared blackboard.
        """
        if handoff_token:
            if not handoff_token.verify():
                raise PermissionError(f"Worker {self.worker_id} rejected invalid or tampered HandoffToken.")
            # Verify depth constraints
            if handoff_token.depth > 3:
                raise PermissionError(f"Worker {self.worker_id} rejected task exceeding max delegation depth.")

        # Simulate execution latency
        await asyncio.sleep(0.05)

        # Produce domain-specific artifact
        output_data = {
            "task_id": task.task_id,
            "worker_id": self.worker_id,
            "domain": self.domain_name,
            "status": "COMPLETED",
            "findings": execution_payload.get("raw_data") if execution_payload else "Processed default payload",
            "analyzed_at_ts": time.time(),
        }

        # Write to stigmergic blackboard with retry on concurrency conflict
        key = f"artifacts/{task.task_id}"
        written = False
        retries = 3
        while not written and retries > 0:
            try:
                existing = await self.blackboard.read(key)
                expected_ver = existing.version if existing else None
                await self.blackboard.write(
                    key=key,
                    value=output_data,
                    author_agent_id=self.worker_id,
                    expected_version=expected_ver,
                    tags=["artifact", self.domain_name, task.mission_id],
                )
                written = True
            except ConcurrencyConflictError:
                retries -= 1
                await asyncio.sleep(0.01)

        task.status = "COMPLETED"
        return output_data
