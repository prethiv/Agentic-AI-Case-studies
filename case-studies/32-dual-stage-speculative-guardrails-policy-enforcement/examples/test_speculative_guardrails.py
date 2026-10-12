"""
Unit Test Suite for Speculative Policy Guardrails & Non-Blocking Enforcement.
============================================================================
Validates:
  1. Fast-path sub-15ms deterministic denial on PII (SSN, credit cards).
  2. Fast-path deterministic denial on destructive commands (rm -rf, drop table).
  3. Fast-path obfuscation detection (base64-encoded dangerous payloads).
  4. Fast-path Bloom filter and exact blacklist match.
  5. Action risk classifier correctly distinguishes idempotent vs mutating intents.
  6. High-mutating actions block on synchronous deep gate before tool execution.
  7. High-mutating actions abort when deep policy rejects (tool never called).
  8. Low-idempotent actions run speculatively in parallel with deep evaluator.
  9. Low-idempotent speculative results are revoked and purged when deep policy denies.
  10. Fail-closed timeout behavior when deep evaluator exceeds SLA limit.
"""

import asyncio
import base64
import time
import unittest

from speculative_guardrail_engine import (
    ActionIntent,
    ActionRiskClassifierGate,
    DeepSemanticEvaluator,
    FastPathFilter,
    PolicyActionRisk,
    PolicyEvaluationResult,
    PolicyVerdict,
    SpeculativePolicyEngine,
)


class TestSpeculativeGuardrails(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.fast_filter = FastPathFilter()
        self.deep_evaluator = DeepSemanticEvaluator(simulated_latency_s=0.05)
        self.engine = SpeculativePolicyEngine(
            fast_filter=self.fast_filter,
            deep_evaluator=self.deep_evaluator,
            deep_timeout_s=0.5,
        )

    # ------------------------------------------------------------------------
    # 1. Fast-Path Deterministic Filter Tests (< 15ms)
    # ------------------------------------------------------------------------

    def test_fast_path_ssn_denial_under_15ms(self):
        """Validates that SSN leak attempt is dropped in sub-15ms."""
        intent = ActionIntent(
            tool_name="get_user_profile",
            arguments={"query": "lookup user with ssn 000-12-3456"},
            risk_profile=PolicyActionRisk.LOW_IDEMPOTENT,
            agent_id="agent-001",
            session_id="sess-001",
        )
        res = self.engine.evaluate_stage1_fast(intent)
        self.assertEqual(res.verdict, PolicyVerdict.DENY)
        self.assertIn("PII_SSN_DETECTED", res.violated_policies)
        self.assertLess(res.latency_ms, 15.0, f"Latency exceeded 15ms: {res.latency_ms}ms")

    def test_fast_path_destructive_command_denial(self):
        """Validates immediate block of destructive shell and SQL commands."""
        intent = ActionIntent(
            tool_name="execute_terminal",
            arguments={"command": "rm -rf / --no-preserve-root"},
            risk_profile=PolicyActionRisk.HIGH_MUTATING,
            agent_id="agent-001",
            session_id="sess-002",
        )
        res = self.engine.evaluate_stage1_fast(intent)
        self.assertEqual(res.verdict, PolicyVerdict.DENY)
        self.assertIn("DESTRUCTIVE_COMMAND_DETECTED", res.violated_policies)

    def test_fast_path_base64_obfuscation_detection(self):
        """Detects obfuscated base64 dangerous payloads decoded in fast-path."""
        dangerous_command = "drop database enterprise_prod;"
        encoded = base64.b64encode(dangerous_command.encode("utf-8")).decode("utf-8")

        intent = ActionIntent(
            tool_name="run_query",
            arguments={"encoded_payload": encoded},
            risk_profile=PolicyActionRisk.HIGH_MUTATING,
            agent_id="agent-002",
            session_id="sess-003",
        )
        res = self.engine.evaluate_stage1_fast(intent)
        self.assertEqual(res.verdict, PolicyVerdict.DENY)
        self.assertIn("DESTRUCTIVE_COMMAND_DETECTED", res.violated_policies)

    def test_fast_path_bloom_filter_blacklist_token(self):
        """Verifies Bloom filter detection of blacklisted exfiltration terms."""
        intent = ActionIntent(
            tool_name="fetch_network",
            arguments={"action": "attempt to exfiltrate secret data"},
            risk_profile=PolicyActionRisk.LOW_IDEMPOTENT,
            agent_id="agent-003",
            session_id="sess-004",
        )
        res = self.engine.evaluate_stage1_fast(intent)
        self.assertEqual(res.verdict, PolicyVerdict.DENY)
        self.assertIn("BLOCKLIST_KEYWORD_EXFILTRATE", res.violated_policies)

    # ------------------------------------------------------------------------
    # 2. Risk Classification Gate Tests
    # ------------------------------------------------------------------------

    def test_risk_classifier_gate_routing(self):
        """Verifies correct classification between idempotent reads and state mutations."""
        risk_read = ActionRiskClassifierGate.classify_intent("read_document", {"doc_id": "123"})
        self.assertEqual(risk_read, PolicyActionRisk.LOW_IDEMPOTENT)

        risk_delete = ActionRiskClassifierGate.classify_intent("delete_record", {"rec_id": "456"})
        self.assertEqual(risk_delete, PolicyActionRisk.HIGH_MUTATING)

        risk_flag = ActionRiskClassifierGate.classify_intent("fetch_data", {"mutate": True})
        self.assertEqual(risk_flag, PolicyActionRisk.HIGH_MUTATING)

    # ------------------------------------------------------------------------
    # 3. High-Mutating Synchronous Gate Tests
    # ------------------------------------------------------------------------

    async def test_high_mutating_synchronous_barrier_approved(self):
        """High-mutating action awaits deep evaluation, executes tool only after approval."""
        tool_called = False

        async def mock_wire_transfer(args):
            nonlocal tool_called
            tool_called = True
            return {"status": "transferred", "amount": args["amount"]}

        intent = ActionIntent(
            tool_name="wire_transfer",
            arguments={"amount": 500, "recipient": "vendor_corp"},
            risk_profile=PolicyActionRisk.HIGH_MUTATING,
            agent_id="agent-fin",
            session_id="sess-fin-1",
        )

        success, result, trace = await self.engine.execute_with_guardrails(intent, mock_wire_transfer)

        self.assertTrue(success)
        self.assertTrue(tool_called)
        self.assertEqual(result["status"], "transferred")
        self.assertTrue(trace.committed)
        self.assertFalse(trace.speculative_executed)

    async def test_high_mutating_synchronous_barrier_rejected(self):
        """High-mutating action rejected by deep evaluator halts before executing tool."""
        tool_called = False

        async def mock_delete_table(args):
            nonlocal tool_called
            tool_called = True
            return {"status": "deleted"}

        intent = ActionIntent(
            tool_name="delete_table",
            arguments={"table": "restricted_payroll"},
            risk_profile=PolicyActionRisk.HIGH_MUTATING,
            agent_id="agent-admin",
            session_id="sess-admin-1",
        )

        success, result, trace = await self.engine.execute_with_guardrails(intent, mock_delete_table)

        self.assertFalse(success)
        self.assertFalse(tool_called, "Tool must NOT be executed when synchronous deep gate denies!")
        self.assertIn("RESTRICTED_DATASET_ACCESS_RESTRICTED_PAYROLL", result)
        self.assertFalse(trace.committed)

    # ------------------------------------------------------------------------
    # 4. Low-Idempotent Speculative Parallel Execution Tests
    # ------------------------------------------------------------------------

    async def test_speculative_parallel_execution_cleared_by_2pc(self):
        """Low-idempotent tool runs concurrently; observation is committed on policy clearance."""
        t0 = time.perf_counter()

        async def mock_db_query(args):
            await asyncio.sleep(0.04)
            return {"rows": [1, 2, 3], "query": args["query"]}

        intent = ActionIntent(
            tool_name="get_analytics_report",
            arguments={"query": "SELECT revenue FROM q3_summary", "table": "public_sales"},
            risk_profile=PolicyActionRisk.LOW_IDEMPOTENT,
            agent_id="agent-analytics",
            session_id="sess-an-1",
        )

        success, result, trace = await self.engine.execute_with_guardrails(intent, mock_db_query)
        total_duration = time.perf_counter() - t0

        self.assertTrue(success)
        self.assertEqual(result["rows"], [1, 2, 3])
        self.assertTrue(trace.speculative_executed)
        self.assertTrue(trace.committed)
        # Deep eval takes 0.05s, tool takes 0.04s. Running in parallel should take ~0.05s, not (0.05 + 0.04 = 0.09s)
        self.assertLess(total_duration, 0.08, "Parallel execution did not slash latency!")

    async def test_speculative_execution_revoked_by_deep_policy_denial(self):
        """When deep evaluator denies, speculative staging buffer is purged and discarded."""
        tool_called = False

        async def mock_speculative_query(args):
            nonlocal tool_called
            tool_called = True
            return {"confidential_data": "payroll_records_2026"}

        intent = ActionIntent(
            tool_name="fetch_records",
            arguments={"table": "restricted_payroll"},
            risk_profile=PolicyActionRisk.LOW_IDEMPOTENT,
            agent_id="agent-hr",
            session_id="sess-hr-1",
        )

        success, result, trace = await self.engine.execute_with_guardrails(intent, mock_speculative_query)

        self.assertFalse(success)
        self.assertTrue(tool_called, "Tool was speculatively executed in parallel")
        self.assertFalse(trace.committed, "Speculative observation must not be committed!")
        self.assertIn("Speculative result revoked by deep policy check", result)
        self.assertNotIn("payroll_records_2026", result)

    # ------------------------------------------------------------------------
    # 5. Fail-Closed Timeout Handling Tests
    # ------------------------------------------------------------------------

    async def test_deep_evaluator_timeout_fails_closed(self):
        """Slow deep evaluator exceeding SLA triggers fail-closed revocation."""
        slow_evaluator = DeepSemanticEvaluator(simulated_latency_s=0.3)
        engine_with_short_sla = SpeculativePolicyEngine(
            fast_filter=self.fast_filter,
            deep_evaluator=slow_evaluator,
            deep_timeout_s=0.05,  # Shorter than 0.3s
        )

        async def mock_quick_fetch(args):
            return {"data": "cached_info"}

        intent = ActionIntent(
            tool_name="read_cache",
            arguments={"key": "stats"},
            risk_profile=PolicyActionRisk.LOW_IDEMPOTENT,
            agent_id="agent-cache",
            session_id="sess-cache-1",
        )

        success, result, trace = await engine_with_short_sla.execute_with_guardrails(intent, mock_quick_fetch)

        self.assertFalse(success)
        self.assertIn("timed out", result)
        self.assertFalse(trace.committed)


if __name__ == "__main__":
    unittest.main()
