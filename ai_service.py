"""
ai_service.py
Centralised AI service layer for the Personalised Student Interview System.

Every AI call in the application goes through this module - nothing else
talks to an LLM API directly. This module automatically detects whether an
AI_API_KEY is configured:

    - If a key IS present   -> AI MODE (calls the Anthropic API)
    - If a key is NOT present -> DEMO MODE (deterministic, realistic mock AI)

Both modes expose exactly the same methods, so the rest of the application
never needs to know which mode is active.
"""

import os
import re
import json
import random
from dotenv import load_dotenv

import prompts

load_dotenv()

CATEGORIES = ["Technical Knowledge", "Problem Solving", "Projects", "Communication", "Behavioural"]
DIFFICULTIES = ["Easy", "Medium", "Hard"]


# ============================================================================
# DEMO QUESTION BANK
# Each question carries a set of "signal keywords" used by the deterministic
# demo grader to simulate realistic, keyword-aware scoring.
# ============================================================================
QUESTION_BANK = {
    "Technical Knowledge": {
        "Easy": [
            {"key": "tk_e1", "text": "What is the difference between a list and a tuple in Python?",
             "keywords": ["mutable", "immutable", "list", "tuple", "change", "order"]},
            {"key": "tk_e2", "text": "What is a primary key in a relational database?",
             "keywords": ["unique", "primary", "key", "identify", "row", "table"]},
            {"key": "tk_e3", "text": "What is the difference between supervised and unsupervised learning?",
             "keywords": ["label", "labeled", "unlabeled", "supervised", "unsupervised", "target"]},
        ],
        "Medium": [
            {"key": "tk_m1", "text": "Explain overfitting and how you would recognise it in a model.",
             "keywords": ["overfit", "training", "validation", "generalize", "variance", "test"]},
            {"key": "tk_m2", "text": "How does indexing improve database query performance, and what is the trade-off?",
             "keywords": ["index", "query", "performance", "write", "storage", "lookup"]},
            {"key": "tk_m3", "text": "Explain the bias-variance trade-off in machine learning.",
             "keywords": ["bias", "variance", "trade-off", "underfit", "overfit", "error"]},
        ],
        "Hard": [
            {"key": "tk_h1", "text": "How would you detect and reduce overfitting in a machine learning model in production?",
             "keywords": ["regularization", "cross-validation", "dropout", "early stopping", "data augmentation", "monitor"]},
            {"key": "tk_h2", "text": "Design a database schema to handle high-write time-series data at scale. What are the key considerations?",
             "keywords": ["partition", "index", "scale", "write", "schema", "time-series"]},
            {"key": "tk_h3", "text": "Compare gradient boosting and random forests, including when you would prefer one over the other.",
             "keywords": ["boosting", "random forest", "bias", "variance", "ensemble", "sequential"]},
        ],
    },
    "Problem Solving": {
        "Easy": [
            {"key": "ps_e1", "text": "How would you find duplicate values in a large list?",
             "keywords": ["set", "hash", "duplicate", "dictionary", "loop", "count"]},
            {"key": "ps_e2", "text": "How would you approach debugging code that produces incorrect output?",
             "keywords": ["debug", "reproduce", "log", "isolate", "test", "breakpoint"]},
        ],
        "Medium": [
            {"key": "ps_m1", "text": "How would you design an algorithm to detect fraud patterns in transaction data?",
             "keywords": ["pattern", "anomaly", "threshold", "feature", "model", "outlier"]},
            {"key": "ps_m2", "text": "A system's response time suddenly doubled in production. How would you investigate?",
             "keywords": ["monitor", "log", "profile", "bottleneck", "metric", "isolate"]},
        ],
        "Hard": [
            {"key": "ps_h1", "text": "Design a scalable system to detect fraud patterns in real-time transaction streams, and explain your trade-offs.",
             "keywords": ["stream", "real-time", "scalable", "trade-off", "latency", "throughput"]},
            {"key": "ps_h2", "text": "How would you optimise a machine learning pipeline that is too slow for production use?",
             "keywords": ["optimise", "pipeline", "latency", "batch", "cache", "parallel"]},
        ],
    },
    "Projects": {
        "Easy": [
            {"key": "pr_e1", "text": "Describe one project from your resume and what your role in it was.",
             "keywords": ["project", "role", "built", "developed", "team", "responsible"]},
            {"key": "pr_e2", "text": "What tools or technologies did you use in your most recent project?",
             "keywords": ["tool", "technology", "used", "stack", "library", "framework"]},
        ],
        "Medium": [
            {"key": "pr_m1", "text": "What was the most challenging technical problem you solved in a project, and how did you solve it?",
             "keywords": ["challenge", "problem", "solved", "approach", "solution", "result"]},
            {"key": "pr_m2", "text": "How did you measure the success or impact of one of your projects?",
             "keywords": ["metric", "impact", "measure", "result", "improvement", "success"]},
        ],
        "Hard": [
            {"key": "pr_h1", "text": "Walk through the end-to-end architecture of your most complex project, including trade-offs you made.",
             "keywords": ["architecture", "trade-off", "design", "scale", "decision", "component"]},
            {"key": "pr_h2", "text": "If you rebuilt your best project today, what would you do differently and why?",
             "keywords": ["improve", "differently", "lesson", "redesign", "mistake", "learn"]},
        ],
    },
    "Communication": {
        "Easy": [
            {"key": "co_e1", "text": "Explain a technical concept from your field to someone with no technical background.",
             "keywords": ["simple", "analogy", "explain", "example", "non-technical", "clear"]},
            {"key": "co_e2", "text": "How do you typically document your work so others can understand it?",
             "keywords": ["document", "comment", "readme", "clear", "share", "explain"]},
        ],
        "Medium": [
            {"key": "co_m1", "text": "Describe a time you had to explain a technical trade-off to a non-technical stakeholder.",
             "keywords": ["stakeholder", "trade-off", "explain", "simplify", "decision", "communicate"]},
            {"key": "co_m2", "text": "How would you present the results of a complex analysis to a manager who has limited time?",
             "keywords": ["summary", "concise", "key point", "manager", "present", "highlight"]},
        ],
        "Hard": [
            {"key": "co_h1", "text": "Describe how you would communicate a project failure or missed deadline to leadership.",
             "keywords": ["failure", "leadership", "transparent", "plan", "accountability", "communicate"]},
        ],
    },
    "Behavioural": {
        "Easy": [
            {"key": "be_e1", "text": "Tell me about a time you worked effectively as part of a team.",
             "keywords": ["team", "collaborate", "together", "role", "communication", "support"]},
            {"key": "be_e2", "text": "How do you prioritise tasks when you have multiple deadlines?",
             "keywords": ["priorit", "deadline", "plan", "organise", "urgent", "important"]},
        ],
        "Medium": [
            {"key": "be_m1", "text": "Tell me about a time you disagreed with a teammate. How did you resolve it?",
             "keywords": ["disagree", "resolve", "conflict", "listen", "compromise", "discuss"]},
            {"key": "be_m2", "text": "Describe a situation where you had to learn a new skill quickly for a project.",
             "keywords": ["learn", "quick", "adapt", "new skill", "research", "apply"]},
        ],
        "Hard": [
            {"key": "be_h1", "text": "Tell me about a time you made a mistake that impacted your team. How did you handle it?",
             "keywords": ["mistake", "impact", "accountability", "fix", "learn", "communicate"]},
        ],
    },
}

# Default category weightage used by the Interview Planner Agent
DEFAULT_WEIGHTS = {
    "Technical Knowledge": 30,
    "Problem Solving": 25,
    "Projects": 20,
    "Communication": 10,
    "Behavioural": 15,
}


def _extract_json(text: str) -> dict:
    """Best-effort extraction of a JSON object from an LLM response."""
    text = text.strip()
    text = re.sub(r"^```(json)?", "", text.strip())
    text = re.sub(r"```$", "", text.strip())
    try:
        return json.loads(text)
    except Exception:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                pass
    return {}


class AIService:
    def __init__(self, mode_override: str = "auto"):
        self.api_key = os.getenv("AI_API_KEY", "").strip()
        self.model = os.getenv("AI_MODEL", "claude-3-5-haiku-20241022").strip()
        self._client = None

        if mode_override == "demo":
            self.mode = "demo"
        elif mode_override == "api":
            self.mode = "api" if self.api_key else "demo"
        else:
            self.mode = "api" if self.api_key else "demo"

        if self.mode == "api":
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=self.api_key)
            except Exception:
                # SDK missing or client failed to init - fall back safely
                self.mode = "demo"
                self._client = None

    # ------------------------------------------------------------ utility
    def is_demo(self) -> bool:
        return self.mode == "demo"

    def mode_label(self) -> str:
        return "Demo Mode" if self.is_demo() else "AI Mode (Live API)"

    def _call_llm(self, prompt: str, max_tokens: int = 500) -> str:
        """Low level call to the Anthropic API with a safe fallback."""
        if not self._client:
            return ""
        try:
            resp = self._client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            parts = []
            for block in resp.content:
                if getattr(block, "type", "") == "text":
                    parts.append(block.text)
            return "\n".join(parts).strip()
        except Exception:
            return ""

    # ------------------------------------------------------------ 1. profile analysis
    def analyse_profile(self, name, target_role, experience_level, skills, career_goal, resume_text):
        if self.mode == "api":
            prompt = prompts.PROFILE_ANALYSIS_PROMPT.format(
                name=name, target_role=target_role, experience_level=experience_level,
                skills=", ".join(skills), career_goal=career_goal,
                resume_text=(resume_text or "")[:4000],
            )
            raw = self._call_llm(prompt, max_tokens=700)
            data = _extract_json(raw)
            if data:
                return data
        return self._demo_analyse_profile(target_role, experience_level, skills, career_goal, resume_text)

    def _demo_analyse_profile(self, target_role, experience_level, skills, career_goal, resume_text):
        skills = [s.strip() for s in skills if s.strip()]
        text = (resume_text or "").lower()

        project_kw = ["project", "built", "developed", "designed", "implemented"]
        projects_found = []
        for line in (resume_text or "").splitlines():
            low = line.lower()
            if any(k in low for k in project_kw) and len(line.strip()) > 8:
                projects_found.append(line.strip()[:120])
        if not projects_found:
            projects_found = [f"{target_role}-focused academic project using {', '.join(skills[:3]) or 'core skills'}"]

        education = "Not specified"
        for line in (resume_text or "").splitlines():
            if any(k in line.lower() for k in ["b.tech", "bachelor", "university", "college", "degree", "b.e", "m.tech"]):
                education = line.strip()[:120]
                break

        strengths = skills[:3] if skills else ["Willingness to learn"]
        weak_pool = ["System design", "Advanced statistics", "Communication under pressure",
                     "Large-scale architecture", "Behavioural storytelling"]
        weaknesses = [w for w in weak_pool if not any(w.lower().split()[0] in s.lower() for s in skills)][:2]

        strategy = (
            f"Based on this profile, the interview will focus more on "
            f"{', '.join(skills[:3]) if skills else 'core fundamentals'}, problem solving and "
            f"project knowledge relevant to the {target_role} role."
        )

        return {
            "skills": skills,
            "projects": projects_found[:4],
            "education": education,
            "experience_level": experience_level or "Intermediate",
            "strengths": strengths,
            "weaknesses": weaknesses,
            "strategy_summary": strategy,
        }

    # ------------------------------------------------------------ 2. question generation
    def generate_question(self, category, difficulty, target_role, experience_level,
                           asked_keys, interview_type="initial", performance_signal="neutral"):
        if self.mode == "api":
            prompt = prompts.QUESTION_GENERATION_PROMPT.format(
                interview_type=interview_type, target_role=target_role,
                experience_level=experience_level, category=category, difficulty=difficulty,
                asked_questions="; ".join(asked_keys) if asked_keys else "None",
                performance_signal=performance_signal,
            )
            text = self._call_llm(prompt, max_tokens=200)
            if text:
                return {"key": f"api_{random.randint(10000,99999)}", "text": text.strip()}
        return self._demo_pick_question(category, difficulty, asked_keys)

    def _demo_pick_question(self, category, difficulty, asked_keys):
        bank = QUESTION_BANK.get(category, {}).get(difficulty, [])
        candidates = [q for q in bank if q["key"] not in asked_keys]
        if not candidates:
            # widen search to any difficulty in this category not yet asked
            all_in_cat = [q for d in QUESTION_BANK.get(category, {}).values() for q in d]
            candidates = [q for q in all_in_cat if q["key"] not in asked_keys]
        if not candidates:
            # last resort: allow a repeat rather than crashing
            candidates = QUESTION_BANK.get(category, {}).get(difficulty, []) or [
                {"key": "generic", "text": f"Tell me more about your experience relevant to {category}.",
                 "keywords": []}
            ]
        return random.choice(candidates)

    # ------------------------------------------------------------ 3. reassessment question
    def generate_reassessment_question(self, category, difficulty, target_role, original_question, asked_keys):
        if self.mode == "api":
            prompt = prompts.REASSESSMENT_QUESTION_PROMPT.format(
                category=category, difficulty=difficulty,
                original_question=original_question, target_role=target_role,
            )
            text = self._call_llm(prompt, max_tokens=200)
            if text:
                return {"key": f"api_re_{random.randint(10000,99999)}", "text": text.strip()}
        # Demo: prefer a harder/alternate phrasing not asked before
        upgraded_difficulty = {"Easy": "Medium", "Medium": "Hard", "Hard": "Hard"}.get(difficulty, difficulty)
        return self._demo_pick_question(category, upgraded_difficulty, asked_keys)

    # ------------------------------------------------------------ 4. answer evaluation
    def evaluate_answer(self, question_text, answer_text, category, difficulty, keywords=None):
        if self.mode == "api":
            prompt = prompts.ANSWER_EVALUATION_PROMPT.format(
                category=category, difficulty=difficulty, question=question_text, answer=answer_text,
            )
            raw = self._call_llm(prompt, max_tokens=300)
            data = _extract_json(raw)
            if data and "correctness" in data:
                scores = {k: float(data.get(k, 5)) for k in
                          ["correctness", "relevance", "completeness", "technical_depth", "clarity", "reasoning"]}
                overall = round(sum(scores.values()) / len(scores), 1)
                return {"scores": scores, "overall": overall, "feedback": data.get("feedback", "")}
        return self._demo_evaluate_answer(answer_text, keywords or [])

    def _demo_evaluate_answer(self, answer_text, keywords):
        answer_text = (answer_text or "").strip()
        low = answer_text.lower()
        word_count = len(answer_text.split())

        if word_count == 0:
            scores = {k: 0.0 for k in
                      ["correctness", "relevance", "completeness", "technical_depth", "clarity", "reasoning"]}
            return {"scores": scores, "overall": 0.0,
                    "feedback": "No answer was provided. Try to attempt every question, even partially."}

        matched = sum(1 for kw in keywords if kw.lower() in low)
        kw_ratio = matched / len(keywords) if keywords else 0.3

        # length component: rewards substantive answers, caps out around ~90 words
        length_score = min(word_count / 90.0, 1.0)

        base = 0.6 * kw_ratio + 0.4 * length_score
        base = max(0.05, min(base, 1.0))

        noise = random.uniform(-0.05, 0.05)
        base = max(0.0, min(1.0, base + noise))

        def score_for(mult=1.0, jitter=0.6):
            val = base * 10 * mult + random.uniform(-jitter, jitter)
            return round(max(0.0, min(10.0, val)), 1)

        scores = {
            "correctness": score_for(1.0),
            "relevance": score_for(1.05),
            "completeness": score_for(0.95),
            "technical_depth": score_for(0.9),
            "clarity": score_for(1.0),
            "reasoning": score_for(0.95),
        }
        overall = round(sum(scores.values()) / len(scores), 1)

        if overall >= 8:
            feedback = "Strong answer with good coverage of the key concept. Keep reinforcing this depth."
        elif overall >= 6.5:
            feedback = "Solid understanding shown. Adding a concrete example would strengthen the answer further."
        elif overall >= 5:
            feedback = "Reasonable attempt, but the explanation lacks some depth and precision. Review the core concept."
        else:
            feedback = "This answer needs more detail and accuracy. Revisit the fundamentals of this topic before the next attempt."

        return {"scores": scores, "overall": overall, "feedback": feedback}

    # ------------------------------------------------------------ 5. practice generation
    def generate_practice_question(self, category, target_role, weak_topics, practice_number):
        if self.mode == "api":
            prompt = prompts.PRACTICE_GENERATION_PROMPT.format(
                category=category, target_role=target_role,
                weak_topics=", ".join(weak_topics) if weak_topics else "general fundamentals",
                practice_number=practice_number,
            )
            text = self._call_llm(prompt, max_tokens=150)
            if text:
                return {"key": f"api_pr_{random.randint(10000,99999)}", "text": text.strip()}
        # demo: cycle through the category's easy->medium->hard bank
        order = ["Easy", "Medium", "Hard"]
        diff = order[min(practice_number - 1, len(order) - 1)]
        all_qs = QUESTION_BANK.get(category, {}).get(diff, []) or \
            [q for d in QUESTION_BANK.get(category, {}).values() for q in d]
        q = random.choice(all_qs) if all_qs else \
            {"key": "generic_practice", "text": f"Practice question on {category}.", "keywords": []}
        return q

    # ------------------------------------------------------------ 6. feedback summary
    def generate_feedback_summary(self, target_role, category_scores, overall_score, result):
        if self.mode == "api":
            prompt = prompts.FEEDBACK_SUMMARY_PROMPT.format(
                target_role=target_role, category_scores=json.dumps(category_scores),
                overall_score=overall_score, result=result,
            )
            text = self._call_llm(prompt, max_tokens=150)
            if text:
                return text.strip()
        if not category_scores:
            return "Performance summary is not yet available."
        best = max(category_scores, key=category_scores.get)
        worst = min(category_scores, key=category_scores.get)
        if result == "PASS":
            return (f"Great work — you scored {overall_score}% overall for the {target_role} interview, "
                    f"driven by strong performance in {best}. Keep sharpening {worst} to stay well-rounded.")
        return (f"You scored {overall_score}% for the {target_role} interview, just short of the required mark. "
                f"{best} was your strongest area, while {worst} needs focused practice before your next attempt.")


def get_ai_service(mode_override="auto"):
    return AIService(mode_override=mode_override)
