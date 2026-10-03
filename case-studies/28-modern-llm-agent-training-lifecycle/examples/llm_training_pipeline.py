"""
Executable Reference Implementation for Case Study 28:
Modern LLM & Agent Training Lifecycles — From Pre-Training & Agentic SFT to RLVR (GRPO) and Sandboxed Tool Grounding.

Demonstrates:
- Agentic SFT Loss Masking: Multi-turn ReAct formatting with strict assistant-only loss masking
- Verifiable Rule-Based Reward Engine: Evaluating math, code execution, and tool schema validity
- Group Relative Policy Optimization (GRPO) Advantage Estimation: Normalized group rewards without critic networks
- Emergence of Thinking Token Self-Correction: Simulating reasoning length scaling and exploration dynamics
"""

from __future__ import annotations

import dataclasses
from enum import Enum
import hashlib
import json
import logging
import math
import random
from typing import Any, Callable, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("LLMTrainingPipeline")


class MessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL_OBSERVATION = "tool_observation"


class ChatTurn(BaseModel):
    role: MessageRole
    content: str
    tool_call_name: Optional[str] = None
    tool_call_args: Optional[Dict[str, Any]] = None
    compute_loss: bool = False  # Masking flag: True only for model generation targets


class AgenticSFTTrajectory(BaseModel):
    trajectory_id: str
    turns: List[ChatTurn]
    total_tokens: int = 0
    masked_target_tokens: int = 0

    def compute_masking_ratios(self) -> Dict[str, float]:
        """Calculates what percentage of tokens are actively supervised vs masked."""
        active = sum(len(turn.content.split()) for turn in self.turns if turn.compute_loss)
        total = sum(len(turn.content.split()) for turn in self.turns)
        return {
            "active_supervised_tokens": active,
            "total_tokens": total,
            "supervision_ratio": round(active / max(1, total), 3),
        }


class GRPOHypothesis(BaseModel):
    sample_id: str
    prompt: str
    thinking_tokens: str
    final_solution: str
    total_tokens: int
    raw_reward: float = 0.0
    normalized_advantage: float = 0.0
    passes_verification: bool = False


class VerifiableRewardEvaluator:
    """
    Evaluates rule-based verifiable rewards for math/coding and tool schema calls.
    Provides strict 0/1 outcome rewards plus optional formatting bonuses.
    """

    @staticmethod
    def verify_tool_schema(tool_name: str, args: Dict[str, Any], expected_schema: Dict[str, type]) -> Tuple[bool, str]:
        for param, param_type in expected_schema.items():
            if param not in args:
                return False, f"Missing required parameter '{param}'"
            if not isinstance(args[param], param_type):
                return False, f"Invalid type for '{param}': expected {param_type.__name__}, got {type(args[param]).__name__}"
        return True, "Valid Schema"

    @staticmethod
    def verify_math_computation(solution_text: str, ground_truth_answer: str) -> float:
        """Checks if final boxed or designated answer matches truth."""
        clean_text = solution_text.strip().replace(" ", "")
        clean_target = ground_truth_answer.strip().replace(" ", "")
        if f"Answer:{clean_target}" in clean_text or f"boxed{{{clean_target}}}" in clean_text:
            return 1.0
        return 0.0

    @staticmethod
    def verify_python_code_execution(code_snippet: str, test_assertion: str) -> Tuple[bool, float]:
        """Simulates sandboxed verification of generated Python logic."""
        full_script = f"{code_snippet}\n{test_assertion}"
        local_scope: Dict[str, Any] = {}
        try:
            exec(full_script, {}, local_scope)
            return True, 1.0
        except Exception:
            return False, 0.0


class GRPOTrainingEngine:
    """
    Simulates Group Relative Policy Optimization (GRPO) advantage estimation.
    For each prompt, samples a group of G candidates, computes rule rewards,
    and normalizes advantages relative to the group mean and standard deviation.
    """

    def __init__(self, group_size: int = 4, beta_kl: float = 0.04, epsilon_clip: float = 0.2):
        self.group_size = group_size
        self.beta_kl = beta_kl
        self.epsilon_clip = epsilon_clip

    def evaluate_group_rollouts(
        self,
        prompt: str,
        rollouts: List[GRPOHypothesis],
        ground_truth: str,
    ) -> List[GRPOHypothesis]:
        """Calculates raw rewards and group-relative normalized advantages."""
        if len(rollouts) != self.group_size:
            raise ValueError(f"Rollout count ({len(rollouts)}) must match group_size ({self.group_size})")

        # 1. Compute raw verifiable rewards for each candidate in group
        for cand in rollouts:
            math_reward = VerifiableRewardEvaluator.verify_math_computation(cand.final_solution, ground_truth)
            
            # Format penalty/bonus: check if thinking tags exist
            format_reward = 0.2 if ("<think>" in cand.thinking_tokens and "</think>" in cand.thinking_tokens) else -0.5
            
            cand.passes_verification = (math_reward == 1.0)
            cand.raw_reward = math_reward + format_reward

        # 2. Compute group mean and standard deviation
        raw_rewards = [c.raw_reward for c in rollouts]
        mean_r = sum(raw_rewards) / len(raw_rewards)
        variance = sum((r - mean_r) ** 2 for r in raw_rewards) / len(raw_rewards)
        std_r = math.sqrt(variance) + 1e-8

        # 3. Normalize advantage A_i = (r_i - mean) / std
        for cand in rollouts:
            cand.normalized_advantage = round((cand.raw_reward - mean_r) / std_r, 4)

        return rollouts

    def compute_policy_gradient_metrics(
        self, rollouts: List[GRPOHypothesis]
    ) -> Dict[str, Any]:
        """Calculates batch telemetry metrics for monitoring test-time reasoning scaling."""
        mean_reward = sum(c.raw_reward for c in rollouts) / len(rollouts)
        accuracy = sum(1.0 for c in rollouts if c.passes_verification) / len(rollouts)
        avg_thinking_len = sum(len(c.thinking_tokens.split()) for c in rollouts) / len(rollouts)
        pos_advantages = [c for c in rollouts if c.normalized_advantage > 0]

        return {
            "group_size": len(rollouts),
            "mean_group_reward": round(mean_reward, 3),
            "pass_rate_accuracy": round(accuracy, 3),
            "avg_thinking_token_count": round(avg_thinking_len, 1),
            "positive_advantage_count": len(pos_advantages),
        }


def build_synthetic_agentic_sft_dataset() -> AgenticSFTTrajectory:
    """
    Constructs a high-quality multi-turn Agentic SFT trajectory with strict
    token loss masking on assistant generation targets only.
    """
    turns = [
        ChatTurn(
            role=MessageRole.SYSTEM,
            content="You are an autonomous engineering agent with access to database inspection tools.",
            compute_loss=False,  # Masked: system prompt
        ),
        ChatTurn(
            role=MessageRole.USER,
            content="Analyze query latency on the 'customers' table and recommend an index.",
            compute_loss=False,  # Masked: user prompt
        ),
        ChatTurn(
            role=MessageRole.ASSISTANT,
            content="<think>\nI need to inspect the slow query logs and current index definitions for 'customers'.\n</think>\n"
                    "<tool_call>{\"name\": \"get_table_indexes\", \"arguments\": {\"table\": \"customers\"}}</tool_call>",
            tool_call_name="get_table_indexes",
            tool_call_args={"table": "customers"},
            compute_loss=True,  # Supervised: assistant thinking and tool calling
        ),
        ChatTurn(
            role=MessageRole.TOOL_OBSERVATION,
            content="{\"table\": \"customers\", \"indexes\": [\"PRIMARY (id)\"], \"p99_latency_ms\": 420.5}",
            compute_loss=False,  # Masked: tool output from environment
        ),
        ChatTurn(
            role=MessageRole.ASSISTANT,
            content="<think>\nThe table lacks a secondary index on lookup fields, causing full table scans.\n</think>\n"
                    "Recommendation: Create a B-Tree index on 'customers(email, created_at)'.",
            compute_loss=True,  # Supervised: final solution reasoning
        ),
    ]

    trajectory = AgenticSFTTrajectory(
        trajectory_id="traj_db_opt_001",
        turns=turns,
    )
    return trajectory


def run_training_pipeline_verification():
    """Runs end-to-end verification of SFT Loss Masking and GRPO Reasoning Alignment."""
    logger.info("================================================================================")
    logger.info("STARTING CASE STUDY 28 VERIFICATION: LLM TRAINING LIFECYCLE (SFT & GRPO RLVR)")
    logger.info("================================================================================")

    # -------------------------------------------------------------
    # 1. VERIFY AGENTIC SFT LOSS MASKING
    # -------------------------------------------------------------
    sft_traj = build_synthetic_agentic_sft_dataset()
    ratios = sft_traj.compute_masking_ratios()
    logger.info("Agentic SFT Trajectory Masking Ratios: %s", json.dumps(ratios, indent=2))

    assert ratios["supervision_ratio"] < 1.0, "SFT error: User and tool tokens must be masked out of loss!"
    assert ratios["active_supervised_tokens"] > 0, "SFT error: Assistant turns must be supervised!"

    # -------------------------------------------------------------
    # 2. VERIFY RULE-BASED VERIFIABLE REWARD EVALUATOR
    # -------------------------------------------------------------
    valid_schema, msg = VerifiableRewardEvaluator.verify_tool_schema(
        tool_name="get_table_indexes",
        args={"table": "customers"},
        expected_schema={"table": str},
    )
    assert valid_schema, f"Schema verification failed: {msg}"

    invalid_schema, _ = VerifiableRewardEvaluator.verify_tool_schema(
        tool_name="get_table_indexes",
        args={"table": 12345},  # Invalid type
        expected_schema={"table": str},
    )
    assert not invalid_schema, "Schema validator accepted invalid integer argument!"

    # Python Execution Verification
    py_code = "def solve(n):\n    return sum(i for i in range(n) if i % 2 == 0)"
    py_test = "assert solve(10) == 20"
    success, score = VerifiableRewardEvaluator.verify_python_code_execution(py_code, py_test)
    assert success and score == 1.0, "Code execution reward verification failed!"

    # -------------------------------------------------------------
    # 3. VERIFY GRPO GROUP ROLLOUT & ADVANTAGE NORMALIZATION
    # -------------------------------------------------------------
    grpo_engine = GRPOTrainingEngine(group_size=4, beta_kl=0.04)
    prompt = "Find the sum of all primes less than 10."
    ground_truth = "17"  # 2 + 3 + 5 + 7 = 17

    # Simulate 4 rollouts with varying degrees of reasoning length and correctness
    candidates = [
        GRPOHypothesis(
            sample_id="cand_1",
            prompt=prompt,
            thinking_tokens="<think> Primes less than 10 are 2, 3, 5, 7. Sum = 2+3+5+7 = 17. </think>",
            final_solution="Answer: 17",
            total_tokens=65,
        ),
        GRPOHypothesis(
            sample_id="cand_2",
            prompt=prompt,
            thinking_tokens="<think> Primes are 1, 2, 3, 5, 7. Sum = 1+2+3+5+7 = 18. </think>",  # 1 is not prime
            final_solution="Answer: 18",
            total_tokens=58,
        ),
        GRPOHypothesis(
            sample_id="cand_3",
            prompt=prompt,
            thinking_tokens="<think> Let me list: 2, 3, 5, 7, 9. Wait, 9 is 3*3. Primes: 2, 3, 5, 7. Total 17. </think>",
            final_solution="Answer: 17",
            total_tokens=85,
        ),
        GRPOHypothesis(
            sample_id="cand_4",
            prompt=prompt,
            thinking_tokens="Quick answer without thinking tags.",
            final_solution="Answer: 15",
            total_tokens=22,
        ),
    ]

    evaluated_candidates = grpo_engine.evaluate_group_rollouts(
        prompt=prompt,
        rollouts=candidates,
        ground_truth=ground_truth,
    )

    logger.info("\n--- GRPO GROUP EVALUATION RESULTS ---")
    for cand in evaluated_candidates:
        logger.info(
            "Candidate [%s]: Pass=%s | Raw Reward=%0.2f | Normalized Advantage=%+0.3f | Length=%d tokens",
            cand.sample_id,
            cand.passes_verification,
            cand.raw_reward,
            cand.normalized_advantage,
            cand.total_tokens,
        )

    # Assertions on GRPO mechanics
    cand_1 = next(c for c in evaluated_candidates if c.sample_id == "cand_1")
    cand_2 = next(c for c in evaluated_candidates if c.sample_id == "cand_2")
    cand_3 = next(c for c in evaluated_candidates if c.sample_id == "cand_3")
    cand_4 = next(c for c in evaluated_candidates if c.sample_id == "cand_4")

    assert cand_1.normalized_advantage > 0, "Correct solution must receive positive advantage!"
    assert cand_3.normalized_advantage > 0, "Self-corrected solution must receive positive advantage!"
    assert cand_2.normalized_advantage < 0, "Flawed solution must receive negative advantage!"
    assert cand_4.normalized_advantage < 0, "Unreasoned incorrect answer must receive heavily penalizing advantage!"

    metrics = grpo_engine.compute_policy_gradient_metrics(evaluated_candidates)
    logger.info("\n--- GRPO POLICY GRADIENT BATCH METRICS ---")
    logger.info(json.dumps(metrics, indent=2))

    assert metrics["pass_rate_accuracy"] == 0.5, "Expected 2 of 4 candidates to pass"
    assert metrics["positive_advantage_count"] == 2, "Expected 2 positive advantages"

    logger.info("================================================================================")
    logger.info("ALL TRAINING PIPELINE VERIFICATION ASSERTIONS PASSED SUCCESSFULLY!")
    logger.info("================================================================================")


if __name__ == "__main__":
    run_training_pipeline_verification()
