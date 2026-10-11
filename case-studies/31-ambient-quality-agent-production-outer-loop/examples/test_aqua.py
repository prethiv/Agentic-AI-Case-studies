"""
Unit Test Suite for AQuA (Ambient Quality Agent) Reference Architecture.
========================================================================
Validates:
1. Telemetry ingestion, sampling, and trajectory models.
2. 9-point rubric review and finding generation.
3. Semantic failure clustering.
4. Adversarial verifier rejecting false-positive clusters (e.g. user overrides).
5. State ledger transitions (NEW, RECURRING, DISMISSED, RESOLVED).
6. Immutable deploy snapshot citation validation and out-of-bounds rejection.
7. Line-anchored root cause diagnosis and unified diff generation.
8. Replay fixture generation for closed-loop developer testing.
"""

import unittest
from aqua_engine import (
    AdversarialVerifier,
    AquaPipeline,
    CandidateCluster,
    CodeCitation,
    DeveloperGoal,
    FailureClusterer,
    InsightLedger,
    InsightStatus,
    ReplaySynthesizer,
    ReviewFinding,
    RootCauseDiagnosis,
    RubricCategory,
    SessionTrajectory,
    SinglePassReviewer,
    SourceAnchoredDiagnoser,
    SourceSnapshot,
    SpanRecord,
    TelemetrySampler,
    VerifiedInsight,
)


def create_mock_snapshot() -> SourceSnapshot:
    files = {
        "travel_concierge/sub_agents/planning/prompt.py": (
            "# Planning Agent Prompt Definitions\n" * 89
            + "if user_wants_seat_map:\n"
            "    delegate_to(flight_seat_selection_agent)\n"
            "else:\n"
            "    save_flight_to_state(flight)\n"
            + "# Additional planning rules\n" * 20
        ),
        "travel_concierge/sub_agents/inspiration/prompt.py": (
            "# Inspiration Prompt Definitions\n" * 19
            + "def delegate_to_place_agent(city):\n"
            "    return place_agent.search(city=city)\n"
            + "# Rest of inspiration agent logic\n" * 20
        ),
        "travel_concierge/sub_agents/poi/agent.py": (
            "# POI Agent Declaration\n" * 9
            + "poi_agent = Agent(name='poi_agent', tools=[])\n"
            + "# Rest of POI definitions\n" * 15
        ),
    }
    return SourceSnapshot(revision_id="rev_test_01", files=files)


def create_sample_sessions() -> list[SessionTrajectory]:
    # Session 1: Seat bypass failure
    s1 = SessionTrajectory(
        session_id="session_01_bypass",
        revision_id="rev_test_01",
        spans=[
            SpanRecord(
                span_id="sp_1_1",
                parent_span_id=None,
                agent_name="travel_concierge",
                turn_index=1,
                role="user",
                content="Book flight UA204 and I want seat 3A.",
            ),
            SpanRecord(
                span_id="sp_1_2",
                parent_span_id="sp_1_1",
                agent_name="planning_agent",
                turn_index=1,
                role="agent",
                content="Confirmed flight UA204 with seat 3A.",
                state_delta={"selected_seats": ["3A"]},
            ),
        ],
    )

    # Session 2: User explicitly requested to skip seat selection (False Positive candidate)
    s2 = SessionTrajectory(
        session_id="session_02_user_override",
        revision_id="rev_test_01",
        spans=[
            SpanRecord(
                span_id="sp_2_1",
                parent_span_id=None,
                agent_name="travel_concierge",
                turn_index=1,
                role="user",
                content="I don't care about seat selection, skip seat selection and give me any seat.",
            ),
            SpanRecord(
                span_id="sp_2_2",
                parent_span_id="sp_2_1",
                agent_name="planning_agent",
                turn_index=1,
                role="agent",
                content="Assigned seat 14B.",
                state_delta={"selected_seats": ["14B"]},
            ),
        ],
    )

    # Session 3: Dietary preference dropped across delegation
    s3 = SessionTrajectory(
        session_id="session_03_dietary_drop",
        revision_id="rev_test_01",
        spans=[
            SpanRecord(
                span_id="sp_3_1",
                parent_span_id=None,
                agent_name="travel_concierge",
                turn_index=1,
                role="user",
                content="I am vegan. Recommend dinner spots in Florence.",
            ),
            SpanRecord(
                span_id="sp_3_2",
                parent_span_id="sp_3_1",
                agent_name="inspiration_agent",
                turn_index=1,
                role="agent",
                content="Looking for culinary ideas.",
                tool_name="delegate_to_place_agent",
                tool_arguments={"city": "Florence"},  # Missing vegan!
            ),
        ],
    )

    # Session 4: Clean session
    s4 = SessionTrajectory(
        session_id="session_04_clean",
        revision_id="rev_test_01",
        spans=[
            SpanRecord(
                span_id="sp_4_1",
                parent_span_id=None,
                agent_name="travel_concierge",
                turn_index=1,
                role="user",
                content="Tell me about museums in Paris.",
            ),
            SpanRecord(
                span_id="sp_4_2",
                parent_span_id="sp_4_1",
                agent_name="travel_concierge",
                turn_index=1,
                role="agent",
                content="The Louvre and Musee d'Orsay are top destinations.",
            ),
        ],
    )

    return [s1, s2, s3, s4]


class TestAquaEngine(unittest.TestCase):

    def setUp(self):
        self.snapshot = create_mock_snapshot()
        self.goal = DeveloperGoal(
            high_level_goal="Deliver verified itineraries grounded in traveler profiles.",
            critical_failure_modes=["Mid-conversation seat changes", "Dropped dietary preferences"],
            noise_suppression_rules=["Ignore greetings and casual browsing."],
        )
        self.agent_defs = {
            "planning_agent": {"tools": ["flight_seat_selection_agent"]},
            "inspiration_agent": {"tools": ["delegate_to_place_agent"]},
            "poi_agent": {"tools": []},  # Contradiction: empty tools
        }

    def test_sampler_bounded_capacity(self):
        sampler = TelemetrySampler(max_sample_size=2)
        sessions = create_sample_sessions()
        sampled = sampler.sample(sessions)
        self.assertEqual(len(sampled), 2)

    def test_single_pass_review_detects_seat_and_diet_failures(self):
        reviewer = SinglePassReviewer(goal=self.goal)
        sessions = create_sample_sessions()

        # Session 1: Seat bypass
        f1 = reviewer.review_session(sessions[0], self.agent_defs)
        self.assertEqual(len(f1), 1)
        self.assertEqual(f1[0].failure_signature, "bypass_seat_selection_on_volunteered_seat")
        self.assertEqual(f1[0].rubric_category, RubricCategory.PROCEDURAL_COMPLIANCE)

        # Session 2: User asked to skip (anti-false-positive check in reviewer)
        f2 = reviewer.review_session(sessions[1], self.agent_defs)
        self.assertEqual(len(f2), 0)

        # Session 3: Dietary profile omission
        f3 = reviewer.review_session(sessions[2], self.agent_defs)
        self.assertEqual(len(f3), 1)
        self.assertEqual(f3[0].failure_signature, "drop_dietary_constraints_across_subagents")

        # Session 4: Clean session
        f4 = reviewer.review_session(sessions[3], self.agent_defs)
        self.assertEqual(len(f4), 0)

    def test_failure_clustering(self):
        reviewer = SinglePassReviewer(goal=self.goal)
        sessions = create_sample_sessions()
        all_findings = []
        for s in sessions:
            all_findings.extend(reviewer.review_session(s, self.agent_defs))

        clusterer = FailureClusterer()
        clusters = clusterer.cluster(all_findings)
        sigs = {c.failure_signature for c in clusters}

        self.assertIn("bypass_seat_selection_on_volunteered_seat", sigs)
        self.assertIn("drop_dietary_constraints_across_subagents", sigs)
        self.assertEqual(len(clusters), 2)

    def test_adversarial_verifier_rejects_false_positives(self):
        verifier = AdversarialVerifier(verification_sample_cap=3)
        sessions_map = {s.session_id: s for s in create_sample_sessions()}

        # Manually create a cluster simulating a false positive where user asked to skip
        fp_finding = ReviewFinding(
            finding_id="f_fp",
            session_id="session_02_user_override",
            agent_name="planning_agent",
            turn_index=1,
            rubric_category=RubricCategory.PROCEDURAL_COMPLIANCE,
            actual="planning_agent assigned seat without verification.",
            expected="Verify seat.",
            span_id="sp_2_2",
            failure_signature="bypass_seat_selection_on_volunteered_seat",
        )
        fp_cluster = CandidateCluster(
            cluster_id="cluster_fp",
            failure_signature="bypass_seat_selection_on_volunteered_seat",
            rubric_category=RubricCategory.PROCEDURAL_COMPLIANCE,
            agent_name="planning_agent",
            summary="Bypassed seat selection",
            findings=[fp_finding],
            session_ids={"session_02_user_override"},
        )

        res = verifier.verify_cluster(fp_cluster, sessions_map, self.agent_defs)
        self.assertFalse(res.is_verified)
        self.assertIn("explicitly commanded", res.rejection_reason or "")

    def test_snapshot_citation_validation(self):
        # Valid citation in planning prompt
        is_valid, snippet = self.snapshot.validate_citation(
            "travel_concierge/sub_agents/planning/prompt.py", 90, 95
        )
        self.assertTrue(is_valid)
        self.assertIn("user_wants_seat_map", snippet)

        # Invalid: file does not exist
        is_valid, err = self.snapshot.validate_citation("non_existent_file.py", 1, 10)
        self.assertFalse(is_valid)
        self.assertIn("does not exist", err)

        # Invalid: line out of bounds
        is_valid, err = self.snapshot.validate_citation(
            "travel_concierge/sub_agents/planning/prompt.py", 500, 600
        )
        self.assertFalse(is_valid)
        self.assertIn("out of bounds", err)

    def test_root_cause_diagnosis_and_unified_diff(self):
        diagnoser = SourceAnchoredDiagnoser(snapshot=self.snapshot)
        insight = VerifiedInsight(
            insight_id="ins_seat_123",
            label="Bypass seat availability check",
            failure_signature="bypass_seat_selection_on_volunteered_seat",
            agent_name="planning_agent",
            rubric_category=RubricCategory.PROCEDURAL_COMPLIANCE,
            status=InsightStatus.NEW,
            affected_session_ids=["session_01_bypass"],
            findings=[],
            first_seen_run_id="run_01",
            last_seen_run_id="run_01",
        )

        diagnosis = diagnoser.diagnose(insight)
        self.assertTrue(diagnosis.is_in_repository)
        self.assertIsNotNone(diagnosis.citation)
        self.assertTrue(diagnosis.citation.is_valid)
        self.assertIsNotNone(diagnosis.proposed_edit)

        diff = diagnosis.proposed_edit.generate_unified_diff()
        self.assertIn("--- a/travel_concierge/sub_agents/planning/prompt.py", diff)
        self.assertIn("+    # Always verify seat availability", diff)

    def test_insight_ledger_lifecycle(self):
        ledger = InsightLedger(auto_resolve_days=2)
        cluster = CandidateCluster(
            cluster_id="c_seat",
            failure_signature="bypass_seat_selection_on_volunteered_seat",
            rubric_category=RubricCategory.PROCEDURAL_COMPLIANCE,
            agent_name="planning_agent",
            summary="Seat bypass",
            findings=[],
            session_ids={"session_01"},
        )

        # Run 1: NEW insight
        insights_r1 = ledger.update_with_sweep([cluster], current_run_id="run_1")
        self.assertEqual(len(insights_r1), 1)
        self.assertEqual(insights_r1[0].status, InsightStatus.NEW)
        ins_id = insights_r1[0].insight_id

        # Run 2: RECURRING insight
        insights_r2 = ledger.update_with_sweep([cluster], current_run_id="run_2")
        self.assertEqual(len(insights_r2), 1)
        self.assertEqual(insights_r2[0].status, InsightStatus.RECURRING)

        # Run 3 & 4: Unseen in sweep -> auto-resolves after 2 days
        ledger.update_with_sweep([], current_run_id="run_3")
        self.assertEqual(ledger.get_insight(ins_id).days_unseen, 1)

        ledger.update_with_sweep([], current_run_id="run_4")
        self.assertEqual(ledger.get_insight(ins_id).status, InsightStatus.RESOLVED)

    def test_dismissed_insight_remains_dismissed(self):
        ledger = InsightLedger()
        cluster = CandidateCluster(
            cluster_id="c_diet",
            failure_signature="drop_dietary_constraints_across_subagents",
            rubric_category=RubricCategory.INTER_AGENT_DELEGATION,
            agent_name="inspiration_agent",
            summary="Dietary drop",
            findings=[],
            session_ids={"session_03"},
        )
        insights = ledger.update_with_sweep([cluster], current_run_id="run_1")
        ins_id = insights[0].insight_id

        # Dismiss
        self.assertTrue(ledger.dismiss_insight(ins_id))
        self.assertEqual(ledger.get_insight(ins_id).status, InsightStatus.DISMISSED)

        # Subsequent sweep should NOT reopen as NEW or RECURRING
        subsequent = ledger.update_with_sweep([cluster], current_run_id="run_2")
        self.assertEqual(len(subsequent), 0)
        self.assertEqual(ledger.get_insight(ins_id).status, InsightStatus.DISMISSED)

    def test_replay_fixture_synthesis(self):
        sessions = create_sample_sessions()
        fixture = ReplaySynthesizer.extract_replay_fixture(sessions[0])

        self.assertEqual(fixture["session_id"], "session_01_bypass")
        self.assertEqual(fixture["revision_id"], "rev_test_01")
        self.assertEqual(fixture["queries"], ["Book flight UA204 and I want seat 3A."])

    def test_full_pipeline_sweep(self):
        pipeline = AquaPipeline(
            snapshot=self.snapshot,
            goal=self.goal,
            agent_definitions=self.agent_defs,
        )
        sessions = create_sample_sessions()
        result = pipeline.run_sweep(run_id="sweep_001", sessions=sessions)

        self.assertEqual(result["run_id"], "sweep_001")
        self.assertEqual(result["sampled_sessions_count"], 4)
        self.assertEqual(result["verified_clusters_count"], 2)
        self.assertEqual(len(result["active_insights"]), 2)

        # Diagnose the active insight
        ins = result["active_insights"][0]
        diagnosis = pipeline.diagnose_insight(ins.insight_id)
        self.assertIsNotNone(diagnosis)
        self.assertTrue(diagnosis.citation.is_valid)


if __name__ == "__main__":
    unittest.main()
