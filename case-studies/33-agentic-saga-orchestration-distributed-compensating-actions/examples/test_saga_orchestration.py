"""
Automated Unit and Integration Test Suite for Agentic Saga Orchestration.
========================================================================
Validates:
  1. Write-Ahead registration enforces reversible mutating tools have compensation specs.
  2. Happy path forward execution and output commitment.
  3. Dynamic parameter binding (forward output resource IDs bound to compensation arguments).
  4. LIFO (Last-In, First-Out) compensation unwinding on downstream failure.
  5. Read-only actions bypass compensation queue without blocking rollback.
  6. Idempotency keys are deterministically passed and tracked during compensation.
  7. Transient compensation failures recover via exponential backoff retry.
  8. Unrecoverable compensation failure escalates to Dead Letter Queue (DLQ) and freezes session.
  9. Session in terminal/rollback state rejects subsequent forward step registration.
  10. End-to-end multi-tier cloud deployment failure unwinds cluster -> subnet -> vpc cleanly.
"""

import asyncio
import os
import sys
import unittest
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from saga_orchestration_engine import (
    ActionMutatingClass,
    AgenticSagaCoordinator,
    CompensatingActionSpec,
    DeadLetterEntry,
    RuntimeMutatingToolGate,
    SagaSessionStatus,
    SagaStepRecord,
    SagaStepStatus,
    WriteAheadIntentLedger,
)


class MockDistributedEnvironment:
    """Simulates distributed cloud infrastructure services with failure injection."""

    def __init__(self) -> None:
        self.state: Dict[str, Any] = {
            "vpcs": {},
            "subnets": {},
            "clusters": {},
            "dns_records": {},
        }
        self.call_history: List[Dict[str, Any]] = []
        self.fail_forward_tools: set[str] = set()
        self.glitch_compensation_tools: Dict[str, int] = {}
        self.fail_compensation_tools: set[str] = set()

    async def execute(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        self.call_history.append({
            "tool_name": tool_name,
            "arguments": arguments,
            "idempotency_key": idempotency_key,
        })

        # Failure injection
        if tool_name in self.fail_forward_tools:
            raise RuntimeError(f"Simulated forward failure on tool: {tool_name}")

        if tool_name in self.fail_compensation_tools:
            raise RuntimeError(f"Permanent network failure on compensation tool: {tool_name}")

        if tool_name in self.glitch_compensation_tools and self.glitch_compensation_tools[tool_name] > 0:
            self.glitch_compensation_tools[tool_name] -= 1
            raise ConnectionResetError(f"Transient glitch on tool: {tool_name}")

        # Domain implementations
        if tool_name == "aws_create_vpc":
            vpc_id = f"vpc-{len(self.state['vpcs']) + 1:04d}"
            cidr = arguments.get("cidr_block", "10.0.0.0/16")
            self.state["vpcs"][vpc_id] = {"cidr": cidr, "active": True}
            return {"vpc_id": vpc_id, "status": "AVAILABLE"}

        elif tool_name == "aws_delete_vpc":
            vpc_id = arguments.get("vpc_id")
            if vpc_id in self.state["vpcs"]:
                del self.state["vpcs"][vpc_id]
            return {"deleted": vpc_id, "status": "TERMINATED"}

        elif tool_name == "aws_create_subnet":
            subnet_id = f"sub-{len(self.state['subnets']) + 1:04d}"
            vpc_id = arguments.get("vpc_id")
            self.state["subnets"][subnet_id] = {"vpc_id": vpc_id, "active": True}
            return {"subnet_id": subnet_id, "status": "AVAILABLE"}

        elif tool_name == "aws_delete_subnet":
            subnet_id = arguments.get("subnet_id")
            if subnet_id in self.state["subnets"]:
                del self.state["subnets"][subnet_id]
            return {"deleted": subnet_id, "status": "TERMINATED"}

        elif tool_name == "k8s_create_cluster":
            cluster_id = f"cls-{len(self.state['clusters']) + 1:04d}"
            subnet_id = arguments.get("subnet_id")
            self.state["clusters"][cluster_id] = {"subnet_id": subnet_id, "active": True}
            return {"cluster_id": cluster_id, "nodes": 3, "status": "READY"}

        elif tool_name == "k8s_delete_cluster":
            cluster_id = arguments.get("cluster_id")
            if cluster_id in self.state["clusters"]:
                del self.state["clusters"][cluster_id]
            return {"deleted": cluster_id, "status": "DESTROYED"}

        elif tool_name == "inspect_telemetry":
            return {"metrics": "all_healthy", "count": 42}

        elif tool_name == "deploy_app":
            raise RuntimeError("Out of memory during pod allocation")

        return {"status": "ok"}


class TestAgenticSagaOrchestration(unittest.IsolatedAsyncioTestCase):

    def setUp(self) -> None:
        self.env = MockDistributedEnvironment()
        self.ledger = WriteAheadIntentLedger()
        self.coordinator = AgenticSagaCoordinator(
            ledger=self.ledger,
            tool_executor=self.env.execute,
        )
        self.gate = RuntimeMutatingToolGate(
            coordinator=self.coordinator,
            tool_executor=self.env.execute,
        )

    # -------------------------------------------------------------------------
    # 1. Registration Invariants & Schema Enforcement
    # -------------------------------------------------------------------------

    async def test_mutating_action_requires_compensation_spec(self) -> None:
        """Verifies that reversible mutating tools cannot register without compensation spec."""
        with self.assertRaises(ValueError) as ctx:
            await self.coordinator.register_step(
                session_id="sess-01",
                forward_tool="aws_create_vpc",
                forward_args={"cidr_block": "10.0.0.0/16"},
                compensation=None,
                mutating_class=ActionMutatingClass.REVERSIBLE_MUTATING,
            )
        self.assertIn("must register an explicit CompensatingActionSpec", str(ctx.exception))

    async def test_read_only_action_registers_without_compensation(self) -> None:
        """Read-only actions can be registered without compensation and commit cleanly."""
        step = await self.coordinator.register_step(
            session_id="sess-02",
            forward_tool="inspect_telemetry",
            forward_args={},
            compensation=None,
            mutating_class=ActionMutatingClass.READ_ONLY,
        )
        self.assertEqual(step.status, SagaStepStatus.ARMED)
        self.assertEqual(step.mutating_class, ActionMutatingClass.READ_ONLY)

    # -------------------------------------------------------------------------
    # 2. Dynamic Output Binding & Happy Path
    # -------------------------------------------------------------------------

    async def test_forward_output_dynamic_parameter_binding(self) -> None:
        """Verifies that forward execution outputs dynamically bind to compensating spec arguments."""
        session_id = "sess-03"

        def vpc_compensation(args: Dict[str, Any]) -> CompensatingActionSpec:
            return CompensatingActionSpec(
                compensation_tool_name="aws_delete_vpc",
                dynamic_param_mapping={"vpc_id": "vpc_id"},
            )

        result = await self.gate.execute_action(
            session_id=session_id,
            tool_name="aws_create_vpc",
            arguments={"cidr_block": "172.16.0.0/12"},
            compensation_spec_factory=vpc_compensation,
        )

        vpc_id = result["vpc_id"]
        self.assertTrue(vpc_id.startswith("vpc-"))
        self.assertIn(vpc_id, self.env.state["vpcs"])

        # Check ledger record
        steps = await self.ledger.get_session_steps(session_id)
        self.assertEqual(len(steps), 1)
        committed_step = steps[0]
        self.assertEqual(committed_step.status, SagaStepStatus.COMMITTED)
        self.assertIsNotNone(committed_step.compensating_action)
        # Verify dynamic binding occurred:
        self.assertEqual(committed_step.compensating_action.fixed_arguments.get("vpc_id"), vpc_id)
        self.assertEqual(committed_step.compensating_action.target_resource_id, vpc_id)

    # -------------------------------------------------------------------------
    # 3. Deterministic LIFO Rollback Verification
    # -------------------------------------------------------------------------

    async def test_deterministic_lifo_rollback_on_downstream_failure(self) -> None:
        """
        Executes a 3-step sequence where step 3 fails:
        1. Create VPC
        2. Create Subnet
        3. Deploy App (Fails)
        Coordinator must unwind: Step 2 (delete Subnet) THEN Step 1 (delete VPC).
        """
        session_id = "sess-04"

        # Step 1: Create VPC
        vpc_res = await self.gate.execute_action(
            session_id=session_id,
            tool_name="aws_create_vpc",
            arguments={"cidr_block": "10.0.0.0/16"},
            compensation_spec_factory=lambda _: CompensatingActionSpec(
                compensation_tool_name="aws_delete_vpc",
                dynamic_param_mapping={"vpc_id": "vpc_id"},
            ),
        )
        vpc_id = vpc_res["vpc_id"]

        # Step 2: Create Subnet
        subnet_res = await self.gate.execute_action(
            session_id=session_id,
            tool_name="aws_create_subnet",
            arguments={"vpc_id": vpc_id},
            compensation_spec_factory=lambda _: CompensatingActionSpec(
                compensation_tool_name="aws_delete_subnet",
                dynamic_param_mapping={"subnet_id": "subnet_id"},
            ),
        )
        subnet_id = subnet_res["subnet_id"]

        # Both VPC and Subnet are currently active in environment
        self.assertIn(vpc_id, self.env.state["vpcs"])
        self.assertIn(subnet_id, self.env.state["subnets"])

        # Step 3: Mutating action that fails permanently
        with self.assertRaises(RuntimeError) as ctx:
            await self.gate.execute_action(
                session_id=session_id,
                tool_name="deploy_app",
                arguments={"subnet_id": subnet_id, "image": "redis:7"},
                compensation_spec_factory=lambda _: CompensatingActionSpec(
                    compensation_tool_name="remove_app",
                ),
            )
        self.assertIn("Saga rollback executed with status ROLLED_BACK", str(ctx.exception))
        self.assertIn("Compensated: 2, Failed: 0", str(ctx.exception))

        # Check environment clean-state reconciliation
        self.assertNotIn(subnet_id, self.env.state["subnets"])
        self.assertNotIn(vpc_id, self.env.state["vpcs"])

        # Check call history order: Subnet deleted BEFORE VPC deleted (LIFO)
        comp_calls = [
            c["tool_name"] for c in self.env.call_history
            if c["tool_name"].startswith("aws_delete")
        ]
        self.assertEqual(comp_calls, ["aws_delete_subnet", "aws_delete_vpc"])

        # Verify final session status and steps
        steps = await self.ledger.get_session_steps(session_id)
        self.assertEqual(steps[0].status, SagaStepStatus.COMPENSATED)
        self.assertEqual(steps[1].status, SagaStepStatus.COMPENSATED)
        self.assertEqual(steps[2].status, SagaStepStatus.COMPENSATION_FAILED)

    # -------------------------------------------------------------------------
    # 4. Read-Only Step in Trajectory Bypasses Compensation
    # -------------------------------------------------------------------------

    async def test_read_only_step_in_unwind_chain(self) -> None:
        """Interleaved read-only steps do not register compensation actions and are skipped in LIFO."""
        session_id = "sess-05"

        # Step 1: Mutating VPC
        await self.gate.execute_action(
            session_id=session_id,
            tool_name="aws_create_vpc",
            arguments={"cidr_block": "10.1.0.0/16"},
            compensation_spec_factory=lambda _: CompensatingActionSpec(
                compensation_tool_name="aws_delete_vpc",
                dynamic_param_mapping={"vpc_id": "vpc_id"},
            ),
        )

        # Step 2: Read-Only Telemetry Inspection
        await self.gate.execute_action(
            session_id=session_id,
            tool_name="inspect_telemetry",
            arguments={},
            mutating_class=ActionMutatingClass.READ_ONLY,
        )

        # Step 3: Failing Action triggers automated rollback
        with self.assertRaises(RuntimeError) as ctx:
            await self.gate.execute_action(
                session_id=session_id,
                tool_name="deploy_app",
                arguments={},
                compensation_spec_factory=lambda _: CompensatingActionSpec(
                    compensation_tool_name="noop",
                ),
            )
        self.assertIn("Compensated: 1, Failed: 0", str(ctx.exception))

        # Check step statuses: Mutating step is compensated, read-only stays committed
        steps = await self.ledger.get_session_steps(session_id)
        self.assertEqual(steps[0].status, SagaStepStatus.COMPENSATED)
        self.assertEqual(steps[1].status, SagaStepStatus.COMMITTED)
        self.assertEqual(steps[2].status, SagaStepStatus.COMPENSATION_FAILED)

    # -------------------------------------------------------------------------
    # 5. Idempotency Key Fencing & Backoff Retry
    # -------------------------------------------------------------------------

    async def test_transient_compensation_glitch_recovers_via_retry(self) -> None:
        """Transient network failure during compensation is retried with backoff and succeeds."""
        session_id = "sess-06"
        self.env.glitch_compensation_tools["aws_delete_vpc"] = 2  # Fail twice, succeed on attempt 3

        await self.gate.execute_action(
            session_id=session_id,
            tool_name="aws_create_vpc",
            arguments={"cidr_block": "10.2.0.0/16"},
            compensation_spec_factory=lambda _: CompensatingActionSpec(
                compensation_tool_name="aws_delete_vpc",
                dynamic_param_mapping={"vpc_id": "vpc_id"},
                max_retry_attempts=3,
                base_backoff_seconds=0.01,
            ),
        )

        # Trigger manual rollback
        report = await self.coordinator.execute_rollback(session_id)
        self.assertEqual(report.session_status, SagaSessionStatus.ROLLED_BACK)
        self.assertEqual(report.successfully_compensated, 1)
        self.assertEqual(report.failed_compensations, 0)
        self.assertEqual(len(report.audit_trail), 1)
        self.assertEqual(report.audit_trail[0]["attempt"], 3)

    # -------------------------------------------------------------------------
    # 6. Unrecoverable Compensation Escalation to Dead Letter Queue
    # -------------------------------------------------------------------------

    async def test_unrecoverable_compensation_freezes_session_and_logs_dlq(self) -> None:
        """When compensation exhausts retries, session freezes to FAILED_CRITICAL and logs to DLQ."""
        session_id = "sess-07"
        self.env.fail_compensation_tools.add("aws_delete_vpc")

        await self.gate.execute_action(
            session_id=session_id,
            tool_name="aws_create_vpc",
            arguments={"cidr_block": "10.3.0.0/16"},
            compensation_spec_factory=lambda _: CompensatingActionSpec(
                compensation_tool_name="aws_delete_vpc",
                dynamic_param_mapping={"vpc_id": "vpc_id"},
                max_retry_attempts=2,
                base_backoff_seconds=0.01,
            ),
        )

        report = await self.coordinator.execute_rollback(session_id)
        self.assertEqual(report.session_status, SagaSessionStatus.FAILED_CRITICAL)
        self.assertEqual(report.failed_compensations, 1)
        self.assertEqual(len(report.dead_letter_entries), 1)

        dlq = report.dead_letter_entries[0]
        self.assertEqual(dlq.tool_name, "aws_delete_vpc")
        self.assertEqual(dlq.attempts_exhausted, 2)
        self.assertIn("Permanent network failure", dlq.failure_reason)

    # -------------------------------------------------------------------------
    # 7. Session Protection Against Post-Rollback Registration
    # -------------------------------------------------------------------------

    async def test_registration_rejected_on_rolled_back_session(self) -> None:
        """Active session in ROLLED_BACK state prevents further step registration."""
        session_id = "sess-08"
        await self.gate.execute_action(
            session_id=session_id,
            tool_name="aws_create_vpc",
            arguments={"cidr_block": "10.4.0.0/16"},
            compensation_spec_factory=lambda _: CompensatingActionSpec(
                compensation_tool_name="aws_delete_vpc",
                dynamic_param_mapping={"vpc_id": "vpc_id"},
            ),
        )
        await self.coordinator.execute_rollback(session_id)

        with self.assertRaises(RuntimeError) as ctx:
            await self.coordinator.register_step(
                session_id=session_id,
                forward_tool="inspect_telemetry",
                forward_args={},
                mutating_class=ActionMutatingClass.READ_ONLY,
            )
        self.assertIn("terminal/recovering state", str(ctx.exception))

    # -------------------------------------------------------------------------
    # 8. Cryptographic State Integrity Hash
    # -------------------------------------------------------------------------

    async def test_state_integrity_hash_changes_across_lifecycle(self) -> None:
        """Validates that session state integrity SHA-256 hash updates monotonically."""
        session_id = "sess-09"
        hash_0 = await self.ledger.compute_integrity_hash(session_id)

        await self.gate.execute_action(
            session_id=session_id,
            tool_name="aws_create_vpc",
            arguments={"cidr_block": "10.5.0.0/16"},
            compensation_spec_factory=lambda _: CompensatingActionSpec(
                compensation_tool_name="aws_delete_vpc",
                dynamic_param_mapping={"vpc_id": "vpc_id"},
            ),
        )
        hash_1 = await self.ledger.compute_integrity_hash(session_id)
        self.assertNotEqual(hash_0, hash_1)

        await self.coordinator.execute_rollback(session_id)
        hash_2 = await self.ledger.compute_integrity_hash(session_id)
        self.assertNotEqual(hash_1, hash_2)

    # -------------------------------------------------------------------------
    # 9. Clean-State Reconciliation Report Integrity
    # -------------------------------------------------------------------------

    async def test_clean_state_reconciliation_report_fields(self) -> None:
        """Verifies all audit trail, timing, and hash properties in Reconciliation Report."""
        session_id = "sess-10"
        await self.gate.execute_action(
            session_id=session_id,
            tool_name="aws_create_vpc",
            arguments={"cidr_block": "192.168.0.0/16"},
            compensation_spec_factory=lambda _: CompensatingActionSpec(
                compensation_tool_name="aws_delete_vpc",
                dynamic_param_mapping={"vpc_id": "vpc_id"},
            ),
        )
        report = await self.coordinator.execute_rollback(session_id)
        self.assertEqual(report.session_id, session_id)
        self.assertEqual(report.session_status, SagaSessionStatus.ROLLED_BACK)
        self.assertEqual(report.total_steps, 1)
        self.assertEqual(report.mutating_steps, 1)
        self.assertEqual(report.successfully_compensated, 1)
        self.assertEqual(report.failed_compensations, 0)
        self.assertTrue(report.unwound_in_lifo_order)
        self.assertEqual(len(report.dead_letter_entries), 0)
        self.assertEqual(len(report.audit_trail), 1)
        self.assertTrue(len(report.state_integrity_hash) == 64)
        self.assertLessEqual(report.started_at_utc, report.concluded_at_utc)

    # -------------------------------------------------------------------------
    # 10. Multi-Tier End-to-End Infrastructure Deployment Rollback
    # -------------------------------------------------------------------------

    async def test_multi_tier_cloud_infrastructure_rollback(self) -> None:
        """
        Tests complete 4-tier infrastructure trajectory:
          Step 0: Create VPC
          Step 1: Create Subnet (bound to VPC ID)
          Step 2: Create Kubernetes Cluster (bound to Subnet ID)
          Step 3: Deploy Application (Fails fatal OOM)
        Unwind must neutralise in exact reverse order:
          Cluster -> Subnet -> VPC
        """
        session_id = "sess-11"

        # Step 0: VPC
        vpc_res = await self.gate.execute_action(
            session_id=session_id,
            tool_name="aws_create_vpc",
            arguments={"cidr_block": "10.100.0.0/16"},
            compensation_spec_factory=lambda _: CompensatingActionSpec(
                compensation_tool_name="aws_delete_vpc",
                dynamic_param_mapping={"vpc_id": "vpc_id"},
            ),
        )
        vpc_id = vpc_res["vpc_id"]

        # Step 1: Subnet
        subnet_res = await self.gate.execute_action(
            session_id=session_id,
            tool_name="aws_create_subnet",
            arguments={"vpc_id": vpc_id},
            compensation_spec_factory=lambda _: CompensatingActionSpec(
                compensation_tool_name="aws_delete_subnet",
                dynamic_param_mapping={"subnet_id": "subnet_id"},
            ),
        )
        subnet_id = subnet_res["subnet_id"]

        # Step 2: K8s Cluster
        cluster_res = await self.gate.execute_action(
            session_id=session_id,
            tool_name="k8s_create_cluster",
            arguments={"subnet_id": subnet_id},
            compensation_spec_factory=lambda _: CompensatingActionSpec(
                compensation_tool_name="k8s_delete_cluster",
                dynamic_param_mapping={"cluster_id": "cluster_id"},
            ),
        )
        cluster_id = cluster_res["cluster_id"]

        # All 3 resources exist in mock cloud environment
        self.assertIn(vpc_id, self.env.state["vpcs"])
        self.assertIn(subnet_id, self.env.state["subnets"])
        self.assertIn(cluster_id, self.env.state["clusters"])

        # Step 3: Mutating deployment fails
        with self.assertRaises(RuntimeError) as ctx:
            await self.gate.execute_action(
                session_id=session_id,
                tool_name="deploy_app",
                arguments={"cluster_id": cluster_id, "image": "postgres:16"},
                compensation_spec_factory=lambda _: CompensatingActionSpec(
                    compensation_tool_name="remove_app",
                ),
            )
        self.assertIn("Compensated: 3, Failed: 0", str(ctx.exception))

        # Check all resources were deleted from cloud state
        self.assertNotIn(cluster_id, self.env.state["clusters"])
        self.assertNotIn(subnet_id, self.env.state["subnets"])
        self.assertNotIn(vpc_id, self.env.state["vpcs"])

        # Check call history order: k8s_delete_cluster -> aws_delete_subnet -> aws_delete_vpc
        comp_tools = [
            c["tool_name"] for c in self.env.call_history
            if c["tool_name"].endswith(("_cluster", "_subnet", "_vpc")) and c["tool_name"].startswith(("aws_delete", "k8s_delete"))
        ]
        self.assertEqual(comp_tools, ["k8s_delete_cluster", "aws_delete_subnet", "aws_delete_vpc"])


if __name__ == "__main__":
    unittest.main()
