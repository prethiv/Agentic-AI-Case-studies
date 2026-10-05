"""
Unit Test Suite for Case Study 30: Multi-Agent Mesh Architecture
================================================================
Validates core mesh mechanics:
  - Dynamic semantic capability matching & routing.
  - Contract Net Protocol (CNP) game-theoretic auction evaluation.
  - Cognitive sidecar proxy: cycle detection & monotonic TTL enforcement.
  - Circuit breaker state machine (Closed -> Open -> Half-Open).
  - OpenTelemetry distributed span recording & causal DAG integrity.
"""

import unittest
import uuid
from mesh_core import (
    A2AMessageEnvelope,
    AgentNode,
    CapabilityDescriptor,
    CapabilityRegistry,
    CircuitBreakerState,
    CNPBid,
    CognitiveSidecarProxy,
    ContractNetEngine,
    DistributedTraceCollector,
    PeerProfile,
    RFPAnnouncement,
    compute_semantic_similarity,
    make_security_mesh,
)


class TestMultiAgentMesh(unittest.TestCase):

    def setUp(self):
        self.collector = DistributedTraceCollector()
        self.registry = CapabilityRegistry()

    def test_semantic_similarity_matching(self):
        """Verifies that intent text correctly scores high for semantically related capabilities."""
        cap_desc = "Performs automated static code analysis and AST parsing"
        sim_high = compute_semantic_similarity("code analysis ast", cap_desc, [0.1] * 16)
        sim_low = compute_semantic_similarity("database backup postgres", cap_desc, [0.1] * 16)
        self.assertGreater(sim_high, sim_low)
        self.assertGreaterEqual(sim_high, 0.4)

    def test_contract_net_protocol_bidding(self):
        """Verifies that CNP surplus scoring awards the optimal bid under budget and latency constraints."""
        rfp = RFPAnnouncement(
            rfp_id="rfp-01",
            initiator_did="did:mesh:client",
            task_intent="generate-diff",
            task_description="Remediate buffer overflow in C module",
            max_budget_tokens=5000,
            deadline_seconds=2.0,
        )

        bids = [
            # High confidence, low cost, fast
            CNPBid("b1", "rfp-01", "did:mesh:agent-opt", "Synthesizer", 2000, 400.0, 0.95),
            # Over budget (must be rejected)
            CNPBid("b2", "rfp-01", "did:mesh:agent-expensive", "Synthesizer", 8000, 200.0, 0.99),
            # Low confidence
            CNPBid("b3", "rfp-01", "did:mesh:agent-weak", "Synthesizer", 1500, 500.0, 0.40),
        ]

        winner = ContractNetEngine.evaluate_bids(rfp, bids)
        self.assertIsNotNone(winner)
        self.assertEqual(winner.bidder_did, "did:mesh:agent-opt")

    def test_monotonic_hop_limit_expiration(self):
        """Sidecar proxy must immediately halt envelopes with hop_limit <= 0."""
        proxy = CognitiveSidecarProxy("did:mesh:test-agent", self.collector)
        envelope = A2AMessageEnvelope(
            message_id="m-exp",
            trace_id="tr-01",
            span_id="sp-01",
            parent_span_id=None,
            sender_did="did:mesh:caller",
            recipient_did="did:mesh:test-agent",
            intent="do-work",
            payload={},
            hop_limit=0,
        )
        allowed, reason = proxy.pre_dispatch_check(envelope)
        self.assertFalse(allowed)
        self.assertIn("HOP_LIMIT_EXCEEDED", reason)

    def test_cyclic_delegation_detection(self):
        """Sidecar proxy must block attempts to delegate to an agent already in the causal chain."""
        proxy = CognitiveSidecarProxy("did:mesh:agent-a", self.collector)
        envelope = A2AMessageEnvelope(
            message_id="m-cycle",
            trace_id="tr-02",
            span_id="sp-02",
            parent_span_id=None,
            sender_did="did:mesh:agent-c",
            recipient_did="did:mesh:agent-a",
            intent="recurse",
            payload={},
            hop_limit=4,
            delegation_chain=["did:mesh:agent-a", "did:mesh:agent-b", "did:mesh:agent-c"],
        )
        allowed, reason = proxy.pre_dispatch_check(envelope)
        self.assertFalse(allowed)
        self.assertIn("DELEGATION_CYCLE_DETECTED", reason)

    def test_token_budget_exhaustion(self):
        """Sidecar proxy must block messages with depleted token budgets."""
        proxy = CognitiveSidecarProxy("did:mesh:agent-b", self.collector)
        envelope = A2AMessageEnvelope(
            message_id="m-budget",
            trace_id="tr-03",
            span_id="sp-03",
            parent_span_id=None,
            sender_did="did:mesh:caller",
            recipient_did="did:mesh:agent-b",
            intent="heavy-task",
            payload={},
            token_budget_remaining=0,
        )
        allowed, reason = proxy.pre_dispatch_check(envelope)
        self.assertFalse(allowed)
        self.assertIn("TOKEN_BUDGET_EXHAUSTED", reason)

    def test_circuit_breaker_trip_and_cooldown(self):
        """Consecutive execution failures must trip the circuit breaker from CLOSED to OPEN."""
        proxy = CognitiveSidecarProxy("did:mesh:failing-agent", self.collector)
        self.assertEqual(proxy.state, CircuitBreakerState.CLOSED)

        # Trigger 3 consecutive errors
        proxy.record_outcome(success=False, tokens_used=10)
        proxy.record_outcome(success=False, tokens_used=10)
        proxy.record_outcome(success=False, tokens_used=10)
        self.assertEqual(proxy.state, CircuitBreakerState.OPEN)

        # In OPEN state, pre-dispatch checks must fail
        env = A2AMessageEnvelope("m", "tr", "sp", None, "s", "did:mesh:failing-agent", "x", {}, hop_limit=3)
        allowed, reason = proxy.pre_dispatch_check(env)
        self.assertFalse(allowed)
        self.assertIn("CIRCUIT_BREAKER_OPEN", reason)

    def test_end_to_end_mesh_workflow(self):
        """Executes full 4-agent incident response mesh and verifies distributed trace ledger."""
        agents, registry, collector = make_security_mesh()
        trace_id = uuid.uuid4().hex

        root_envelope = A2AMessageEnvelope(
            message_id="test-root",
            trace_id=trace_id,
            span_id="root-span",
            parent_span_id=None,
            sender_did="did:mesh:siem",
            recipient_did=agents["sentinel"].did,
            intent="triage-alert",
            payload={"alert": "Suspicious reverse shell probe"},
            hop_limit=5,
        )

        res = agents["sentinel"].receive_message(root_envelope)
        self.assertEqual(res["status"], "OK")
        self.assertTrue(res["data"]["investigation_result"]["data"]["patch"]["sandboxed_tests_passed"])
        self.assertTrue(res["data"]["investigation_result"]["data"]["compliance"]["approved"])

        # Validate OpenTelemetry trace
        summary = collector.export_trace_summary(trace_id)
        self.assertEqual(summary["total_spans"], 4)
        self.assertGreater(summary["total_tokens_consumed"], 1000)

        # Validate Mermaid DAG export
        mermaid = collector.render_mermaid_dag(trace_id)
        self.assertTrue(mermaid.startswith("graph TD"))
        self.assertIn("Sentinel", mermaid)
        self.assertIn("ForensicInvestigator", mermaid)


if __name__ == "__main__":
    unittest.main()
