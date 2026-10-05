"""
Case Study 30: Multi-Agent Mesh Architecture Reference Implementation
======================================================================
A decentralized, cloud-native Agent-to-Agent (A2A) mesh framework demonstrating:
  1. Peer-to-Peer Agent Nodes with Decentralized Identifiers (DIDs).
  2. Semantic Capability Registry & Multi-Attribute Intent Routing.
  3. Game-Theoretic Contract Net Protocol (CNP) RFP & Bidding Engine.
  4. Cognitive Sidecar Proxy enforcing Monotonic Hop Decrement & Cycle Prevention.
  5. Token Velocity Circuit Breakers (Closed/Open/Half-Open state machine).
  6. OpenTelemetry-Compatible Distributed GenAI Tracing & Causal DAG Ledger.
"""

from __future__ import annotations

import dataclasses
import enum
import hashlib
import json
import math
import re
import time
import uuid
from typing import Any, Callable, Dict, List, Optional, Set, Tuple


# ============================================================================
# 1. OpenTelemetry Distributed Tracing & Causal DAG Ledger
# ============================================================================

@dataclasses.dataclass
class OTelSpan:
    """Represents a distributed span compliant with OpenTelemetry GenAI conventions."""
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    agent_did: str
    agent_role: str
    action_name: str
    start_time: float
    end_time: Optional[float] = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    status: str = "OK"  # "OK" | "ERROR" | "CIRCUIT_BREAKER"
    attributes: Dict[str, Any] = dataclasses.field(default_factory=dict)

    def duration_ms(self) -> float:
        if self.end_time:
            return round((self.end_time - self.start_time) * 1000, 2)
        return 0.0


class DistributedTraceCollector:
    """In-memory telemetry collector recording distributed cognitive causal traces."""

    def __init__(self):
        self.spans: List[OTelSpan] = []

    def start_span(
        self,
        trace_id: str,
        parent_span_id: Optional[str],
        agent_did: str,
        agent_role: str,
        action_name: str,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> OTelSpan:
        span = OTelSpan(
            trace_id=trace_id,
            span_id=uuid.uuid4().hex[:16],
            parent_span_id=parent_span_id,
            agent_did=agent_did,
            agent_role=agent_role,
            action_name=action_name,
            start_time=time.time(),
            attributes=attributes or {},
        )
        self.spans.append(span)
        return span

    def finish_span(
        self,
        span: OTelSpan,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        status: str = "OK",
        attributes: Optional[Dict[str, Any]] = None,
    ):
        span.end_time = time.time()
        span.prompt_tokens = prompt_tokens
        span.completion_tokens = completion_tokens
        span.status = status
        if attributes:
            span.attributes.update(attributes)

    def export_trace_summary(self, trace_id: str) -> Dict[str, Any]:
        trace_spans = [s for s in self.spans if s.trace_id == trace_id]
        total_tokens = sum(s.prompt_tokens + s.completion_tokens for s in trace_spans)
        total_duration = max((s.end_time or s.start_time) for s in trace_spans) - min(s.start_time for s in trace_spans) if trace_spans else 0.0

        return {
            "trace_id": trace_id,
            "total_spans": len(trace_spans),
            "total_tokens_consumed": total_tokens,
            "total_duration_ms": round(total_duration * 1000, 2),
            "spans": [
                {
                    "span_id": s.span_id,
                    "parent_span_id": s.parent_span_id,
                    "agent": f"{s.agent_role} ({s.agent_did})",
                    "action": s.action_name,
                    "status": s.status,
                    "duration_ms": s.duration_ms(),
                    "tokens": s.prompt_tokens + s.completion_tokens,
                }
                for s in trace_spans
            ],
        }

    def render_mermaid_dag(self, trace_id: str) -> str:
        """Renders the causal trace execution as a valid Mermaid graph."""
        trace_spans = [s for s in self.spans if s.trace_id == trace_id]
        lines = ["graph TD"]
        for s in trace_spans:
            node_label = f'"{s.agent_role}: {s.action_name} ({s.status})"'
            lines.append(f"    span_{s.span_id}[{node_label}]")
            if s.parent_span_id:
                lines.append(f'    span_{s.parent_span_id} -->|"hops to"| span_{s.span_id}')
        return "\n".join(lines)


# ============================================================================
# 2. A2A Wire Protocol & Cryptographic Macaroon Envelope
# ============================================================================

@dataclasses.dataclass
class A2AMessageEnvelope:
    """Standardized Agent-to-Agent wire envelope containing routing & security metadata."""
    message_id: str
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    sender_did: str
    recipient_did: str
    intent: str
    payload: Dict[str, Any]
    hop_limit: int = 5
    delegation_chain: List[str] = dataclasses.field(default_factory=list)
    token_budget_remaining: int = 16000
    macaroon_signature: str = ""
    timestamp: float = dataclasses.field(default_factory=time.time)

    def create_attenuated_child(
        self,
        new_recipient_did: str,
        new_intent: str,
        new_payload: Dict[str, Any],
        allocated_token_budget: int,
    ) -> A2AMessageEnvelope:
        """Derives a cryptographically bounded child message envelope."""
        child_chain = list(self.delegation_chain)
        if self.sender_did not in child_chain:
            child_chain.append(self.sender_did)

        # Attenuate token budget: child cannot exceed allocated or remaining
        bounded_budget = min(allocated_token_budget, self.token_budget_remaining)

        # Simple HMAC-like signature simulation for attenuated capabilities
        sig_body = f"{self.trace_id}:{new_recipient_did}:{bounded_budget}:{len(child_chain)}"
        child_sig = hashlib.sha256(sig_body.encode()).hexdigest()[:16]

        return A2AMessageEnvelope(
            message_id=f"msg-{uuid.uuid4().hex[:8]}",
            trace_id=self.trace_id,
            span_id=uuid.uuid4().hex[:16],
            parent_span_id=self.span_id,
            sender_did=self.recipient_did,  # Current recipient becomes sender
            recipient_did=new_recipient_did,
            intent=new_intent,
            payload=new_payload,
            hop_limit=self.hop_limit - 1,  # Strict monotonic decrement
            delegation_chain=child_chain,
            token_budget_remaining=bounded_budget,
            macaroon_signature=child_sig,
        )


# ============================================================================
# 3. Semantic Capability Registry & Multi-Attribute Routing
# ============================================================================

def _text_to_feature_vector(text: str, dim: int = 16) -> List[float]:
    """Generates a normalized deterministic mock embedding vector from semantic text."""
    tokens = set(re.findall(r"\w+", text.lower()))
    h = hashlib.sha256(text.lower().encode()).digest()
    vec = [(h[i % len(h)] / 255.0) - 0.5 for i in range(dim)]
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


def compute_semantic_similarity(query_text: str, cap_text: str, cap_vector: List[float]) -> float:
    """Computes a hybrid lexical-semantic similarity score in [0.0, 1.0]."""
    q_tokens = set(re.findall(r"[a-z0-9]+", query_text.lower()))
    c_tokens = set(re.findall(r"[a-z0-9]+", cap_text.lower()))
    overlap = len(q_tokens.intersection(c_tokens)) / float(max(1, len(q_tokens))) if q_tokens else 0.0

    q_vec = _text_to_feature_vector(query_text)
    dot = sum(a * b for a, b in zip(q_vec, cap_vector))
    norm1 = math.sqrt(sum(a * a for a in q_vec)) or 1.0
    norm2 = math.sqrt(sum(b * b for b in cap_vector)) or 1.0
    cos = max(0.0, min(1.0, (dot / (norm1 * norm2) + 1.0) / 2.0))

    # Weight lexical overlap 70% and vector cosine 30% for robust deterministic matching
    return round((0.70 * overlap) + (0.30 * cos), 4)


@dataclasses.dataclass
class CapabilityDescriptor:
    intent_name: str
    description: str
    semantic_vector: List[float]
    confidence_floor: float = 0.8
    cost_per_token: float = 0.00002
    avg_latency_ms: float = 400.0


@dataclasses.dataclass
class PeerProfile:
    did: str
    role: str
    endpoint: str
    capabilities: List[CapabilityDescriptor]
    trust_score: float = 0.95
    is_active: bool = True
    active_load: float = 0.1  # 0.0 to 1.0


class CapabilityRegistry:
    """Decentralized or local registry tracking peer capabilities and routing scores."""

    def __init__(self):
        self.peers: Dict[str, PeerProfile] = {}

    def register_peer(self, peer: PeerProfile):
        self.peers[peer.did] = peer

    def deregister_peer(self, did: str):
        if did in self.peers:
            self.peers[did].is_active = False

    def route_intent(
        self,
        query_intent: str,
        query_description: str,
        exclude_dids: Optional[Set[str]] = None,
        weights: Tuple[float, float, float, float] = (0.50, 0.25, 0.15, 0.10),
    ) -> Optional[Tuple[PeerProfile, float]]:
        """
        Calculates Pareto routing score across candidates:
        Score = w1*Similarity + w2*Trust - w3*LatencyNorm - w4*CostNorm
        """
        exclude = exclude_dids or set()
        query_vec = _text_to_feature_vector(f"{query_intent} {query_description}")
        w_sim, w_trust, w_lat, w_cost = weights

        best_peer: Optional[PeerProfile] = None
        best_score = -1.0

        for peer in self.peers.values():
            if not peer.is_active or peer.did in exclude:
                continue

            # Find best matching capability for this peer
            max_sim = 0.0
            query_full = f"{query_intent} {query_description}"
            for cap in peer.capabilities:
                cap_full = f"{cap.intent_name} {cap.description}"
                sim = compute_semantic_similarity(query_full, cap_full, cap.semantic_vector)
                if sim > max_sim:
                    max_sim = sim

            lat_norm = min(1.0, peer.capabilities[0].avg_latency_ms / 1000.0) if peer.capabilities else 0.5
            cost_norm = min(1.0, (peer.capabilities[0].cost_per_token * 100000)) if peer.capabilities else 0.5

            score = (
                (w_sim * max_sim)
                + (w_trust * peer.trust_score)
                - (w_lat * lat_norm)
                - (w_cost * cost_norm)
            )

            if score > best_score:
                best_score = score
                best_peer = peer

        if best_peer:
            return best_peer, round(best_score, 4)
        return None


# ============================================================================
# 4. Contract Net Protocol (CNP) Market Auction Engine
# ============================================================================

@dataclasses.dataclass
class RFPAnnouncement:
    rfp_id: str
    initiator_did: str
    task_intent: str
    task_description: str
    max_budget_tokens: int
    deadline_seconds: float


@dataclasses.dataclass
class CNPBid:
    bid_id: str
    rfp_id: str
    bidder_did: str
    bidder_role: str
    estimated_cost_tokens: int
    estimated_duration_ms: float
    confidence_score: float  # 0.0 to 1.0


class ContractNetEngine:
    """Coordinates decentralized Request For Proposal (RFP) bidding cycles."""

    @staticmethod
    def evaluate_bids(
        rfp: RFPAnnouncement,
        bids: List[CNPBid],
        alpha: float = 0.6,
        beta: float = 0.25,
        gamma: float = 0.15,
    ) -> Optional[CNPBid]:
        """
        Selects winning bid based on Surplus Utility:
        Surplus = alpha * Confidence - beta * (Cost / MaxBudget) - gamma * (Time / Deadline)
        """
        valid_bids = [b for b in bids if b.estimated_cost_tokens <= rfp.max_budget_tokens]
        if not valid_bids:
            return None

        best_bid = None
        best_surplus = -100.0

        for bid in valid_bids:
            cost_ratio = bid.estimated_cost_tokens / float(rfp.max_budget_tokens or 1)
            time_ratio = (bid.estimated_duration_ms / 1000.0) / float(rfp.deadline_seconds or 1.0)
            surplus = (alpha * bid.confidence_score) - (beta * cost_ratio) - (gamma * time_ratio)

            if surplus > best_surplus:
                best_surplus = surplus
                best_bid = bid

        return best_bid


# ============================================================================
# 5. Cognitive Sidecar Proxy & Circuit Breakers
# ============================================================================

class CircuitBreakerState(enum.Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CognitiveSidecarProxy:
    """
    Sidecar container intercepting inbound & outbound A2A traffic:
      - Validates and decrements Hop Limits (TTL).
      - Detects and neutralizes cyclic delegation graph loops.
      - Enforces Token Velocity ceilings and Circuit Breaker trips.
    """

    def __init__(self, agent_did: str, trace_collector: DistributedTraceCollector):
        self.agent_did = agent_did
        self.trace_collector = trace_collector
        self.state = CircuitBreakerState.CLOSED
        self.consecutive_errors = 0
        self.error_threshold = 3
        self.last_trip_time: Optional[float] = None
        self.cooldown_seconds = 5.0
        self.cumulative_tokens_consumed = 0

    def pre_dispatch_check(self, envelope: A2AMessageEnvelope) -> Tuple[bool, str]:
        """Validates outbound or inbound envelope prior to invocation."""
        # Check 1: Circuit breaker status
        now = time.time()
        if self.state == CircuitBreakerState.OPEN:
            if self.last_trip_time and (now - self.last_trip_time > self.cooldown_seconds):
                self.state = CircuitBreakerState.HALF_OPEN
            else:
                return False, f"CIRCUIT_BREAKER_OPEN: Agent {self.agent_did} in cooldown"

        # Check 2: Monotonic Hop Limit (TTL)
        if envelope.hop_limit <= 0:
            return False, f"HOP_LIMIT_EXCEEDED: Envelope hop limit reached 0 (trace {envelope.trace_id})"

        # Check 3: Cycle Detection (Recipient already in delegation chain)
        if envelope.recipient_did in envelope.delegation_chain:
            return False, (
                f"DELEGATION_CYCLE_DETECTED: Loop attempted to {envelope.recipient_did} "
                f"in chain {envelope.delegation_chain}"
            )

        # Check 4: Token Budget Exhaustion
        if envelope.token_budget_remaining <= 0:
            return False, f"TOKEN_BUDGET_EXHAUSTED: Budget remaining is {envelope.token_budget_remaining}"

        return True, "OK"

    def record_outcome(self, success: bool, tokens_used: int):
        self.cumulative_tokens_consumed += tokens_used
        if success:
            if self.state == CircuitBreakerState.HALF_OPEN:
                self.state = CircuitBreakerState.CLOSED
            self.consecutive_errors = 0
        else:
            self.consecutive_errors += 1
            if self.consecutive_errors >= self.error_threshold:
                self.state = CircuitBreakerState.OPEN
                self.last_trip_time = time.time()


# ============================================================================
# 6. Autonomous Peer Agent Node
# ============================================================================

class AgentNode:
    """Autonomous sovereign peer node in the Agent Mesh."""

    def __init__(
        self,
        did: str,
        role: str,
        registry: CapabilityRegistry,
        trace_collector: DistributedTraceCollector,
        handler: Callable[[AgentNode, A2AMessageEnvelope], Dict[str, Any]],
    ):
        self.did = did
        self.role = role
        self.registry = registry
        self.trace_collector = trace_collector
        self.handler = handler
        self.proxy = CognitiveSidecarProxy(did, trace_collector)
        self.inbox: List[A2AMessageEnvelope] = []
        self.active_contracts: Dict[str, CNPBid] = {}

    def receive_message(self, envelope: A2AMessageEnvelope) -> Dict[str, Any]:
        """Inbound entrypoint routed through the Cognitive Sidecar Proxy."""
        # 1. Sidecar interceptor check
        is_allowed, reason = self.proxy.pre_dispatch_check(envelope)
        if not is_allowed:
            # Emit error span
            span = self.trace_collector.start_span(
                trace_id=envelope.trace_id,
                parent_span_id=envelope.parent_span_id,
                agent_did=self.did,
                agent_role=self.role,
                action_name=f"reject_{envelope.intent}",
            )
            self.trace_collector.finish_span(span, status=f"REJECTED: {reason}")
            return {"status": "ERROR", "reason": reason}

        # 2. Start OpenTelemetry span
        span = self.trace_collector.start_span(
            trace_id=envelope.trace_id,
            parent_span_id=envelope.parent_span_id,
            agent_did=self.did,
            agent_role=self.role,
            action_name=f"handle_{envelope.intent}",
            attributes={"hop_limit": envelope.hop_limit, "chain": envelope.delegation_chain},
        )
        self.current_span_id = span.span_id

        try:
            # 3. Execute business logic handler
            result = self.handler(self, envelope)
            tokens_used = result.get("tokens_consumed", 350)
            self.proxy.record_outcome(success=True, tokens_used=tokens_used)

            self.trace_collector.finish_span(
                span,
                prompt_tokens=int(tokens_used * 0.6),
                completion_tokens=int(tokens_used * 0.4),
                status="OK",
                attributes={"result_summary": str(result.get("data", {}))[:60]},
            )
            return {"status": "OK", "data": result.get("data", {}), "tokens_consumed": tokens_used}

        except Exception as ex:
            self.proxy.record_outcome(success=False, tokens_used=50)
            self.trace_collector.finish_span(span, status=f"EXCEPTION: {str(ex)}")
            return {"status": "ERROR", "reason": str(ex)}

    def delegate(
        self,
        parent_envelope: A2AMessageEnvelope,
        target_did: str,
        intent: str,
        payload: Dict[str, Any],
        allocated_budget: int = 4000,
    ) -> Dict[str, Any]:
        """Dispatches an attenuated child task directly to a peer node."""
        child_envelope = parent_envelope.create_attenuated_child(
            new_recipient_did=target_did,
            new_intent=intent,
            new_payload=payload,
            allocated_token_budget=allocated_budget,
        )
        # Ensure child span points directly to this agent's active execution span
        if getattr(self, "current_span_id", None):
            child_envelope.parent_span_id = self.current_span_id

        target_peer_profile = self.registry.peers.get(target_did)
        if not target_peer_profile or not target_peer_profile.is_active:
            return {"status": "ERROR", "reason": f"Target peer {target_did} is offline or unregistered"}

        # In-process or network dispatch simulation
        target_agent = target_peer_profile.endpoint  # We store agent reference in endpoint for demo
        if isinstance(target_agent, AgentNode):
            return target_agent.receive_message(child_envelope)
        return {"status": "ERROR", "reason": "Invalid agent endpoint"}


# ============================================================================
# 7. End-to-End Enterprise Scenario: Incident Response Mesh
# ============================================================================

def make_security_mesh() -> Tuple[Dict[str, AgentNode], CapabilityRegistry, DistributedTraceCollector]:
    """Assembles a 4-agent autonomous incident response mesh."""
    collector = DistributedTraceCollector()
    registry = CapabilityRegistry()

    # --- Handlers ---
    def sentinel_handler(agent: AgentNode, envelope: A2AMessageEnvelope) -> Dict[str, Any]:
        # Sentinel detects threat, seeks investigator peer via semantic routing
        anomaly = envelope.payload.get("alert", "SSH Brute Force")
        best = registry.route_intent("investigate-breach", "correlate logs and reverse shell forensic trace", exclude_dids={agent.did})
        if not best:
            return {"data": {"action": "no_peer_found"}, "tokens_consumed": 150}

        investigator_peer, score = best
        investigation = agent.delegate(
            parent_envelope=envelope,
            target_did=investigator_peer.did,
            intent="investigate-breach",
            payload={"incident_type": anomaly, "source_ip": "198.51.100.42"},
            allocated_budget=8000,
        )
        return {
            "data": {"alert_triaged": anomaly, "investigation_result": investigation},
            "tokens_consumed": 400,
        }

    def investigator_handler(agent: AgentNode, envelope: A2AMessageEnvelope) -> Dict[str, Any]:
        # Investigator discovers compromised script, delegates patch creation & compliance check
        ip = envelope.payload.get("source_ip", "unknown")
        # 1. Delegate patch generation
        patch_res = agent.delegate(
            parent_envelope=envelope,
            target_did="did:mesh:patch-synthesizer-01",
            intent="generate-firewall-patch",
            payload={"block_ip": ip, "target_file": "/etc/nftables.conf"},
            allocated_budget=3000,
        )
        # 2. Delegate compliance audit
        compliance_res = agent.delegate(
            parent_envelope=envelope,
            target_did="did:mesh:compliance-auditor-01",
            intent="audit-blast-radius",
            payload={"proposed_action": "BLOCK_IP", "target": ip},
            allocated_budget=2000,
        )
        return {
            "data": {
                "root_cause": f"Malicious probe from {ip} verified",
                "patch": patch_res.get("data"),
                "compliance": compliance_res.get("data"),
            },
            "tokens_consumed": 650,
        }

    def patch_synthesizer_handler(agent: AgentNode, envelope: A2AMessageEnvelope) -> Dict[str, Any]:
        ip = envelope.payload.get("block_ip", "0.0.0.0")
        diff_code = f"+ rule inet filter input ip saddr {ip} drop comment 'Auto-quarantine by Agent Mesh'"
        return {
            "data": {"diff": diff_code, "sandboxed_tests_passed": True},
            "tokens_consumed": 380,
        }

    def compliance_auditor_handler(agent: AgentNode, envelope: A2AMessageEnvelope) -> Dict[str, Any]:
        action = envelope.payload.get("proposed_action", "")
        # Compliance approval
        return {
            "data": {
                "policy_checked": "SOC2-CC6.1",
                "approved": True,
                "attestation_token": "sig-attest-9938bf2",
            },
            "tokens_consumed": 220,
        }

    # --- Instantiate Agents ---
    sentinel = AgentNode("did:mesh:sentinel-01", "Sentinel", registry, collector, sentinel_handler)
    investigator = AgentNode("did:mesh:investigator-01", "ForensicInvestigator", registry, collector, investigator_handler)
    synthesizer = AgentNode("did:mesh:patch-synthesizer-01", "PatchSynthesizer", registry, collector, patch_synthesizer_handler)
    auditor = AgentNode("did:mesh:compliance-auditor-01", "ComplianceAuditor", registry, collector, compliance_auditor_handler)

    agents = {
        "sentinel": sentinel,
        "investigator": investigator,
        "synthesizer": synthesizer,
        "auditor": auditor,
    }

    # --- Register Capabilities in Mesh ---
    for node, desc, intents in [
        (sentinel, "Real-time SIEM triage and anomaly detection", ["triage-alert", "monitor-telemetry"]),
        (investigator, "Forensic log correlation and process tree investigation", ["investigate-breach", "root-cause-analysis"]),
        (synthesizer, "AST diff synthesis, sandboxed patch execution", ["generate-firewall-patch", "code-remediation"]),
        (auditor, "Regulatory governance, blast radius assessment", ["audit-blast-radius", "compliance-check"]),
    ]:
        caps = [
            CapabilityDescriptor(
                intent_name=intent,
                description=desc,
                semantic_vector=_text_to_feature_vector(f"{intent} {desc}"),
            )
            for intent in intents
        ]
        profile = PeerProfile(
            did=node.did,
            role=node.role,
            endpoint=node,  # Direct object ref for simulation
            capabilities=caps,
            trust_score=0.98,
        )
        registry.register_peer(profile)

    return agents, registry, collector


# ============================================================================
# 8. Main Execution Simulation
# ============================================================================

def run_mesh_simulation():
    print("=" * 80)
    print("CASE STUDY 30: MULTI-AGENT MESH (P2P DECENTRALIZED COGNITIVE FABRIC)")
    print("=" * 80)

    agents, registry, collector = make_security_mesh()
    trace_id = uuid.uuid4().hex

    # Root user trigger envelope
    root_envelope = A2AMessageEnvelope(
        message_id="root-trigger-01",
        trace_id=trace_id,
        span_id=uuid.uuid4().hex[:16],
        parent_span_id=None,
        sender_did="did:mesh:siem-webhook",
        recipient_did=agents["sentinel"].did,
        intent="triage-alert",
        payload={"alert": "Unauthorized Root SSH Credential Stuffing & Reverse Shell"},
        hop_limit=5,
        token_budget_remaining=16000,
    )

    print(f"\n[1] Ingesting root incident alert into Mesh...")
    print(f"    Trace ID: {trace_id}")
    print(f"    Target Node: {agents['sentinel'].role} ({agents['sentinel'].did})")

    # Dispatch to sentinel
    response = agents["sentinel"].receive_message(root_envelope)

    print("\n[2] Execution Result Returned Across P2P Mesh:")
    print(json.dumps(response, indent=2))

    print("\n[3] OpenTelemetry GenAI Distributed Trace Summary:")
    summary = collector.export_trace_summary(trace_id)
    print(f"    Total Distributed Spans:   {summary['total_spans']}")
    print(f"    Total Cognitive Duration:  {summary['total_duration_ms']} ms")
    print(f"    Total Tokens Consumed:     {summary['total_tokens_consumed']} tokens")

    print("\n[4] Causal Span Execution Sequence:")
    for s in summary["spans"]:
        print(f"    • [{s['status']}] {s['agent']} -> {s['action']} ({s['duration_ms']} ms, {s['tokens']} tokens)")

    print("\n[5] Generated Mermaid Causal DAG:")
    print(collector.render_mermaid_dag(trace_id))

    print("\n[6] Testing Resilient Mesh Guardrails:")
    # A. Cycle test
    print("    A. Testing Cycle Detection Guardrail (Sentinel -> Investigator -> Sentinel)...")
    cyclic_envelope = A2AMessageEnvelope(
        message_id="cycle-test",
        trace_id=trace_id,
        span_id="cyclic-span",
        parent_span_id=None,
        sender_did=agents["investigator"].did,
        recipient_did=agents["sentinel"].did,
        intent="query-again",
        payload={},
        delegation_chain=[agents["sentinel"].did, agents["investigator"].did],  # Sentinel already present!
    )
    cycle_res = agents["sentinel"].receive_message(cyclic_envelope)
    print(f"       Result: {cycle_res['reason']}")

    # B. Hop limit test
    print("    B. Testing Monotonic Hop Limit (TTL=0)...")
    expired_envelope = A2AMessageEnvelope(
        message_id="hop-test",
        trace_id=trace_id,
        span_id="expired-span",
        parent_span_id=None,
        sender_did="did:mesh:external",
        recipient_did=agents["synthesizer"].did,
        intent="generate-diff",
        payload={},
        hop_limit=0,  # Expired
    )
    hop_res = agents["synthesizer"].receive_message(expired_envelope)
    print(f"       Result: {hop_res['reason']}")

    print("\n[SUCCESS] Multi-Agent Mesh executed with 100% decentralized peer autonomy!\n")


if __name__ == "__main__":
    run_mesh_simulation()
