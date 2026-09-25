"""
End-to-End Simulation: Hybrid Hierarchical Delegation & Stigmergic Swarm.
Scenario: Automated Cyber Incident Response & Mitigation Swarm.
"""

import asyncio
import json
import time
from blackboard import StigmergicBlackboard
from coordinator import MissionCoordinator
from worker import SpecialistWorker
from protocol import TaskSpec


async def main():
    print("=" * 80)
    print("  CASE STUDY 11: HYBRID DELEGATION & STIGMERGIC BLACKBOARD SWARM")
    print("  Scenario: Multi-Agent Cyber Incident Response & Exploit Mitigation")
    print("=" * 80)

    # 1. Initialize Shared Stigmergic Blackboard & Strategic Coordinator
    blackboard = StigmergicBlackboard(evaporation_rate=0.05)
    coordinator = MissionCoordinator(
        coordinator_id="Coord-Orchestrator-01",
        blackboard=blackboard,
        max_delegation_depth=3,
        total_token_budget=60000,
    )

    # 2. Spin up Specialist Worker Pool
    triage_worker = SpecialistWorker(
        worker_id="Worker-Triage",
        domain_name="Log & Traffic Forensics",
        capabilities={"log_analysis": 0.95, "network_forensics": 0.90, "waf_engineering": 0.30},
        blackboard=blackboard,
        base_latency_ms=450.0,
        base_token_cost=800,
    )

    reverse_worker = SpecialistWorker(
        worker_id="Worker-MalwareLab",
        domain_name="Reverse Engineering & Sandboxing",
        capabilities={"reverse_engineering": 0.96, "sandbox_detonation": 0.92, "log_analysis": 0.40},
        blackboard=blackboard,
        base_latency_ms=1200.0,
        base_token_cost=2500,
    )

    waf_worker = SpecialistWorker(
        worker_id="Worker-DefenseOps",
        domain_name="WAF & Mitigation Engineering",
        capabilities={"waf_engineering": 0.94, "patch_synthesis": 0.88, "network_forensics": 0.50},
        blackboard=blackboard,
        base_latency_ms=600.0,
        base_token_cost=1100,
    )

    generalist_worker = SpecialistWorker(
        worker_id="Worker-Generalist",
        domain_name="Generalist Support",
        capabilities={"log_analysis": 0.60, "reverse_engineering": 0.50, "waf_engineering": 0.55},
        blackboard=blackboard,
        base_latency_ms=750.0,
        base_token_cost=1500,
    )

    workers = [triage_worker, reverse_worker, waf_worker, generalist_worker]
    print(f"\n[INIT] Registered 4 specialized workers into Swarm Pool.")

    # 3. Define Mission & Tasks
    mission_id = "INCIDENT-2026-0925-SEC"
    tasks = [
        TaskSpec(
            task_id="TASK-01-TRIAGE",
            mission_id=mission_id,
            description="Extract malicious payloads, IPs, and user agents from edge ingress logs",
            required_capabilities=["log_analysis", "network_forensics"],
            priority=5,
            depth=1,
        ),
        TaskSpec(
            task_id="TASK-02-REVERSE",
            mission_id=mission_id,
            description="Decompile binary payload from IOC and extract exploit signature",
            required_capabilities=["reverse_engineering", "sandbox_detonation"],
            parent_task_id="TASK-01-TRIAGE",
            priority=4,
            depth=2,
            dependencies=["TASK-01-TRIAGE"],
        ),
        TaskSpec(
            task_id="TASK-03-WAF-RULE",
            mission_id=mission_id,
            description="Generate ModSecurity / Coraza WAF rules blocking the zero-day exploit pattern",
            required_capabilities=["waf_engineering", "patch_synthesis"],
            parent_task_id="TASK-02-REVERSE",
            priority=5,
            depth=2,
            dependencies=["TASK-02-REVERSE"],
        ),
    ]

    # Reactive subscription: Workers observe blackboard updates via stigmergy
    blackboard.subscribe("artifacts/*", lambda delta, entry: print(
        f"  [STIGMERGY SIGNAL] -> Event on key '{delta.key}' (v{delta.new_version}) written by {delta.author_agent_id}"
    ))

    # 4. Execute Contract Net Auctions & Dynamic Delegation
    for task in tasks:
        print(f"\n" + "-" * 70)
        print(f"[AUCTION] Coordinator issuing Call for Proposals (CFP) for Task: {task.task_id}")
        print(f"          Description: {task.description}")
        print(f"          Required: {task.required_capabilities}")

        # Collect bids from all available workers
        bids = [w.compute_bid(task) for w in workers]
        for b in bids:
            print(f"  * Bid: {b.worker_id:<22} | Score: {b.bid_score:+0.3f} | Conf: {b.capability_confidence:.2f} | Lat: {b.estimated_latency_ms}ms")

        # Coordinator awards task to highest scoring bidder
        award = coordinator.conduct_auction(task, bids)
        assert award is not None, "Auction failed to produce a winner"
        print(f"  >>> AWARDED TO: {award.worker_id} (Score: {award.winning_bid_score:+.3f})")

        # Register delegation in coordinator graph & check DAG invariants
        coordinator.register_delegation(
            from_agent=coordinator.coordinator_id,
            to_agent=award.worker_id,
            current_depth=task.depth,
        )

        # Mint Handoff Token with scoped permissions
        handoff_token = coordinator.mint_handoff_token(
            mission_id=mission_id,
            source_agent_id=coordinator.coordinator_id,
            target_agent_id=award.worker_id,
            task_id=task.task_id,
            depth=task.depth,
            allowed_tools=["read_blackboard", "write_blackboard", "sandbox_eval"],
            epistemic_summary=f"Authorized execution for {task.task_id}",
            immutable_constraints=["DO_NOT_EXCEED_RETRY_CEILING", "AUDIT_ALL_PAYLOADS"],
        )

        # Find the winning worker instance and execute
        winning_worker = next(w for w in workers if w.worker_id == award.worker_id)
        
        # Prepare context from previous blackboard outputs (stigmergic reading)
        context_payload = {}
        if task.dependencies:
            for dep in task.dependencies:
                dep_entry = await blackboard.read(f"artifacts/{dep}")
                if dep_entry:
                    context_payload[dep] = dep_entry.value

        print(f"  [EXECUTION] {award.worker_id} starting execution...")
        result = await winning_worker.execute_task(
            task=task,
            handoff_token=handoff_token,
            execution_payload={"raw_data": f"Artifact synthesized for {task.task_id} with inputs {list(context_payload.keys())}"}
        )
        print(f"  [COMPLETED] {award.worker_id} published artifact to blackboard.")

    # 5. Decay step: simulate environment pheromone evaporation
    evaporated = await blackboard.apply_pheromone_evaporation()
    print(f"\n[STIGMERGIC DECAY] Applied evaporation cycle across {evaporated} blackboard entries.")

    # 6. Mission Synthesis & Audit Trail Summary
    print("\n" + "=" * 80)
    print("  MISSION OUTCOME & SWARM TELEMETRY AUDIT")
    print("=" * 80)
    all_artifacts = await blackboard.query_by_tag(mission_id)
    print(f"Total Stored Artifacts: {len(all_artifacts)}")
    for a in all_artifacts:
        print(f" - Key: {a.key:<25} | Author: {a.author_agent_id:<22} | Urgency: {a.pheromone_urgency:.3f}")

    print(f"\nTotal Token Expenditure: {coordinator.consumed_tokens} / {coordinator.total_token_budget} tokens")
    print(f"Delegation Hierarchy Graph: {dict(coordinator.delegation_graph)}")
    print(f"Total Blackboard State Deltas: {len(blackboard.get_audit_trail())}")
    print("\n[SUCCESS] Swarm resolved all mission objectives with zero point-to-point message cascades!")


if __name__ == "__main__":
    asyncio.run(main())
