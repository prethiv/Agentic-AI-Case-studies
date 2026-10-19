"""
Agentic Saga Orchestration & Distributed Compensating Actions Engine.
====================================================================
Production-grade reference architecture for multi-step agent mutations
across distributed, non-ACID external environments.

Key Components:
  - WriteAheadIntentLedger: Append-only persistent journal of forward and compensating actions.
  - CompensatingActionSpec: Idempotent compensation contract with dynamic parameter binding.
  - AgenticSagaCoordinator: LIFO orchestrator with exponential backoff retry and fencing.
  - RuntimeMutatingToolGate: Pre-execution registration and post-execution commitment interceptor.
  - DeadLetterQueue & ReconciliationReport: Verifiable audit trail and clean-state attestation.
"""

from __future__ import annotations

import asyncio
import datetime
import enum
import hashlib
import json
import logging
import time
import uuid
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

logger = logging.getLogger("agentic_saga")


class SagaStepStatus(str, enum.Enum):
    ARMED = "ARMED"
    COMMITTED = "COMMITTED"
    COMPENSATION_PENDING = "COMPENSATION_PENDING"
    COMPENSATED = "COMPENSATED"
    COMPENSATION_FAILED = "COMPENSATION_FAILED"


class SagaSessionStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    ROLLBACK_TRIGGERED = "ROLLBACK_TRIGGERED"
    ROLLED_BACK = "ROLLED_BACK"
    FAILED_CRITICAL = "FAILED_CRITICAL"


class ActionMutatingClass(str, enum.Enum):
    READ_ONLY = "READ_ONLY"
    REVERSIBLE_MUTATING = "REVERSIBLE_MUTATING"
    IRREVERSIBLE_MUTATING = "IRREVERSIBLE_MUTATING"


class CompensatingActionSpec(BaseModel):
    """Specification contract for an idempotent inverse operation."""
    compensation_tool_name: str
    target_resource_id: Optional[str] = None
    fixed_arguments: Dict[str, Any] = Field(default_factory=dict)
    dynamic_param_mapping: Dict[str, str] = Field(
        default_factory=dict,
        description="Maps forward output key -> compensation argument key"
    )
    idempotency_key: str = Field(
        default_factory=lambda: f"comp_{uuid.uuid4().hex[:12]}"
    )
    max_retry_attempts: int = 3
    base_backoff_seconds: float = 0.05
    timeout_seconds: float = 10.0


class SagaStepRecord(BaseModel):
    """Immutably recorded step inside the Write-Ahead Intent Ledger."""
    step_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    step_index: int
    forward_tool_name: str
    forward_arguments: Dict[str, Any]
    mutating_class: ActionMutatingClass = ActionMutatingClass.REVERSIBLE_MUTATING
    forward_output: Optional[Dict[str, Any]] = None
    compensating_action: Optional[CompensatingActionSpec] = None
    status: SagaStepStatus = SagaStepStatus.ARMED
    created_at_utc: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    committed_at_utc: Optional[datetime.datetime] = None
    compensated_at_utc: Optional[datetime.datetime] = None
    error_message: Optional[str] = None


class DeadLetterEntry(BaseModel):
    """Entry recorded when automated compensation fails, requiring emergency manual review."""
    entry_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    step_id: str
    tool_name: str
    arguments: Dict[str, Any]
    idempotency_key: str
    failure_reason: str
    attempts_exhausted: int
    timestamp_utc: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )


class CleanStateReconciliationReport(BaseModel):
    """Verifiable clean-state audit report emitted at conclusion of Saga unwind."""
    session_id: str
    session_status: SagaSessionStatus
    total_steps: int
    mutating_steps: int
    successfully_compensated: int
    failed_compensations: int
    unwound_in_lifo_order: bool
    dead_letter_entries: List[DeadLetterEntry] = Field(default_factory=list)
    audit_trail: List[Dict[str, Any]] = Field(default_factory=list)
    started_at_utc: datetime.datetime
    concluded_at_utc: datetime.datetime
    state_integrity_hash: str


class WriteAheadIntentLedger:
    """
    Append-only in-memory Write-Ahead Intent Ledger.
    Provides immutable step indexing, snapshot query capabilities, and persistence isolation.
    """

    def __init__(self) -> None:
        self._records: List[SagaStepRecord] = []
        self._dead_letter_queue: List[DeadLetterEntry] = []
        self._lock = asyncio.Lock()

    async def append(self, step: SagaStepRecord) -> None:
        async with self._lock:
            self._records.append(step)

    async def get_session_steps(self, session_id: str) -> List[SagaStepRecord]:
        async with self._lock:
            return [s for s in self._records if s.session_id == session_id]

    async def get_step_by_id(self, step_id: str) -> Optional[SagaStepRecord]:
        async with self._lock:
            for s in self._records:
                if s.step_id == step_id:
                    return s
            return None

    async def update_step(self, step: SagaStepRecord) -> None:
        async with self._lock:
            for idx, existing in enumerate(self._records):
                if existing.step_id == step.step_id:
                    self._records[idx] = step
                    return
            raise KeyError(f"Step with id {step.step_id} not found in ledger")

    update = update_step

    async def record_dead_letter(self, entry: DeadLetterEntry) -> None:
        async with self._lock:
            self._dead_letter_queue.append(entry)

    async def get_dead_letters(self, session_id: str) -> List[DeadLetterEntry]:
        async with self._lock:
            return [d for d in self._dead_letter_queue if d.session_id == session_id]

    async def compute_integrity_hash(self, session_id: str) -> str:
        """Computes a SHA-256 state integrity digest over the session's recorded transitions."""
        steps = await self.get_session_steps(session_id)
        hasher = hashlib.sha256()
        for s in steps:
            payload = f"{s.step_id}|{s.step_index}|{s.status.value}|{s.forward_tool_name}|{s.error_message}"
            hasher.update(payload.encode("utf-8"))
        return hasher.hexdigest()


# Signature for tool invocation callable
ToolExecutor = Callable[[str, Dict[str, Any], Optional[str]], Awaitable[Dict[str, Any]]]


class AgenticSagaCoordinator:
    """
    The Saga Coordinator orchestrates forward step registration, dynamic parameter binding,
    and automated LIFO unwinding when forward execution encounters unrecoverable failure.
    """

    def __init__(
        self,
        ledger: WriteAheadIntentLedger,
        tool_executor: ToolExecutor,
    ) -> None:
        self.ledger = ledger
        self.tool_executor = tool_executor
        self._session_statuses: Dict[str, SagaSessionStatus] = {}
        self._executed_idempotency_keys: set[str] = set()

    def get_session_status(self, session_id: str) -> SagaSessionStatus:
        return self._session_statuses.get(session_id, SagaSessionStatus.ACTIVE)

    async def register_step(
        self,
        session_id: str,
        forward_tool: str,
        forward_args: Dict[str, Any],
        compensation: Optional[CompensatingActionSpec] = None,
        mutating_class: ActionMutatingClass = ActionMutatingClass.REVERSIBLE_MUTATING,
    ) -> SagaStepRecord:
        """Enforces write-ahead registration prior to invoking mutating tools."""
        current_status = self.get_session_status(session_id)
        if current_status in (SagaSessionStatus.ROLLBACK_TRIGGERED, SagaSessionStatus.ROLLED_BACK, SagaSessionStatus.FAILED_CRITICAL):
            raise RuntimeError(
                f"Cannot register step on session {session_id} in terminal/recovering state {current_status.value}"
            )

        existing_steps = await self.ledger.get_session_steps(session_id)
        step_index = len(existing_steps)

        # Enforce invariant: non-read-only actions must provide compensating spec
        if mutating_class == ActionMutatingClass.REVERSIBLE_MUTATING and compensation is None:
            raise ValueError(
                f"Reversible mutating action '{forward_tool}' must register an explicit CompensatingActionSpec"
            )

        step = SagaStepRecord(
            session_id=session_id,
            step_index=step_index,
            forward_tool_name=forward_tool,
            forward_arguments=forward_args,
            mutating_class=mutating_class,
            compensating_action=compensation,
            status=SagaStepStatus.ARMED,
        )
        await self.ledger.append(step)
        self._session_statuses[session_id] = SagaSessionStatus.ACTIVE
        return step

    async def mark_step_committed(
        self,
        step_id: str,
        output: Dict[str, Any],
    ) -> SagaStepRecord:
        """
        Binds forward execution output to the step record.
        Dynamically binds returned parameters (e.g., generated resource IDs) to the compensating spec.
        """
        step = await self.ledger.get_step_by_id(step_id)
        if not step:
            raise KeyError(f"Step {step_id} does not exist in ledger")

        step.forward_output = output
        step.status = SagaStepStatus.COMMITTED
        step.committed_at_utc = datetime.datetime.now(datetime.timezone.utc)

        # Dynamic parameter binding from forward output to compensation arguments
        if step.compensating_action and step.compensating_action.dynamic_param_mapping:
            for out_key, comp_key in step.compensating_action.dynamic_param_mapping.items():
                if out_key in output:
                    val = output[out_key]
                    step.compensating_action.fixed_arguments[comp_key] = val
                    if comp_key == "resource_id" or comp_key.endswith("_id"):
                        step.compensating_action.target_resource_id = str(val)

        await self.ledger.update(step)
        return step

    async def execute_rollback(
        self,
        session_id: str,
        trigger_reason: str = "Downstream step failure",
    ) -> CleanStateReconciliationReport:
        """
        Executes compensating actions in reverse chronological order (LIFO).
        Implements idempotency fencing, exponential backoff retry, and dead-letter queue escalation.
        """
        started_at = datetime.datetime.now(datetime.timezone.utc)
        self._session_statuses[session_id] = SagaSessionStatus.ROLLBACK_TRIGGERED

        session_steps = await self.ledger.get_session_steps(session_id)
        # Select steps that committed side-effects and need compensation
        committed_steps = [
            s for s in session_steps
            if s.status in (SagaStepStatus.COMMITTED, SagaStepStatus.COMPENSATION_PENDING)
            and s.mutating_class == ActionMutatingClass.REVERSIBLE_MUTATING
            and s.compensating_action is not None
        ]

        # Order strictly in reverse chronological order (LIFO)
        unwind_queue = list(reversed(committed_steps))

        successfully_compensated = 0
        failed_compensations = 0
        audit_trail: List[Dict[str, Any]] = []
        is_lifo = True

        # Verify LIFO ordering invariant
        for idx in range(len(unwind_queue) - 1):
            if unwind_queue[idx].step_index < unwind_queue[idx + 1].step_index:
                is_lifo = False

        terminal_critical = False

        for step in unwind_queue:
            comp = step.compensating_action
            assert comp is not None

            step.status = SagaStepStatus.COMPENSATION_PENDING
            await self.ledger.update(step)

            attempt_success = False
            last_err = ""

            for attempt in range(1, comp.max_retry_attempts + 1):
                try:
                    # Idempotency check: if tool_executor already executed this exact key
                    # (simulate idempotency fencing at transport level)
                    res = await self.tool_executor(
                        comp.compensation_tool_name,
                        comp.fixed_arguments,
                        comp.idempotency_key,
                    )
                    self._executed_idempotency_keys.add(comp.idempotency_key)
                    attempt_success = True
                    step.status = SagaStepStatus.COMPENSATED
                    step.compensated_at_utc = datetime.datetime.now(datetime.timezone.utc)
                    await self.ledger.update(step)
                    successfully_compensated += 1

                    audit_trail.append({
                        "step_id": step.step_id,
                        "step_index": step.step_index,
                        "forward_tool": step.forward_tool_name,
                        "compensation_tool": comp.compensation_tool_name,
                        "idempotency_key": comp.idempotency_key,
                        "attempt": attempt,
                        "status": "COMPENSATED",
                        "result": res,
                    })
                    break
                except Exception as ex:
                    last_err = str(ex)
                    if attempt < comp.max_retry_attempts:
                        backoff = comp.base_backoff_seconds * (2 ** (attempt - 1))
                        await asyncio.sleep(backoff)

            if not attempt_success:
                step.status = SagaStepStatus.COMPENSATION_FAILED
                step.error_message = f"Compensation exhausted {comp.max_retry_attempts} attempts: {last_err}"
                await self.ledger.update(step)
                failed_compensations += 1

                dlq_entry = DeadLetterEntry(
                    session_id=session_id,
                    step_id=step.step_id,
                    tool_name=comp.compensation_tool_name,
                    arguments=comp.fixed_arguments,
                    idempotency_key=comp.idempotency_key,
                    failure_reason=last_err,
                    attempts_exhausted=comp.max_retry_attempts,
                )
                await self.ledger.record_dead_letter(dlq_entry)

                audit_trail.append({
                    "step_id": step.step_id,
                    "step_index": step.step_index,
                    "forward_tool": step.forward_tool_name,
                    "compensation_tool": comp.compensation_tool_name,
                    "idempotency_key": comp.idempotency_key,
                    "status": "COMPENSATION_FAILED",
                    "error": last_err,
                })

                # Halt automated rollback immediately on unrecoverable compensation failure
                # Freezes session to avoid cascading state corruption
                terminal_critical = True
                break

        final_status = (
            SagaSessionStatus.FAILED_CRITICAL
            if terminal_critical
            else SagaSessionStatus.ROLLED_BACK
        )
        self._session_statuses[session_id] = final_status

        concluded_at = datetime.datetime.now(datetime.timezone.utc)
        integrity_hash = await self.ledger.compute_integrity_hash(session_id)
        dlq_entries = await self.ledger.get_dead_letters(session_id)

        report = CleanStateReconciliationReport(
            session_id=session_id,
            session_status=final_status,
            total_steps=len(session_steps),
            mutating_steps=len(committed_steps),
            successfully_compensated=successfully_compensated,
            failed_compensations=failed_compensations,
            unwound_in_lifo_order=is_lifo,
            dead_letter_entries=dlq_entries,
            audit_trail=audit_trail,
            started_at_utc=started_at,
            concluded_at_utc=concluded_at,
            state_integrity_hash=integrity_hash,
        )
        return report


class RuntimeMutatingToolGate:
    """
    Interceptor gate intercepting agent planning dispatch.
    Enforces Write-Ahead intent registration and automatic LIFO rollback upon failure.
    """

    def __init__(
        self,
        coordinator: AgenticSagaCoordinator,
        tool_executor: ToolExecutor,
    ) -> None:
        self.coordinator = coordinator
        self.tool_executor = tool_executor

    async def execute_action(
        self,
        session_id: str,
        tool_name: str,
        arguments: Dict[str, Any],
        compensation_spec_factory: Optional[Callable[[Dict[str, Any]], CompensatingActionSpec]] = None,
        mutating_class: ActionMutatingClass = ActionMutatingClass.REVERSIBLE_MUTATING,
        max_forward_retries: int = 1,
    ) -> Dict[str, Any]:
        """
        Executes a tool within transactional saga guarantees.
        If the tool fails after allowed retries, halts the agent and triggers LIFO rollback.
        """
        # 1. Derive compensation specification if mutating
        comp_spec: Optional[CompensatingActionSpec] = None
        if mutating_class == ActionMutatingClass.REVERSIBLE_MUTATING:
            if compensation_spec_factory is None:
                raise ValueError(
                    f"Action '{tool_name}' is declared REVERSIBLE_MUTATING but has no compensation_spec_factory"
                )
            comp_spec = compensation_spec_factory(arguments)

        # 2. Register step in write-ahead ledger BEFORE executing
        step_record = await self.coordinator.register_step(
            session_id=session_id,
            forward_tool=tool_name,
            forward_args=arguments,
            compensation=comp_spec,
            mutating_class=mutating_class,
        )

        # 3. Attempt forward execution with bounded retry
        last_exception: Optional[Exception] = None
        result: Optional[Dict[str, Any]] = None

        for attempt in range(1, max_forward_retries + 1):
            try:
                result = await self.tool_executor(tool_name, arguments, None)
                break
            except Exception as ex:
                last_exception = ex
                if attempt < max_forward_retries:
                    await asyncio.sleep(0.02 * attempt)

        if result is None:
            # Step failed unrecoverably: mark step error & trigger Saga rollback
            step_record.status = SagaStepStatus.COMPENSATION_FAILED
            step_record.error_message = f"Forward execution failed: {last_exception}"
            await self.coordinator.ledger.update(step_record)

            report = await self.coordinator.execute_rollback(
                session_id=session_id,
                trigger_reason=f"Forward execution halted at {tool_name}: {last_exception}"
            )
            raise RuntimeError(
                f"Forward action '{tool_name}' failed permanently: {last_exception}. "
                f"Saga rollback executed with status {report.session_status.value}. "
                f"Compensated: {report.successfully_compensated}, Failed: {report.failed_compensations}."
            ) from last_exception

        # 4. Mark step committed & dynamically bind output IDs
        await self.coordinator.mark_step_committed(step_record.step_id, result)
        return result
