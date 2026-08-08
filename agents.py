"""
agents.py
Implements the agentic workflow for the Personalised Student Interview System.
Each class below represents one logical "agent" described in the project spec.
All agents share the single centralized ai_service.AIService instance passed
in at construction time - no agent talks to an LLM directly.
"""

import random
from ai_service import CATEGORIES, DIFFICULTIES, DEFAULT_WEIGHTS

DIFFICULTY_ORDER = ["Easy", "Medium", "Hard"]


# ============================================================================
# 1. PROFILE AGENT
# ============================================================================
class ProfileAgent:
    def __init__(self, ai_service):
        self.ai = ai_service

    def build_profile(self, name, target_role, experience_level, skills, career_goal, resume_text):
        analysis = self.ai.analyse_profile(
            name=name, target_role=target_role, experience_level=experience_level,
            skills=skills, career_goal=career_goal, resume_text=resume_text,
        )
        analysis.setdefault("skills", skills)
        analysis.setdefault("experience_level", experience_level)
        return analysis


# ============================================================================
# 2. INTERVIEW PLANNER AGENT
# ============================================================================
class InterviewPlannerAgent:
    def __init__(self, ai_service):
        self.ai = ai_service

    def create_plan(self, profile: dict, num_questions: int, weight_bias: dict = None):
        """
        Build a category/question-count plan. Category order and per-category
        question counts vary with the student's profile (skills + weaknesses),
        so different students get different plans - not a fixed template.
        """
        weights = dict(DEFAULT_WEIGHTS)
        if weight_bias:
            for cat, extra in weight_bias.items():
                weights[cat] = weights.get(cat, 0) + extra
            total = sum(weights.values())
            weights = {k: round(v / total * 100) for k, v in weights.items()}

        # Nudge weighting based on the student's own weaknesses (from profile agent)
        weaknesses = [w.lower() for w in profile.get("weaknesses", [])]
        for cat in weights:
            if any(cat.lower().split()[0] in w for w in weaknesses):
                weights[cat] += 5
        total = sum(weights.values())
        weights = {k: round(v / total * 100) for k, v in weights.items()}

        # allocate question counts proportionally to weights, minimum 1 per category
        counts = self._allocate_counts(weights, num_questions)

        exp = (profile.get("experience_level") or "Intermediate").lower()
        if "beginner" in exp:
            start_difficulty = "Easy"
        elif "advanced" in exp:
            start_difficulty = "Medium"
        else:
            start_difficulty = "Easy"

        # build an ordered question sequence: category cycled, difficulty adaptive later
        sequence = []
        cats_in_order = sorted(counts.keys(), key=lambda c: -weights[c])
        remaining = dict(counts)
        while sum(remaining.values()) > 0:
            for cat in cats_in_order:
                if remaining[cat] > 0:
                    sequence.append(cat)
                    remaining[cat] -= 1

        return {
            "weights": weights,
            "counts": counts,
            "sequence": sequence[:num_questions],
            "start_difficulty": start_difficulty,
            "strategy_summary": profile.get("strategy_summary", ""),
        }

    @staticmethod
    def _allocate_counts(weights: dict, total: int) -> dict:
        raw = {cat: (w / 100.0) * total for cat, w in weights.items()}
        counts = {cat: max(1, int(v)) for cat, v in raw.items()}
        diff = total - sum(counts.values())
        cats_sorted = sorted(raw.keys(), key=lambda c: raw[c] - int(raw[c]), reverse=True)
        i = 0
        while diff > 0 and cats_sorted:
            counts[cats_sorted[i % len(cats_sorted)]] += 1
            diff -= 1
            i += 1
        while diff < 0:
            for cat in cats_sorted:
                if counts[cat] > 1 and diff < 0:
                    counts[cat] -= 1
                    diff += 1
        return counts


# ============================================================================
# 3 & 4. INTERVIEWER AGENT + ADAPTIVE QUESTION AGENT
# ============================================================================
class InterviewerAgent:
    """
    Maintains interview state across the session: asked questions, answers,
    scores, current topic/difficulty, and weak/strong areas. Delegates the
    "what difficulty next" decision to the adaptive logic below.
    """

    def __init__(self, ai_service):
        self.ai = ai_service

    def next_question(self, state: dict, target_role: str, experience_level: str,
                       interview_type: str = "initial"):
        """
        state is expected to contain:
          sequence: list[category] (remaining categories to ask, in order)
          asked_keys: list[str]
          current_difficulty: str
          last_score: float | None  (0-10 overall of the previous answer)
        Returns (category, difficulty, question_dict) and does NOT mutate state.
        """
        if not state["sequence"]:
            return None

        category = state["sequence"][0]
        difficulty = self._decide_difficulty(state["current_difficulty"], state.get("last_score"))
        signal = "neutral"
        if state.get("last_score") is not None:
            signal = "strong" if state["last_score"] >= 7 else ("weak" if state["last_score"] < 5 else "moderate")

        question = self.ai.generate_question(
            category=category, difficulty=difficulty, target_role=target_role,
            experience_level=experience_level, asked_keys=state["asked_keys"],
            interview_type=interview_type, performance_signal=signal,
        )
        return category, difficulty, question

    @staticmethod
    def _decide_difficulty(current_difficulty: str, last_score):
        """Adaptive Question Agent core logic: raise/lower difficulty based on
        the previous answer's score (out of 10)."""
        if last_score is None:
            return current_difficulty
        idx = DIFFICULTY_ORDER.index(current_difficulty) if current_difficulty in DIFFICULTY_ORDER else 0
        if last_score >= 7.5:
            idx = min(idx + 1, len(DIFFICULTY_ORDER) - 1)   # performed well -> harder
        elif last_score < 5:
            idx = max(idx - 1, 0)                            # performed poorly -> easier
        # else: stay at the same difficulty (moderate performance)
        return DIFFICULTY_ORDER[idx]


# ============================================================================
# 5. ANSWER EVALUATION AGENT (thin wrapper - core logic lives in ai_service)
# ============================================================================
class AnswerEvaluationAgent:
    def __init__(self, ai_service):
        self.ai = ai_service

    def evaluate(self, question_text, answer_text, category, difficulty, keywords=None):
        return self.ai.evaluate_answer(question_text, answer_text, category, difficulty, keywords)


# ============================================================================
# 6. SCORING AGENT
# ============================================================================
class ScoringAgent:
    @staticmethod
    def category_average(scores_list):
        """scores_list: list of 0-10 overall evaluation scores for one category."""
        if not scores_list:
            return 0.0
        return round(sum(scores_list) / len(scores_list) * 10, 1)  # convert to 0-100 scale

    @staticmethod
    def weighted_overall(category_scores: dict, weights: dict):
        """category_scores values are 0-100. weights values are percentages summing ~100."""
        total_weight = sum(weights.get(cat, 0) for cat in category_scores) or 1
        weighted_sum = sum(category_scores[cat] * weights.get(cat, 0) for cat in category_scores)
        return round(weighted_sum / total_weight, 1)


# ============================================================================
# 7. PASS/FAIL AGENT
# ============================================================================
class PassFailAgent:
    @staticmethod
    def evaluate(score: float, passing_percentage: float):
        return score >= passing_percentage


# ============================================================================
# 8. SKILL GAP AGENT
# ============================================================================
class SkillGapAgent:
    @staticmethod
    def identify_gaps(category_scores: dict, passing_percentage: float):
        """Returns list of dicts sorted by ascending score (highest priority first)
        for every category scoring below the passing bar."""
        gaps = [
            {"category": cat, "score": score}
            for cat, score in category_scores.items()
            if score < passing_percentage
        ]
        gaps.sort(key=lambda g: g["score"])
        for i, g in enumerate(gaps, start=1):
            g["priority"] = i
        return gaps


# ============================================================================
# 9 & 10. PERSONALISED PRACTICE AGENT + PRACTICE EVALUATION
# ============================================================================
class PracticeAgent:
    def __init__(self, ai_service):
        self.ai = ai_service

    def build_plan(self, skill_gaps: list, num_practice_questions: int, target_role: str):
        """
        Distribute the configured number of practice questions across weak
        categories, weighted towards the lowest-scoring (highest priority) ones.
        """
        if not skill_gaps:
            return []
        n = len(skill_gaps)
        base = num_practice_questions // n
        remainder = num_practice_questions % n
        plan = []
        for i, gap in enumerate(skill_gaps):
            count = base + (1 if i < remainder else 0)
            count = max(count, 1)
            plan.append({"category": gap["category"], "count": count, "score": gap["score"]})
        return plan

    def generate_items(self, plan: list, target_role: str):
        """Generate the actual practice question text for each planned item."""
        items = []
        for entry in plan:
            for n in range(1, entry["count"] + 1):
                q = self.ai.generate_practice_question(
                    category=entry["category"], target_role=target_role,
                    weak_topics=[entry["category"]], practice_number=n,
                )
                items.append({"category": entry["category"], "question": q["text"], "key": q["key"]})
        return items

    def evaluate_practice_answer(self, question_text, answer_text, category, keywords=None):
        result = self.ai.evaluate_answer(question_text, answer_text, category, "Medium", keywords)
        return result["overall"], result["feedback"]


# ============================================================================
# 11. REASSESSMENT AGENT
# ============================================================================
class ReassessmentAgent:
    def __init__(self, ai_service):
        self.ai = ai_service

    def build_plan(self, previous_interview_questions: list, skill_gaps: list,
                    num_questions: int, weights: dict):
        """
        Build a reassessment plan that re-tests the weak categories (plus a
        couple of previously-strong ones to confirm retention), without
        repeating identical questions.
        """
        weak_categories = [g["category"] for g in skill_gaps]
        other_categories = [c for c in CATEGORIES if c not in weak_categories]

        sequence = []
        # weight weak categories more heavily in the reassessment
        weak_slots = max(1, int(num_questions * 0.6))
        i = 0
        while len(sequence) < weak_slots and weak_categories:
            sequence.append(weak_categories[i % len(weak_categories)])
            i += 1
        i = 0
        while len(sequence) < num_questions and other_categories:
            sequence.append(other_categories[i % len(other_categories)])
            i += 1
        random.shuffle(sequence)

        previously_asked_by_cat = {}
        for q in previous_interview_questions:
            previously_asked_by_cat.setdefault(q["category"], []).append(q)

        return {
            "sequence": sequence[:num_questions],
            "weights": weights,
            "start_difficulty": "Medium",
            "previously_asked_by_cat": previously_asked_by_cat,
        }

    def next_question(self, category, difficulty, target_role, asked_keys, previously_asked_by_cat):
        prior_for_cat = previously_asked_by_cat.get(category, [])
        if prior_for_cat:
            original = random.choice(prior_for_cat)
            question = self.ai.generate_reassessment_question(
                category=category, difficulty=difficulty, target_role=target_role,
                original_question=original["question_text"], asked_keys=asked_keys,
            )
        else:
            question = self.ai.generate_question(
                category=category, difficulty=difficulty, target_role=target_role,
                experience_level="Intermediate", asked_keys=asked_keys, interview_type="reassessment",
            )
        return question


# ============================================================================
# 12. IMPROVEMENT LOOP CONTROLLER
# ============================================================================
class ImprovementLoopController:
    """
    High level orchestrator implementing:
    INTERVIEW -> EVALUATE -> SCORE -> PASS? -> (PASS) or (GAPS -> PRACTICE -> REASSESS -> ... up to max attempts)
    The Streamlit app drives the actual UI/interaction; this class only
    encapsulates the decision of "what should happen next" and enforces the
    maximum reassessment attempt cap so the loop can never run forever.
    """

    def __init__(self, max_reassessments: int = 3):
        self.max_reassessments = max_reassessments

    def can_reassess_again(self, attempt_number: int) -> bool:
        # attempt_number counts the initial interview as attempt 1
        return (attempt_number - 1) < self.max_reassessments

    def decide(self, passed: bool, attempt_number: int) -> str:
        if passed:
            return "PASSED"
        if self.can_reassess_again(attempt_number):
            return "PRACTICE_THEN_REASSESS"
        return "MAX_ATTEMPTS_REACHED"
