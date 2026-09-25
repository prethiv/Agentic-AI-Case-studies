"""
Unit tests for Hybrid Hierarchical Delegation & Stigmergic Blackboard Swarm.
Tests DAG cycle prevention, max depth guardrails, Contract Net auctions, and blackboard concurrency.
"""

import asyncio
import unittest
from blackboard import StigmergicBlackboard, ConcurrencyConflictError
from coordinator import MissionCoordinator, CyclicDelegationError, MaxDepthExceededError
from worker import SpecialistWorker
from protocol import TaskSpec, HandoffToken


class TestSwarmDelegation(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.blackboard = StigmergicBlackboard(evaporation_rate=0.1)
        self.coordinator = MissionCoordinator(
            coordinator_id="Coord-Test",
            blackboard=self.blackboard,
            max_delegation_depth=3,
        )

    def test_cycle_detection_simple(self):
        """Verify that cyclic delegation A -> B -> A is detected and blocked."""
        self.coordinator.register_delegation("AgentA", "AgentB", current_depth=1)
        with self.assertRaises(CyclicDelegationError):
            self.coordinator.register_delegation("AgentB", "AgentA", current_depth=2)

    def test_cycle_detection_multi_hop(self):
        """Verify multi-hop cycle detection: A -> B -> C -> A."""
        self.coordinator.register_delegation("AgentA", "AgentB", current_depth=1)
        self.coordinator.register_delegation("AgentB", "AgentC", current_depth=2)
        with self.assertRaises(CyclicDelegationError):
            self.coordinator.register_delegation("AgentC", "AgentA", current_depth=2)

    def test_self_delegation_cycle(self):
        """Self-delegation A -> A must immediately fail."""
        with self.assertRaises(CyclicDelegationError):
            self.coordinator.register_delegation("AgentA", "AgentA", current_depth=1)

    def test_max_depth_ceiling(self):
        """Delegation exceeding max configured depth must raise MaxDepthExceededError."""
        with self.assertRaises(MaxDepthExceededError):
            self.coordinator.register_delegation("AgentA", "AgentB", current_depth=3)

    def test_contract_net_auction_win(self):
        """Worker with highest capability match must win the auction."""
        specialist = SpecialistWorker(
            worker_id="Specialist-Crypto",
            domain_name="Cryptography",
            capabilities={"cryptography": 0.98},
            blackboard=self.blackboard,
        )
        generalist = SpecialistWorker(
            worker_id="Generalist",
            domain_name="General",
            capabilities={"cryptography": 0.40},
            blackboard=self.blackboard,
        )

        task = TaskSpec(
            task_id="TASK-CRYPTO-AUDIT",
            mission_id="MISSION-TEST",
            description="Audit ECC curve parameters",
            required_capabilities=["cryptography"],
        )

        bids = [specialist.compute_bid(task), generalist.compute_bid(task)]
        award = self.coordinator.conduct_auction(task, bids)

        self.assertIsNotNone(award)
        self.assertEqual(award.worker_id, "Specialist-Crypto")
        self.assertGreater(bids[0].bid_score, bids[1].bid_score)

    async def test_blackboard_concurrency_conflict(self):
        """Attempting to update an entry with a stale version must raise ConcurrencyConflictError."""
        key = "shared/config"
        entry1 = await self.blackboard.write(key=key, value={"rate": 10}, author_agent_id="AgentA")
        self.assertEqual(entry1.version, 1)

        # Agent B writes with correct expected version 1 -> succeeds to version 2
        entry2 = await self.blackboard.write(
            key=key, value={"rate": 20}, author_agent_id="AgentB", expected_version=1
        )
        self.assertEqual(entry2.version, 2)

        # Agent C tries to write with stale expected version 1 -> should fail
        with self.assertRaises(ConcurrencyConflictError):
            await self.blackboard.write(
                key=key, value={"rate": 30}, author_agent_id="AgentC", expected_version=1
            )

    async def test_pheromone_evaporation(self):
        """Verify stigmergic urgency decay."""
        await self.blackboard.write(key="task/urgent", value="alert", author_agent_id="AgentA", pheromone_urgency=1.0)
        await self.blackboard.apply_pheromone_evaporation()
        entry = await self.blackboard.read("task/urgent")
        self.assertIsNotNone(entry)
        self.assertAlmostEqual(entry.pheromone_urgency, 0.9, places=2)

    def test_handoff_token_tamper_detection(self):
        """Tampering with HandoffToken fields invalidates signature verification."""
        token = self.coordinator.mint_handoff_token(
            mission_id="M1",
            source_agent_id="Lead",
            target_agent_id="Worker",
            task_id="T1",
            depth=1,
            allowed_tools=["read"],
            epistemic_summary="Summary",
            immutable_constraints=[],
        )
        self.assertTrue(token.verify())

        # Tamper target agent
        token.target_agent_id = "RogueAgent"
        self.assertFalse(token.verify())


if __name__ == "__main__":
    unittest.main()
