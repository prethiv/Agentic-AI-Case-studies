"""
AQuA (Ambient Quality Agent) Production Outer Loop Reference Implementation.
=============================================================================
Reference implementation of the Ambient Quality Agent (AQuA) outer-loop system
for continuous agent quality engineering, out-of-band telemetry sweeping,
failure mechanism clustering, multi-transcript verification, and immutable
source-snapshot-anchored root cause diagnosis.

Inspired by Google's Cloud AI engineering reference architecture:
"The Outer Loop, Insights First: An Ambient Quality Agent That Diagnoses
Your Production Agent" (Google Developers Blog, Oct 2026).
"""

from __future__ import annotations

import difflib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple


# ============================================================================
# 1. Domain Models & Telemetry Representation
# ============================================================================

class RubricCategory(str, Enum):
    PROCEDURAL_COMPLIANCE = "procedural_compliance"
    TOOL_SELECTION_AND_ARGS = "tool_selection_and_args"
    CONTEXT_GROUNDING = "context_grounding"
    INTER_AGENT_DELEGATION = "inter_agent_delegation"
    CONSTRAINT_PRESERVATION = "constraint_preservation"
    STATE_SYNCHRONIZATION = "state_synchronization"
    TASK_COMPLETION = "task_completion"
    SAFETY_AND_GUARDRAILS = "safety_and_guardrails"
    FALLBACK_AND_RECOVERY = "fallback_and_recovery"


class InsightStatus(str, Enum):
    NEW = "NEW"
    RECURRING = "RECURRING"
    RESOLVED = "RESOLVED"
    DISMISSED = "DISMISSED"


@dataclass
class SpanRecord:
    span_id: str
    parent_span_id: Optional[str]
    agent_name: str
    turn_index: int
    role: str  # "user", "agent", "tool"
    content: str
    tool_name: Optional[str] = None
    tool_arguments: Optional[Dict[str, Any]] = None
    tool_output: Optional[Dict[str, Any]] = None
    state_delta: Optional[Dict[str, Any]] = None
    timestamp: float = field(default_factory=lambda: datetime.now(timezone.utc).timestamp())


@dataclass
class SessionTrajectory:
    session_id: str
    revision_id: str
    spans: List[SpanRecord]
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def total_spans(self) -> int:
        return len(self.spans)

    def get_user_turns(self) -> List[SpanRecord]:
        return [s for s in self.spans if s.role == "user"]

    def get_agent_spans(self, agent_name: Optional[str] = None) -> List[SpanRecord]:
        if agent_name:
            return [s for s in self.spans if s.agent_name == agent_name]
        return [s for s in self.spans if s.role == "agent"]


@dataclass
class DeveloperGoal:
    high_level_goal: str
    critical_failure_modes: List[str]
    noise_suppression_rules: List[str]


@dataclass
class ReviewFinding:
    finding_id: str
    session_id: str
    agent_name: str
    turn_index: int
    rubric_category: RubricCategory
    actual: str
    expected: str
    span_id: str
    failure_signature: str


@dataclass
class CandidateCluster:
    cluster_id: str
    failure_signature: str
    rubric_category: RubricCategory
    agent_name: str
    summary: str
    findings: List[ReviewFinding]
    session_ids: Set[str] = field(default_factory=set)

    def add_finding(self, finding: ReviewFinding) -> None:
        self.findings.append(finding)
        self.session_ids.add(finding.session_id)


@dataclass
class VerificationResult:
    cluster_id: str
    is_verified: bool
    rejection_reason: Optional[str] = None
    supporting_transcripts_count: int = 0
    confidence_evidence: str = ""


@dataclass
class CodeCitation:
    file_path: str
    start_line: int
    end_line: int
    code_snippet: str
    is_valid: bool = False


@dataclass
class ProposedEdit:
    file_path: str
    start_line: int
    end_line: int
    original_code: str
    replacement_code: str
    explanation: str

    def generate_unified_diff(self) -> str:
        orig_lines = self.original_code.splitlines(keepends=True)
        new_lines = self.replacement_code.splitlines(keepends=True)
        diff = difflib.unified_diff(
            orig_lines,
            new_lines,
            fromfile=f"a/{self.file_path} (L{self.start_line}-L{self.end_line})",
            tofile=f"b/{self.file_path}",
            lineterm="",
        )
        return "\n".join(diff)


@dataclass
class RootCauseDiagnosis:
    insight_id: str
    is_in_repository: bool
    citation: Optional[CodeCitation]
    proposed_edit: Optional[ProposedEdit]
    external_attribution: Optional[str]
    explanation: str


@dataclass
class VerifiedInsight:
    insight_id: str
    label: str
    failure_signature: str
    agent_name: str
    rubric_category: RubricCategory
    status: InsightStatus
    affected_session_ids: List[str]
    findings: List[ReviewFinding]
    first_seen_run_id: str
    last_seen_run_id: str
    days_unseen: int = 0
    root_cause: Optional[RootCauseDiagnosis] = None

    @property
    def trace_count(self) -> int:
        return len(self.affected_session_ids)


# ============================================================================
# 2. Immutable Source Snapshot Ledger
# ============================================================================

class SourceSnapshot:
    """Represents the immutable code tree captured at deployment time."""

    def __init__(self, revision_id: str, files: Dict[str, str]):
        self.revision_id = revision_id
        self._files: Dict[str, str] = dict(files)
        self._line_caches: Dict[str, List[str]] = {
            f: content.splitlines() for f, content in files.items()
        }

    @property
    def file_count(self) -> int:
        return len(self._files)

    def get_content(self, file_path: str) -> Optional[str]:
        return self._files.get(file_path)

    def validate_citation(self, file_path: str, start_line: int, end_line: int) -> Tuple[bool, str]:
        if file_path not in self._files:
            return False, f"File '{file_path}' does not exist in revision {self.revision_id}"
        lines = self._line_caches[file_path]
        if start_line < 1 or end_line > len(lines) or start_line > end_line:
            return False, (
                f"Line range {start_line}-{end_line} out of bounds for '{file_path}' "
                f"(total lines: {len(lines)})"
            )
        snippet = "\n".join(lines[start_line - 1 : end_line])
        return True, snippet


# ============================================================================
# 3. Five-Stage Sweep Engine
# ============================================================================

class TelemetrySampler:
    """Stage 1: Pulls bounded, budget-predictable samples from telemetry."""

    def __init__(self, max_sample_size: int = 1000):
        self.max_sample_size = max_sample_size

    def sample(self, all_sessions: List[SessionTrajectory]) -> List[SessionTrajectory]:
        # Bounded sample to keep execution cost deterministic and predictable
        if len(all_sessions) <= self.max_sample_size:
            return list(all_sessions)
        return all_sessions[: self.max_sample_size]


class SinglePassReviewer:
    """Stage 2: Single-pass session review against rubrics + developer goal."""

    def __init__(
        self,
        goal: DeveloperGoal,
        custom_metrics: Optional[List[Callable[[SessionTrajectory], Optional[ReviewFinding]]]] = None,
    ):
        self.goal = goal
        self.custom_metrics = custom_metrics or []

    def review_session(
        self,
        session: SessionTrajectory,
        agent_definitions: Dict[str, Dict[str, Any]],
    ) -> List[ReviewFinding]:
        findings: List[ReviewFinding] = []

        # 1. Deterministic Python Custom Metrics
        for metric in self.custom_metrics:
            finding = metric(session)
            if finding:
                findings.append(finding)

        # 2. Multi-turn Checklist Review (Simulated Evaluator Engine)
        spans = session.spans
        for i, span in enumerate(spans):
            # Check A: Implicit Precondition Bypass (Tool Skipping under User Coercion)
            if span.agent_name == "planning_agent" and span.state_delta:
                seats = span.state_delta.get("selected_seats")
                if seats:
                    # Look backwards: did flight_seat_selection_agent get invoked?
                    seat_checked = any(
                        s.agent_name == "flight_seat_selection_agent"
                        for s in spans[:i]
                    )
                    # Check if user explicitly asked to skip (anti-false-positive check)
                    user_asked_skip = any(
                        "skip seat" in s.content.lower() or "take any seat" in s.content.lower()
                        for s in spans[:i] if s.role == "user"
                    )
                    if not seat_checked and not user_asked_skip:
                        findings.append(
                            ReviewFinding(
                                finding_id=f"find_{session.session_id}_{span.turn_index}_seat",
                                session_id=session.session_id,
                                agent_name="planning_agent",
                                turn_index=span.turn_index,
                                rubric_category=RubricCategory.PROCEDURAL_COMPLIANCE,
                                actual=(
                                    f"When user volunteered seat {seats}, planning_agent saved seat "
                                    f"directly to session state without calling flight_seat_selection_agent."
                                ),
                                expected=(
                                    "planning_agent should call flight_seat_selection_agent to verify "
                                    "seat availability and pricing before committing to session state."
                                ),
                                span_id=span.span_id,
                                failure_signature="bypass_seat_selection_on_volunteered_seat",
                            )
                        )

            # Check B: Cross-Subagent Context Dropping (Dietary Profile Omission)
            if span.agent_name == "inspiration_agent" and span.tool_name == "delegate_to_place_agent":
                args = span.tool_arguments or {}
                # Check if traveler profile had dietary restriction
                profile_vegan = any(
                    "vegan" in s.content.lower() for s in spans[:i] if s.role == "user"
                )
                if profile_vegan and "vegan" not in json.dumps(args).lower():
                    findings.append(
                        ReviewFinding(
                            finding_id=f"find_{session.session_id}_{span.turn_index}_diet",
                            session_id=session.session_id,
                            agent_name="inspiration_agent",
                            turn_index=span.turn_index,
                            rubric_category=RubricCategory.INTER_AGENT_DELEGATION,
                            actual=(
                                "inspiration_agent forwarded trip request to place_agent without passing "
                                "the user's profile constraint (food_preference: vegan)."
                            ),
                            expected=(
                                "Subagent delegations must propagate user profile preferences and dietary "
                                "constraints in request parameters."
                            ),
                            span_id=span.span_id,
                            failure_signature="drop_dietary_constraints_across_subagents",
                        )
                    )

            # Check C: Prompt-to-Toolset Specification Contradiction (Empty Toolset)
            if span.agent_name == "poi_agent":
                agent_def = agent_definitions.get("poi_agent", {})
                declared_tools = agent_def.get("tools", [])
                if len(declared_tools) == 0 and "example.com" in span.content:
                    findings.append(
                        ReviewFinding(
                            finding_id=f"find_{session.session_id}_{span.turn_index}_poi",
                            session_id=session.session_id,
                            agent_name="poi_agent",
                            turn_index=span.turn_index,
                            rubric_category=RubricCategory.TOOL_SELECTION_AND_ARGS,
                            actual=(
                                "poi_agent fabricated placeholder URLs ('example.com') because it was "
                                "declared with tools=[] despite prompt requiring verified Maps Lite grounding."
                            ),
                            expected=(
                                "poi_agent must have Maps Lite tools bound, or prompt must not demand grounding."
                            ),
                            span_id=span.span_id,
                            failure_signature="empty_toolset_grounding_fabrication",
                        )
                    )

        return findings


class FailureClusterer:
    """Stage 3: Groups findings sharing common failure signatures into candidate clusters."""

    def cluster(self, findings: List[ReviewFinding]) -> List[CandidateCluster]:
        clusters_by_sig: Dict[str, CandidateCluster] = {}

        for finding in findings:
            sig = finding.failure_signature
            if sig not in clusters_by_sig:
                clusters_by_sig[sig] = CandidateCluster(
                    cluster_id=f"cluster_{sig}",
                    failure_signature=sig,
                    rubric_category=finding.rubric_category,
                    agent_name=finding.agent_name,
                    summary=finding.actual,
                    findings=[],
                )
            clusters_by_sig[sig].add_finding(finding)

        return list(clusters_by_sig.values())


class AdversarialVerifier:
    """Stage 4: Spot-checks candidate clusters against up to 3 full transcripts.
    
    Rejects false positives (e.g. user explicit overrides or mismatched merges).
    """

    def __init__(self, verification_sample_cap: int = 3):
        self.verification_sample_cap = verification_sample_cap

    def verify_cluster(
        self,
        cluster: CandidateCluster,
        sessions_map: Dict[str, SessionTrajectory],
        agent_definitions: Dict[str, Dict[str, Any]],
    ) -> VerificationResult:
        evidence_sessions = [
            sessions_map[sid]
            for sid in list(cluster.session_ids)[: self.verification_sample_cap]
            if sid in sessions_map
        ]

        if not evidence_sessions:
            return VerificationResult(
                cluster_id=cluster.cluster_id,
                is_verified=False,
                rejection_reason="No valid session transcripts available for verification.",
            )

        # Verification rule 1: False positive check on explicit user requests
        if cluster.failure_signature == "bypass_seat_selection_on_volunteered_seat":
            # Spot-check if user instructed agent to bypass
            overrides = 0
            for session in evidence_sessions:
                user_texts = " ".join([s.content.lower() for s in session.get_user_turns()])
                if "skip seat selection" in user_texts or "don't care about seat" in user_texts:
                    overrides += 1
            if overrides == len(evidence_sessions):
                return VerificationResult(
                    cluster_id=cluster.cluster_id,
                    is_verified=False,
                    rejection_reason=(
                        "Rejected: Traveler explicitly commanded agent to skip seat selection. "
                        "Agent adhered to direct user constraint override."
                    ),
                    supporting_transcripts_count=0,
                )

        # Verification rule 2: Check subagent definition contradiction
        if cluster.failure_signature == "empty_toolset_grounding_fabrication":
            poi_def = agent_definitions.get("poi_agent", {})
            if poi_def.get("tools"):
                return VerificationResult(
                    cluster_id=cluster.cluster_id,
                    is_verified=False,
                    rejection_reason="Rejected: poi_agent does have tools configured in active deployment.",
                )

        # Survived verification
        return VerificationResult(
            cluster_id=cluster.cluster_id,
            is_verified=True,
            supporting_transcripts_count=len(evidence_sessions),
            confidence_evidence=(
                f"Verified against {len(evidence_sessions)} full session transcripts. "
                f"Failure mechanism confirmed across agent '{cluster.agent_name}'."
            ),
        )


class InsightLedger:
    """Stage 5: State-machine tracking in BigQuery / storage (NEW, RECURRING, RESOLVED, DISMISSED)."""

    def __init__(self, auto_resolve_days: int = 14):
        self.auto_resolve_days = auto_resolve_days
        self._insights: Dict[str, VerifiedInsight] = {}

    def get_all_insights(self) -> List[VerifiedInsight]:
        return list(self._insights.values())

    def get_insight(self, insight_id: str) -> Optional[VerifiedInsight]:
        return self._insights.get(insight_id)

    def dismiss_insight(self, insight_id: str) -> bool:
        insight = self._insights.get(insight_id)
        if insight:
            insight.status = InsightStatus.DISMISSED
            return True
        return False

    def update_with_sweep(
        self,
        verified_clusters: List[CandidateCluster],
        current_run_id: str,
    ) -> List[VerifiedInsight]:
        seen_signatures: Set[str] = set()
        active_insights: List[VerifiedInsight] = []

        for cluster in verified_clusters:
            sig = cluster.failure_signature
            seen_signatures.add(sig)

            # Match against existing insight
            existing: Optional[VerifiedInsight] = None
            for ins in self._insights.values():
                if ins.failure_signature == sig:
                    existing = ins
                    break

            if existing:
                if existing.status == InsightStatus.DISMISSED:
                    # Respect permanent dismissal
                    continue
                # Update recurring
                existing.status = InsightStatus.RECURRING
                existing.last_seen_run_id = current_run_id
                existing.days_unseen = 0
                existing.affected_session_ids = list(cluster.session_ids)
                existing.findings = cluster.findings
                active_insights.append(existing)
            else:
                # Brand new insight
                new_insight = VerifiedInsight(
                    insight_id=f"ins_{abs(hash(sig)) % 100000000:08x}",
                    label=cluster.summary,
                    failure_signature=sig,
                    agent_name=cluster.agent_name,
                    rubric_category=cluster.rubric_category,
                    status=InsightStatus.NEW,
                    affected_session_ids=list(cluster.session_ids),
                    findings=cluster.findings,
                    first_seen_run_id=current_run_id,
                    last_seen_run_id=current_run_id,
                    days_unseen=0,
                )
                self._insights[new_insight.insight_id] = new_insight
                active_insights.append(new_insight)

        # Check unseen insights for auto-resolution
        for ins in self._insights.values():
            if ins.failure_signature not in seen_signatures and ins.status in (
                InsightStatus.NEW,
                InsightStatus.RECURRING,
            ):
                ins.days_unseen += 1
                if ins.days_unseen >= self.auto_resolve_days:
                    ins.status = InsightStatus.RESOLVED

        return active_insights


# ============================================================================
# 4. Code-Anchored Root Cause Diagnosis Engine
# ============================================================================

class SourceAnchoredDiagnoser:
    """Diagnoses verified insights anchored to immutable source snapshot."""

    def __init__(self, snapshot: SourceSnapshot):
        self.snapshot = snapshot

    def diagnose(self, insight: VerifiedInsight) -> RootCauseDiagnosis:
        sig = insight.failure_signature

        if sig == "bypass_seat_selection_on_volunteered_seat":
            file_path = "travel_concierge/sub_agents/planning/prompt.py"
            start_line, end_line = 90, 95
            is_valid, snippet = self.snapshot.validate_citation(file_path, start_line, end_line)

            citation = CodeCitation(
                file_path=file_path,
                start_line=start_line,
                end_line=end_line,
                code_snippet=snippet if is_valid else "",
                is_valid=is_valid,
            )

            original_code = (
                "if user_wants_seat_map:\n"
                "    delegate_to(flight_seat_selection_agent)\n"
                "else:\n"
                "    save_flight_to_state(flight)"
            )
            replacement_code = (
                "if user_wants_seat_map or volunteered_seat_number:\n"
                "    # Always verify seat availability via flight_seat_selection_agent\n"
                "    delegate_to(flight_seat_selection_agent, verify_seat=volunteered_seat_number)\n"
                "else:\n"
                "    save_flight_to_state(flight)"
            )

            proposed_edit = ProposedEdit(
                file_path=file_path,
                start_line=start_line,
                end_line=end_line,
                original_code=original_code,
                replacement_code=replacement_code,
                explanation=(
                    "Update flight-selection instruction to explicitly require calling "
                    "flight_seat_selection_agent when a user volunteers a seat number directly."
                ),
            )

            diagnosis = RootCauseDiagnosis(
                insight_id=insight.insight_id,
                is_in_repository=True,
                citation=citation,
                proposed_edit=proposed_edit,
                external_attribution=None,
                explanation=(
                    f"Root cause in {file_path}:{start_line}-{end_line}. The prompt instructions "
                    f"only branch to flight_seat_selection_agent when rendering seat maps, "
                    f"bypassing verification when the user volunteers seat numbers."
                ),
            )
            insight.root_cause = diagnosis
            return diagnosis

        elif sig == "drop_dietary_constraints_across_subagents":
            file_path = "travel_concierge/sub_agents/inspiration/prompt.py"
            start_line, end_line = 20, 25
            is_valid, snippet = self.snapshot.validate_citation(file_path, start_line, end_line)

            citation = CodeCitation(
                file_path=file_path,
                start_line=start_line,
                end_line=end_line,
                code_snippet=snippet if is_valid else "",
                is_valid=is_valid,
            )

            original_code = (
                "def delegate_to_place_agent(city):\n"
                "    return place_agent.search(city=city)"
            )
            replacement_code = (
                "def delegate_to_place_agent(city):\n"
                "    # Propagate dietary preferences and user profile restrictions\n"
                "    dietary = session_state.get('food_preference', None)\n"
                "    return place_agent.search(city=city, dietary_restrictions=dietary)"
            )

            proposed_edit = ProposedEdit(
                file_path=file_path,
                start_line=start_line,
                end_line=end_line,
                original_code=original_code,
                replacement_code=replacement_code,
                explanation="Forward user profile constraints (food_preference) across place_agent tool delegation.",
            )

            diagnosis = RootCauseDiagnosis(
                insight_id=insight.insight_id,
                is_in_repository=True,
                citation=citation,
                proposed_edit=proposed_edit,
                external_attribution=None,
                explanation=(
                    f"Root cause in {file_path}:{start_line}-{end_line}. Subagent delegation wrapper "
                    f"fails to forward session_state dietary restrictions."
                ),
            )
            insight.root_cause = diagnosis
            return diagnosis

        elif sig == "empty_toolset_grounding_fabrication":
            file_path = "travel_concierge/sub_agents/poi/agent.py"
            start_line, end_line = 10, 15
            is_valid, snippet = self.snapshot.validate_citation(file_path, start_line, end_line)

            citation = CodeCitation(
                file_path=file_path,
                start_line=start_line,
                end_line=end_line,
                code_snippet=snippet if is_valid else "",
                is_valid=is_valid,
            )

            original_code = "poi_agent = Agent(name='poi_agent', tools=[])"
            replacement_code = (
                "from google_maps_grounding import MapsGroundingLite\n"
                "poi_agent = Agent(name='poi_agent', tools=[MapsGroundingLite()])"
            )

            proposed_edit = ProposedEdit(
                file_path=file_path,
                start_line=start_line,
                end_line=end_line,
                original_code=original_code,
                replacement_code=replacement_code,
                explanation="Bind MapsGroundingLite tool to poi_agent to satisfy prompt grounding requirements.",
            )

            diagnosis = RootCauseDiagnosis(
                insight_id=insight.insight_id,
                is_in_repository=True,
                citation=citation,
                proposed_edit=proposed_edit,
                external_attribution=None,
                explanation=f"Root cause in {file_path}:{start_line}-{end_line}. Empty tool list contradiction.",
            )
            insight.root_cause = diagnosis
            return diagnosis

        else:
            # External or upstream defect
            diagnosis = RootCauseDiagnosis(
                insight_id=insight.insight_id,
                is_in_repository=False,
                citation=None,
                proposed_edit=None,
                external_attribution="Upstream external microservice or retrieved third-party payload error.",
                explanation="Defect lies outside repository code. No code edit proposed.",
            )
            insight.root_cause = diagnosis
            return diagnosis


# ============================================================================
# 5. Closed-Loop Replay Synthesizer
# ============================================================================

class ReplaySynthesizer:
    """Extracts user turns and initial state from failing sessions for deterministic inner-loop replay."""

    @staticmethod
    def extract_replay_fixture(session: SessionTrajectory) -> Dict[str, Any]:
        user_turns = [s.content for s in session.get_user_turns()]
        return {
            "session_id": session.session_id,
            "revision_id": session.revision_id,
            "state": {},
            "queries": user_turns,
        }


# ============================================================================
# 6. AQuA Orchestration Pipeline
# ============================================================================

class AquaPipeline:
    """End-to-End Ambient Quality Agent Sweep & Diagnostic Pipeline."""

    def __init__(
        self,
        snapshot: SourceSnapshot,
        goal: DeveloperGoal,
        agent_definitions: Dict[str, Dict[str, Any]],
        sampler_cap: int = 1000,
    ):
        self.snapshot = snapshot
        self.goal = goal
        self.agent_definitions = agent_definitions
        self.sampler = TelemetrySampler(max_sample_size=sampler_cap)
        self.reviewer = SinglePassReviewer(goal=goal)
        self.clusterer = FailureClusterer()
        self.verifier = AdversarialVerifier()
        self.ledger = InsightLedger()
        self.diagnoser = SourceAnchoredDiagnoser(snapshot=snapshot)

    def run_sweep(
        self,
        run_id: str,
        sessions: List[SessionTrajectory],
    ) -> Dict[str, Any]:
        # 1. Sample
        sampled = self.sampler.sample(sessions)
        sessions_map = {s.session_id: s for s in sampled}

        # 2. Review
        all_findings: List[ReviewFinding] = []
        for session in sampled:
            findings = self.reviewer.review_session(session, self.agent_definitions)
            all_findings.extend(findings)

        # 3. Cluster
        candidate_clusters = self.clusterer.cluster(all_findings)

        # 4. Verify
        verified_clusters: List[CandidateCluster] = []
        rejected_clusters: List[Tuple[CandidateCluster, str]] = []

        for cluster in candidate_clusters:
            res = self.verifier.verify_cluster(cluster, sessions_map, self.agent_definitions)
            if res.is_verified:
                verified_clusters.append(cluster)
            else:
                rejected_clusters.append((cluster, res.rejection_reason or "Unknown rejection"))

        # 5. Track
        active_insights = self.ledger.update_with_sweep(verified_clusters, run_id)

        return {
            "run_id": run_id,
            "sampled_sessions_count": len(sampled),
            "total_findings_count": len(all_findings),
            "candidate_clusters_count": len(candidate_clusters),
            "verified_clusters_count": len(verified_clusters),
            "rejected_clusters_count": len(rejected_clusters),
            "active_insights": active_insights,
            "rejected_details": rejected_clusters,
        }

    def diagnose_insight(self, insight_id: str) -> Optional[RootCauseDiagnosis]:
        insight = self.ledger.get_insight(insight_id)
        if not insight:
            return None
        return self.diagnoser.diagnose(insight)
