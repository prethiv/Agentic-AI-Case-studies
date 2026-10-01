"""
Executable Reference Implementation for Case Study 26:
Thinking Before Thinking — Scaling Agentic Inference Through Meta-Reasoning.

Demonstrates:
- 4-Stage Deliberative Control Cycle (Assess, Propose, Evaluate, Dispatch)
- Persistent Artifact DAG Memory with causal lineage tracking
- Type-2 AUC Metacognitive Discrimination scoring
- Convergence Frontier & Frontier Selection Gain (FSG)
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import logging
import math
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("MetaReasoningRunner")


@dataclasses.dataclass(frozen=True)
class Artifact:
    artifact_id: str
    round_index: int
    worker_index: int
    title: str
    body: str
    parent_ids: Tuple[str, ...]
    is_controller_note: bool = False
    confidence: str = "MEDIUM"
    correctness_label: Optional[int] = None
    timestamp: float = dataclasses.field(default_factory=time.time)

    def to_index_line(self) -> str:
        tag = "[NOTE]" if self.is_controller_note else "[WORKER]"
        return f"{self.artifact_id}: {tag} {self.title}"


class PersistentArtifactMemory:
    def __init__(self) -> None:
        self._artifacts: Dict[str, Artifact] = {}
        self._adjacency: Dict[str, Set[str]] = {}
        self._reverse_adjacency: Dict[str, Set[str]] = {}

    def write(
        self,
        round_index: int,
        worker_index: int,
        title: str,
        body: str,
        parent_ids: List[str],
        is_controller_note: bool = False,
        confidence: str = "MEDIUM",
        correctness_label: Optional[int] = None,
    ) -> Artifact:
        artifact_id = f"{round_index}_{worker_index}"
        artifact = Artifact(
            artifact_id=artifact_id,
            round_index=round_index,
            worker_index=worker_index,
            title=title,
            body=body,
            parent_ids=tuple(parent_ids),
            is_controller_note=is_controller_note,
            confidence=confidence,
            correctness_label=correctness_label,
        )
        self._artifacts[artifact_id] = artifact
        self._reverse_adjacency[artifact_id] = set(parent_ids)
        if artifact_id not in self._adjacency:
            self._adjacency[artifact_id] = set()

        for pid in parent_ids:
            if pid in self._artifacts:
                self._adjacency.setdefault(pid, set()).add(artifact_id)

        return artifact

    def read(self, artifact_ids: List[str]) -> List[Artifact]:
        return [self._artifacts[aid] for aid in artifact_ids if aid in self._artifacts]

    def get_index_string(self) -> str:
        lines = [art.to_index_line() for art in self._artifacts.values()]
        return "\n".join(lines) if lines else "(Empty Memory)"

    def get_terminal_nodes(self) -> List[Artifact]:
        terminals = []
        for aid, artifact in self._artifacts.items():
            if not artifact.is_controller_note:
                children = self._adjacency.get(aid, set())
                if len(children) == 0:
                    terminals.append(artifact)
        return terminals

    def compute_longest_path(self, artifact_id: str) -> int:
        parents = self._reverse_adjacency.get(artifact_id, set())
        if not parents:
            return 0
        return 1 + max(self.compute_longest_path(p) for p in parents)

    def get_convergence_frontier(self) -> List[Artifact]:
        terminals = self.get_terminal_nodes()
        if not terminals:
            return []
        depths = {t.artifact_id: self.compute_longest_path(t.artifact_id) for t in terminals}
        max_depth = max(depths.values())
        return [t for t in terminals if depths[t.artifact_id] == max_depth]


@dataclasses.dataclass
class CandidateAssessment:
    candidate_id: str
    verdict: str
    reasoning: str
    confidence_score: float


@dataclasses.dataclass
class ControllerState:
    round_index: int
    candidate_assessments: Dict[str, CandidateAssessment]
    overall_assessment: str
    stop_recommended: bool
    stop_candidate_id: Optional[str]
    outstanding_questions: List[str]
    worklist_unexplored: List[str]
    known_dead_ends: List[str]


@dataclasses.dataclass
class ProposedAction:
    action_id: str
    description: str
    rationale: str
    target_memory_ids: List[str]
    expected_gain: str
    parallel_workers: int = 1


@dataclasses.dataclass
class WorkerAssignment:
    steering_prompt: str
    context_artifact_ids: List[str]


class MetacognitiveMetricsEvaluator:
    @staticmethod
    def calculate_type2_auc(pairs: List[Tuple[float, int]]) -> float:
        positives = [score for score, label in pairs if label == 1]
        negatives = [score for score, label in pairs if label == 0]

        if not positives or not negatives:
            return 0.5

        concordant = 0.0
        total_pairs = len(positives) * len(negatives)

        for p in positives:
            for n in negatives:
                if p > n:
                    concordant += 1.0
                elif p == n:
                    concordant += 0.5

        return concordant / total_pairs

    @staticmethod
    def calculate_frontier_selection_gain(
        frontier: List[Artifact], submitted_artifact: Artifact
    ) -> float:
        if not frontier:
            return 0.0
        q_F = sum(1.0 for a in frontier if a.correctness_label == 1) / len(frontier)
        l_sub = 1.0 if submitted_artifact.correctness_label == 1 else 0.0
        return l_sub - q_F


class MetaReasoningController:
    def __init__(
        self,
        task: str,
        memory: PersistentArtifactMemory,
        model_call_budget: int = 100,
    ) -> None:
        self.task = task
        self.memory = memory
        self.nominal_budget = model_call_budget
        self.remaining_budget = model_call_budget
        self.state: Optional[ControllerState] = None
        self.total_controller_calls = 0
        self.total_worker_calls = 0

    def _charge_budget(self, calls: int, is_controller: bool = True) -> bool:
        self.remaining_budget -= calls
        if is_controller:
            self.total_controller_calls += calls
        else:
            self.total_worker_calls += calls

        logger.info(
            "Budget charged: -%d (%s). Remaining: %d / %d",
            calls,
            "Controller" if is_controller else "Workers",
            self.remaining_budget,
            self.nominal_budget,
        )
        return self.remaining_budget > 0

    def stage_assess(self, round_index: int, new_artifacts: List[Artifact]) -> ControllerState:
        self._charge_budget(1, is_controller=True)
        candidate_assessments = dict(self.state.candidate_assessments) if self.state else {}
        open_questions = list(self.state.outstanding_questions) if self.state else []
        dead_ends = list(self.state.known_dead_ends) if self.state else []
        stop_recommended = False
        stop_id = None

        for art in new_artifacts:
            if art.is_controller_note:
                continue

            if "flaw" in art.body.lower():
                verdict = "FUNDAMENTALLY_FLAWED"
                conf_score = 0.15
                dead_ends.append(f"Approach {art.title} failed: critical flaw.")
            elif "gap" in art.body.lower():
                verdict = "HAS_GAPS"
                conf_score = 0.55
                open_questions.append(f"Unverified step in {art.artifact_id}.")
            else:
                verdict = "LIKELY_CORRECT"
                conf_score = 0.92
                stop_recommended = True
                stop_id = art.artifact_id

            candidate_assessments[art.artifact_id] = CandidateAssessment(
                candidate_id=art.artifact_id,
                verdict=verdict,
                reasoning=f"Stage assessment: {verdict}",
                confidence_score=conf_score,
            )

        updated_state = ControllerState(
            round_index=round_index,
            candidate_assessments=candidate_assessments,
            overall_assessment=f"Round {round_index} state: {len(candidate_assessments)} artifacts tracked.",
            stop_recommended=stop_recommended,
            stop_candidate_id=stop_id,
            outstanding_questions=open_questions,
            worklist_unexplored=["Inspect edge cases", "Synthesize findings"],
            known_dead_ends=dead_ends,
        )
        self.state = updated_state
        return updated_state

    def stage_propose(self, state: ControllerState) -> List[ProposedAction]:
        self._charge_budget(1, is_controller=True)
        proposals: List[ProposedAction] = []

        if state.stop_recommended and state.stop_candidate_id:
            proposals.append(
                ProposedAction(
                    action_id="STOP",
                    description=f"Submit candidate {state.stop_candidate_id}",
                    rationale="Complete verified proof established.",
                    target_memory_ids=[state.stop_candidate_id],
                    expected_gain="HIGH_VALUE",
                    parallel_workers=0,
                )
            )

        gap_candidates = [
            cid for cid, ca in state.candidate_assessments.items() if ca.verdict == "HAS_GAPS"
        ]
        if gap_candidates:
            proposals.append(
                ProposedAction(
                    action_id=f"REPAIR_{gap_candidates[-1]}",
                    description=f"Repair lemma in {gap_candidates[-1]}",
                    rationale="Targeted repair yields higher success than full retry.",
                    target_memory_ids=[gap_candidates[-1]],
                    expected_gain="HIGH_VALUE",
                    parallel_workers=1,
                )
            )

        proposals.append(
            ProposedAction(
                action_id="EXPLORE_NEW_ANGLE",
                description="Explore alternative lemma via generating functions",
                rationale="Diversify search frontier.",
                target_memory_ids=[],
                expected_gain="MEDIUM_VALUE",
                parallel_workers=2,
            )
        )
        return proposals

    def stage_evaluate(
        self, state: ControllerState, proposals: List[ProposedAction]
    ) -> ProposedAction:
        self._charge_budget(1, is_controller=True)
        for p in proposals:
            if p.action_id == "STOP":
                if len(state.outstanding_questions) == 0 or self.remaining_budget <= 8:
                    return p

        for p in proposals:
            if p.action_id.startswith("REPAIR_") and self.remaining_budget >= 5:
                return p

        return proposals[-1]

    def stage_dispatch(
        self, state: ControllerState, chosen_action: ProposedAction
    ) -> Tuple[bool, Optional[str], List[WorkerAssignment]]:
        self._charge_budget(1, is_controller=True)
        if chosen_action.action_id == "STOP":
            return True, chosen_action.target_memory_ids[0], []

        assignments: List[WorkerAssignment] = []
        for _ in range(chosen_action.parallel_workers):
            prompt = (
                f"Task: '{self.task}'. Execute action: {chosen_action.action_id}. "
                f"Instructions: {chosen_action.description}."
            )
            assignments.append(
                WorkerAssignment(
                    steering_prompt=prompt,
                    context_artifact_ids=chosen_action.target_memory_ids,
                )
            )
        return False, None, assignments

    def execute_run(self) -> Tuple[Artifact, Dict[str, Any]]:
        logger.info("Executing Meta-Reasoning Run on task: %s", self.task)
        round_index = 0
        new_artifacts: List[Artifact] = []

        # Bootstrap: round 0
        init_worker = self.memory.write(
            round_index=0,
            worker_index=0,
            title="Initial Construction via Pigeonhole Principle",
            body="Partial argument outline. Lemma 1 base case gap present.",
            parent_ids=[],
            confidence="HIGH",
            correctness_label=0,
        )
        new_artifacts.append(init_worker)
        self.total_worker_calls += 1
        self.remaining_budget -= 1

        final_submission_id: Optional[str] = None

        while self.remaining_budget > 4 and round_index < 8:
            round_index += 1
            logger.info("--- CONTROL TURN %d (Budget remaining: %d) ---", round_index, self.remaining_budget)

            state = self.stage_assess(round_index, new_artifacts)
            proposals = self.stage_propose(state)
            selected_proposal = self.stage_evaluate(state, proposals)
            is_stop, submission_id, assignments = self.stage_dispatch(state, selected_proposal)

            if is_stop:
                final_submission_id = submission_id
                break

            new_artifacts = []
            for w_idx, assignment in enumerate(assignments):
                if self.remaining_budget <= 0:
                    break
                self._charge_budget(1, is_controller=False)
                is_repair = "REPAIR" in selected_proposal.action_id
                label = 1 if is_repair else 0
                body = (
                    "Complete, rigorous proof resolving the lemma gap."
                    if is_repair
                    else "Alternative path explored; encountered structural flaw."
                )
                w_artifact = self.memory.write(
                    round_index=round_index,
                    worker_index=w_idx,
                    title=f"Worker {round_index}_{w_idx}: {selected_proposal.action_id}",
                    body=body,
                    parent_ids=assignment.context_artifact_ids,
                    confidence="HIGH",
                    correctness_label=label,
                )
                new_artifacts.append(w_artifact)

        if not final_submission_id:
            frontier = self.memory.get_convergence_frontier()
            final_submission_id = frontier[-1].artifact_id if frontier else "0_0"

        submitted_artifact = self.memory.read([final_submission_id])[0]
        frontier = self.memory.get_convergence_frontier()

        fsg = MetacognitiveMetricsEvaluator.calculate_frontier_selection_gain(
            frontier, submitted_artifact
        )

        monitoring_pairs = []
        if self.state:
            for aid, assessment in self.state.candidate_assessments.items():
                art = self.memory._artifacts.get(aid)
                if art and art.correctness_label is not None:
                    monitoring_pairs.append((assessment.confidence_score, art.correctness_label))

        type2_auc = MetacognitiveMetricsEvaluator.calculate_type2_auc(monitoring_pairs)

        metrics = {
            "total_calls_consumed": self.nominal_budget - self.remaining_budget,
            "controller_calls": self.total_controller_calls,
            "worker_calls": self.total_worker_calls,
            "budget_utilization": (self.nominal_budget - self.remaining_budget) / self.nominal_budget,
            "submitted_artifact_id": submitted_artifact.artifact_id,
            "is_correct": submitted_artifact.correctness_label == 1,
            "frontier_size": len(frontier),
            "frontier_selection_gain": fsg,
            "controller_type2_auc": type2_auc,
        }
        return submitted_artifact, metrics


if __name__ == "__main__":
    memory_pool = PersistentArtifactMemory()
    runner = MetaReasoningController(
        task="IMO 2026 Problem 3: Formal combinatorial geometry proof",
        memory=memory_pool,
        model_call_budget=30,
    )
    result, telemetry = runner.execute_run()
    print("\n=======================================================")
    print("META-REASONING PIPELINE EXECUTION VERIFICATION")
    print("=======================================================")
    print(f"Submitted Artifact ID : {result.artifact_id}")
    print(f"Artifact Title        : {result.title}")
    print(f"Correctness Status    : {'PASSED (l=1)' if telemetry['is_correct'] else 'FAILED (l=0)'}")
    print(f"Budget Utilization    : {telemetry['budget_utilization'] * 100:.1f}%")
    print(f"Controller Calls      : {telemetry['controller_calls']}")
    print(f"Worker Calls          : {telemetry['worker_calls']}")
    print(f"Frontier Nodes Count  : {telemetry['frontier_size']}")
    print(f"Frontier Select Gain  : {telemetry['frontier_selection_gain']:+.3f}")
    print(f"Metacognitive AUC-2   : {telemetry['controller_type2_auc']:.3f}")
    print("=======================================================\n")
