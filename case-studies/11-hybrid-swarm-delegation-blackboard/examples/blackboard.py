"""
Stigmergic Shared Blackboard Engine with Optimistic Concurrency & Pheromone Decay.
Allows worker agents to coordinate asynchronously through environment-mediated state changes.
"""

from __future__ import annotations
import asyncio
import time
import uuid
from typing import Any, Callable, Dict, List, Optional, Set
from protocol import BlackboardEntry, StateDelta


class ConcurrencyConflictError(Exception):
    """Raised when an agent attempts to mutate an entry whose version has drifted."""
    pass


class StigmergicBlackboard:
    """
    Asynchronous event-sourced shared memory board implementing Stigmergy:
    Agents do not communicate peer-to-peer; they react to and mutate environment state.
    """

    def __init__(self, evaporation_rate: float = 0.05):
        self._entries: Dict[str, BlackboardEntry] = {}
        self._deltas: List[StateDelta] = []
        self._subscribers: Dict[str, List[Callable[[StateDelta, BlackboardEntry], Any]]] = {}
        self._lock = asyncio.Lock()
        self.evaporation_rate = evaporation_rate  # rho: rate at which pheromones decay per tick

    async def write(
        self,
        key: str,
        value: Any,
        author_agent_id: str,
        expected_version: Optional[int] = None,
        pheromone_urgency: float = 1.0,
        tags: Optional[List[str]] = None,
    ) -> BlackboardEntry:
        """
        Write or update a blackboard key with optimistic concurrency check.
        If expected_version is provided and differs from stored version, raises ConcurrencyConflictError.
        """
        async with self._lock:
            existing = self._entries.get(key)
            prev_ver = existing.version if existing else 0

            if expected_version is not None and prev_ver != expected_version:
                raise ConcurrencyConflictError(
                    f"Version conflict on key '{key}': expected {expected_version}, but found {prev_ver}."
                )

            new_ver = prev_ver + 1
            now = time.time()
            tags_list = tags or (existing.tags if existing else [])

            entry = BlackboardEntry(
                entry_id=existing.entry_id if existing else str(uuid.uuid4())[:8],
                key=key,
                value=value,
                author_agent_id=author_agent_id,
                version=new_ver,
                pheromone_urgency=pheromone_urgency,
                tags=tags_list,
                created_at_ts=existing.created_at_ts if existing else now,
                updated_at_ts=now,
            )
            self._entries[key] = entry

            delta = StateDelta(
                delta_id=str(uuid.uuid4())[:8],
                key=key,
                previous_version=prev_ver,
                new_version=new_ver,
                patch_op="SET" if existing else "CREATE",
                author_agent_id=author_agent_id,
                timestamp=now,
                summary=f"Key '{key}' updated to v{new_ver} by {author_agent_id}",
            )
            self._deltas.append(delta)

            # Notify pattern subscribers asynchronously
            self._dispatch_events(delta, entry)
            return entry

    async def read(self, key: str) -> Optional[BlackboardEntry]:
        """Read current state of a key."""
        async with self._lock:
            return self._entries.get(key)

    async def query_by_tag(self, tag: str) -> List[BlackboardEntry]:
        """Find all entries containing a specific tag."""
        async with self._lock:
            return [e for e in self._entries.values() if tag in e.tags]

    async def get_all_entries(self) -> Dict[str, BlackboardEntry]:
        """Return a snapshot of all active blackboard entries."""
        async with self._lock:
            return dict(self._entries)

    async def apply_pheromone_evaporation(self) -> int:
        """
        Stigmergic Decay step: tau(t+1) = (1 - rho) * tau(t).
        Reduces urgency of unaddressed items to prevent stale locks.
        """
        async with self._lock:
            evaporated_count = 0
            for entry in self._entries.values():
                entry.pheromone_urgency = max(0.0, entry.pheromone_urgency * (1.0 - self.evaporation_rate))
                evaporated_count += 1
            return evaporated_count

    def subscribe(self, key_pattern: str, handler: Callable[[StateDelta, BlackboardEntry], Any]) -> None:
        """Register a reactive trigger for keys matching a prefix or wildcard."""
        if key_pattern not in self._subscribers:
            self._subscribers[key_pattern] = []
        self._subscribers[key_pattern].append(handler)

    def _dispatch_events(self, delta: StateDelta, entry: BlackboardEntry) -> None:
        """Notify any listeners matching key prefix or '*'."""
        for pattern, handlers in self._subscribers.items():
            if pattern == "*" or delta.key.startswith(pattern.rstrip("*")):
                for h in handlers:
                    try:
                        res = h(delta, entry)
                        if asyncio.iscoroutine(res):
                            asyncio.create_task(res)
                    except Exception as e:
                        print(f"[Blackboard Subscriber Error] handler failed for key '{delta.key}': {e}")

    def get_audit_trail(self) -> List[StateDelta]:
        """Return full event-sourced state-delta audit trail."""
        return list(self._deltas)
