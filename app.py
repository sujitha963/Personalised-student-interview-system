"""
app.py
Personalised Student Interview System - main Streamlit application.

Run with:
    streamlit run app.py
"""

import io
import random
import datetime

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

import database as db
from ai_service import get_ai_service, CATEGORIES, DEFAULT_WEIGHTS
from agents import (
    ProfileAgent, InterviewPlannerAgent, InterviewerAgent, AnswerEvaluationAgent,
    ScoringAgent, PassFailAgent, SkillGapAgent, PracticeAgent, ReassessmentAgent,
    ImprovementLoopController,
)

try:
    import PyPDF2
    PDF_SUPPORT = True
except Exception:
    PDF_SUPPORT = False


# ============================================================================
# PAGE CONFIG + THEME
# ============================================================================
st.set_page_config(
    page_title="Personalised Student Interview System",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

CUSTOM_CSS = """
<style>
:root {
    --lavender: #7c6ff2;
    --lavender-light: #ede9fe;
    --lavender-soft: #f5f3ff;
    --text-dark: #2d2a3e;
}
.stApp { background-color: 757575;}
h1, h2, h3 { color: var(--text-dark) !important; font-family: 'Segoe UI', sans-serif; }
.hero-title { font-size: 2.6rem; font-weight: 800; color: var(--text-dark); margin-bottom: 0.2rem; }
.hero-subtitle { font-size: 1.15rem; color: #635f7a; margin-bottom: 1.5rem; }
.card {
    background: #ffffff;
    border: 1px solid #ece9fb;
    border-radius: 16px;
    padding: 1.4rem 1.6rem;
    box-shadow: 0 2px 10px rgba(124, 111, 242, 0.06);
    margin-bottom: 1rem;
}
.badge {
    display: inline-block;
    padding: 0.25rem 0.75rem;
    border-radius: 999px;
    font-size: 0.85rem;
    font-weight: 600;
}
.badge-pass { background: #e6f7ec; color: #1a8a4a; }
.badge-fail { background: #fdeaea; color: #c0392b; }
.badge-demo { background: var(--lavender-light); color: var(--lavender); }
.badge-api { background: #e6f7ec; color: #1a8a4a; }
.score-big { font-size: 4rem; font-weight: 800; color: var(--lavender); text-align: center; }
.stButton>button {
    background-color: var(--lavender);
    color: white;
    border-radius: 10px;
    border: none;
    padding: 0.5rem 1.3rem;
    font-weight: 600;
}
.stButton>button:hover { background-color: #6a5de0; color: white; }
.feature-line { font-size: 1.02rem; color: #3d3a52; margin-bottom: 0.35rem; }
[data-testid="stSidebar"] { 
    background-color: #f7f5ff; 
}

/* ===== BLACK TEXT THEME ===== */

body,
.stApp {
    color: #000000 !important;
}

/* Normal Streamlit text */
.stMarkdown,
.stMarkdown p,
.stMarkdown span,
.stMarkdown li,
.stMarkdown label {
    color: #000000 !important;
}

/* Headings */
h1, h2, h3, h4, h5, h6 {
    color: #000000 !important;
}

/* Captions */
[data-testid="stCaptionContainer"] {
    color: #333333 !important;
}

/* Form labels */
label,
[data-testid="stWidgetLabel"],
[data-testid="stWidgetLabel"] p {
    color: #000000 !important;
}

/* Text input */
input,
textarea {
    color: #000000 !important;
    background-color: #ffffff !important;
}

/* Input placeholder */
input::placeholder,
textarea::placeholder {
    color: #777777 !important;
}

/* Select boxes */
[data-baseweb="select"] {
    color: #000000 !important;
}

[data-baseweb="select"] * {
    color: #000000 !important;
}

/* Sidebar text */
[data-testid="stSidebar"] * {
    color: #000000 !important;
}

/* Keep buttons white */
.stButton > button {
    color: #ffffff !important;
}

.stButton > button:hover {
    color: #ffffff !important;
}
</style>
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

db.init_db()


# ============================================================================
# SESSION STATE
# ============================================================================
def init_session():
    defaults = {
        "page": "home",
        "student_id": None,
        "settings": db.get_all_settings(),
        "profile_analysis": None,
        "plan": None,
        "interview": None,
        "last_eval": None,
        "skill_gaps": [],
        "practice_items": [],
        "practice_index": 0,
        "practice_cycle": 0,
        "result_status": None,
        "final_message": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


init_session()


def settings():
    return st.session_state.settings


def refresh_settings():
    st.session_state.settings = db.get_all_settings()


def get_ai():
    return get_ai_service(settings().get("ai_mode_override", "auto"))


def goto(page):
    st.session_state.page = page
    st.rerun()


def current_student():
    if st.session_state.student_id is None:
        return None
    return db.get_student(st.session_state.student_id)


# ============================================================================
# SIDEBAR
# ============================================================================
def sidebar():
    with st.sidebar:
        st.markdown("### 🎯 Interview System")
        ai = get_ai()
        badge_class = "badge-demo" if ai.is_demo() else "badge-api"
        st.markdown(
            f'<span class="badge {badge_class}">AI Mode: {ai.mode_label()}</span>',
            unsafe_allow_html=True,
        )
        st.markdown("---")

        student = current_student()
        if student:
            st.markdown(f"**Student:** {student['name']}")
            st.markdown(f"**Target Role:** {student['target_role']}")
            st.markdown("---")

        st.markdown("#### Navigate")
        nav_items = [
            ("home", "🏠 Home"),
            ("profile", "📝 Student Profile"),
            ("analysis", "🔎 Profile Analysis"),
            ("interview", "🎤 Interview"),
            ("results", "📊 Results"),
            ("practice", "💪 Practice"),
            ("reassess_ready", "🔁 Reassessment"),
            ("dashboard", "📈 Progress Dashboard"),
            ("history", "🕘 Interview History"),
        ]
        for key, label in nav_items:
            if st.button(label, key=f"nav_{key}", use_container_width=True):
                goto(key)

        st.markdown("---")
        st.markdown("#### ⚙️ Settings")
        s = settings()
        passing = st.slider("Passing Percentage", 40, 95, int(float(s.get("passing_percentage", 70))))
        n_questions = st.slider("Interview Questions", 5, 15, int(s.get("num_interview_questions", 10)))
        n_practice = st.slider("Practice Questions", 2, 10, int(s.get("num_practice_questions", 5)))
        max_reassess = st.slider("Maximum Reassessments", 1, 5, int(s.get("max_reassessments", 3)))
        ai_mode = st.selectbox("AI Mode", ["auto", "demo", "api"],
                                index=["auto", "demo", "api"].index(s.get("ai_mode_override", "auto")))

        if st.button("💾 Save Settings", use_container_width=True):
            db.set_setting("passing_percentage", passing)
            db.set_setting("num_interview_questions", n_questions)
            db.set_setting("num_practice_questions", n_practice)
            db.set_setting("max_reassessments", max_reassess)
            db.set_setting("ai_mode_override", ai_mode)
            refresh_settings()
            st.success("Settings saved.")
            st.rerun()


# ============================================================================
# PAGE 1 - HOME
# ============================================================================
def page_home():
    st.markdown('<div class="hero-title">Personalised Student Interview System</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="hero-subtitle">AI-powered adaptive interview preparation that understands your '
        'skills, identifies your weaknesses, and helps you improve.</div>',
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns([2, 1])
    with col1:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        features = [
            "✓ Personalised Interviews", "✓ Adaptive Questions", "✓ AI Evaluation",
            "✓ Skill Gap Detection", "✓ Targeted Practice", "✓ Reassessment", "✓ Progress Tracking",
        ]
        for f in features:
            st.markdown(f'<div class="feature-line">{f}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        c1, c2 = st.columns(2)
        with c1:
            if st.button("🚀 Start Interview", use_container_width=True):
                goto("profile")
        with c2:
            if st.button("📊 View Dashboard", use_container_width=True):
                if st.session_state.student_id:
                    goto("dashboard")
                else:
                    st.warning("Create a student profile first.")
    with col2:
        ai = get_ai()
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("#### System Status")
        st.markdown(f"**AI Mode:** {ai.mode_label()}")
        st.markdown(f"**Passing Score:** {settings().get('passing_percentage')}%")
        st.markdown(f"**Interview Questions:** {settings().get('num_interview_questions')}")
        st.markdown(f"**Max Reassessments:** {settings().get('max_reassessments')}")
        st.markdown('</div>', unsafe_allow_html=True)


# ============================================================================
# PAGE 2 - STUDENT PROFILE
# ============================================================================
DEMO_STUDENT = {
    "name": "Alex Kumar",
    "email": "alex.kumar@example.edu",
    "department": "Computer Science",
    "year": "3",
    "target_role": "Data Scientist",
    "experience_level": "Intermediate",
    "skills": "Python, SQL, Machine Learning, Pandas, AWS",
    "career_goal": "To become a data scientist working on real-world ML products.",
}


def extract_resume_text(uploaded_file):
    if uploaded_file is None:
        return "", None
    name = uploaded_file.name.lower()
    try:
        if name.endswith(".pdf"):
            if not PDF_SUPPORT:
                return "", "PDF support is not installed. Please paste your resume text instead."
            reader = PyPDF2.PdfReader(uploaded_file)
            text = "\n".join([(page.extract_text() or "") for page in reader.pages])
            if not text.strip():
                return "", "We couldn't extract any text from this PDF (it may be scanned/image-based)."
            return text, None
        else:
            return uploaded_file.read().decode("utf-8", errors="ignore"), None
    except Exception:
        return "", "We couldn't read that resume file. Please try a different file or paste your resume text below."


def page_profile():
    st.markdown("## 📝 Student Profile")
    st.caption("Tell us about yourself so we can personalise your interview.")

    if st.button("⚡ Load Demo Student"):
        for k, v in DEMO_STUDENT.items():
            st.session_state[f"pf_{k}"] = v
        st.rerun()

    st.markdown('<div class="card">', unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        name = st.text_input("Name", key="pf_name")
        email = st.text_input("Email", key="pf_email")
        department = st.text_input("Department", key="pf_department")
        year = st.text_input("Year", key="pf_year")
    with col2:
        target_role = st.text_input("Target Job Role", key="pf_target_role")
        experience_level = st.selectbox(
            "Experience Level", ["Beginner", "Intermediate", "Advanced"],
            index=["Beginner", "Intermediate", "Advanced"].index(
                st.session_state.get("pf_experience_level", "Beginner")
            ) if st.session_state.get("pf_experience_level") in ["Beginner", "Intermediate", "Advanced"] else 0,
            key="pf_experience_level",
        )
        skills = st.text_input("Skills (comma separated)", key="pf_skills")
        career_goal = st.text_area("Career Goal", key="pf_career_goal", height=80)

    st.markdown("##### Upload Resume (optional)")
    upload = st.file_uploader("Upload Resume", type=["pdf", "txt"], label_visibility="collapsed")
    pasted_resume = st.text_area(
        "Or paste your resume text here", key="pf_resume_paste", height=120,
        placeholder="Paste resume content if you don't have a file handy...",
    )
    st.markdown('</div>', unsafe_allow_html=True)

    if st.button("✅ Create Profile & Analyse", type="primary"):
        if not name or not target_role:
            st.error("Please provide at least your name and target job role.")
            return

        resume_text = ""
        if upload is not None:
            resume_text, err = extract_resume_text(upload)
            if err:
                st.warning(err)
        if not resume_text and pasted_resume.strip():
            resume_text = pasted_resume.strip()

        skills_list = [s.strip() for s in skills.split(",") if s.strip()]

        student_id = db.create_student({
            "name": name, "email": email, "department": department, "year": year,
            "target_role": target_role, "experience_level": experience_level,
            "skills": skills_list, "career_goal": career_goal, "resume_text": resume_text,
        })
        st.session_state.student_id = student_id

        ai = get_ai()
        profile_agent = ProfileAgent(ai)
        analysis = profile_agent.build_profile(
            name, target_role, experience_level, skills_list, career_goal, resume_text
        )
        db.update_student_profile(student_id, analysis)
        st.session_state.profile_analysis = analysis

        planner = InterviewPlannerAgent(ai)
        plan = planner.create_plan(analysis, int(settings().get("num_interview_questions", 10)))
        st.session_state.plan = plan

        goto("analysis")


# ============================================================================
# PAGE 3 - PROFILE ANALYSIS
# ============================================================================
def page_analysis():
    student = current_student()
    if not student:
        st.warning("Please create a student profile first.")
        if st.button("Go to Profile"):
            goto("profile")
        return

    analysis = st.session_state.profile_analysis or student.get("profile", {})
    plan = st.session_state.plan

    st.markdown("## 🔎 Student Profile Analysis")

    col1, col2 = st.columns([1, 1])
    with col1:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown(f"**Target Role:** {student['target_role']}")
        st.markdown(f"**Experience:** {analysis.get('experience_level', student['experience_level'])}")
        st.markdown("**Skills:**")
        for s in analysis.get("skills", student["skills"]):
            st.markdown(f"- {s}")
        if analysis.get("projects"):
            st.markdown("**Detected Projects:**")
            for p in analysis["projects"]:
                st.markdown(f"- {p}")
        st.markdown('</div>', unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("#### AI Interview Strategy")
        st.info(analysis.get("strategy_summary", "The interview will be tailored to your profile."))
        if analysis.get("strengths"):
            st.markdown("**Strengths:** " + ", ".join(analysis["strengths"]))
        if analysis.get("weaknesses"):
            st.markdown("**Potential Growth Areas:** " + ", ".join(analysis["weaknesses"]))
        st.markdown('</div>', unsafe_allow_html=True)

    if plan:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("#### Interview Weightage Plan")
        fig = go.Figure(go.Bar(
            x=list(plan["weights"].values()), y=list(plan["weights"].keys()),
            orientation="h", marker_color="#7c6ff2",
        ))
        fig.update_layout(height=280, margin=dict(l=10, r=10, t=10, b=10),
                           xaxis_title="Weight (%)", plot_bgcolor="white")
        st.plotly_chart(fig, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    if st.button("🎤 Begin Interview", type="primary"):
        start_new_interview(interview_type="initial")


# ============================================================================
# INTERVIEW ENGINE (shared by initial interview + reassessment)
# ============================================================================
def start_new_interview(interview_type="initial"):
    student = current_student()
    ai = get_ai()
    num_q = int(settings().get("num_interview_questions", 10))

    prior_interviews = db.get_student_interviews(student["id"])
    attempt_number = len(prior_interviews) + 1

    if interview_type == "initial":
        analysis = st.session_state.profile_analysis or student.get("profile", {})
        planner = InterviewPlannerAgent(ai)
        plan = st.session_state.plan or planner.create_plan(analysis, num_q)
    else:
        # reassessment: build plan focused on weak areas
        last_interview = prior_interviews[-1]
        prev_questions = db.get_interview_questions(last_interview["id"])
        reassess_agent = ReassessmentAgent(ai)
        plan = reassess_agent.build_plan(
            prev_questions, st.session_state.skill_gaps, num_q, DEFAULT_WEIGHTS
        )

    interview_id = db.create_interview(student["id"], attempt_number, interview_type, plan)

    st.session_state.interview = {
        "id": interview_id,
        "attempt_number": attempt_number,
        "interview_type": interview_type,
        "plan": plan,
        "remaining_sequence": list(plan["sequence"]),
        "asked_keys": [],
        "current_difficulty": plan.get("start_difficulty", "Easy"),
        "last_score": None,
        "question_number": 0,
        "total_questions": len(plan["sequence"]),
        "category_scores_accum": {c: [] for c in CATEGORIES},
        "current_question": None,
        "awaiting_feedback": False,
    }
    st.session_state.last_eval = None
    goto("interview")


def page_interview():
    student = current_student()
    iv = st.session_state.interview
    if not student or not iv:
        st.warning("No interview in progress. Start one from your profile analysis.")
        if st.button("Go to Analysis"):
            goto("analysis")
        return

    ai = get_ai()
    interviewer = InterviewerAgent(ai)
    evaluator = AnswerEvaluationAgent(ai)
    reassess_agent = ReassessmentAgent(ai)

    # ---- generate the next question if needed ----
    if iv["current_question"] is None and iv["remaining_sequence"]:
        category = iv["remaining_sequence"][0]
        difficulty = InterviewerAgent._decide_difficulty(iv["current_difficulty"], iv["last_score"])

        if iv["interview_type"] == "reassessment":
            q = reassess_agent.next_question(
                category, difficulty, student["target_role"], iv["asked_keys"],
                iv["plan"].get("previously_asked_by_cat", {}),
            )
        else:
            _, _, q = interviewer.next_question(
                {"sequence": iv["remaining_sequence"], "asked_keys": iv["asked_keys"],
                 "current_difficulty": iv["current_difficulty"], "last_score": iv["last_score"]},
                student["target_role"], student["experience_level"], iv["interview_type"],
            )

        keywords = []
        from ai_service import QUESTION_BANK
        bank_entry = QUESTION_BANK.get(category, {}).get(difficulty, [])
        for item in bank_entry:
            if item["key"] == q.get("key"):
                keywords = item.get("keywords", [])
                break

        qid = db.add_question(iv["id"], iv["question_number"] + 1, category, difficulty, q["text"], q["key"])
        iv["current_question"] = {
            "db_id": qid, "category": category, "difficulty": difficulty,
            "text": q["text"], "key": q["key"], "keywords": keywords,
        }
        iv["current_difficulty"] = difficulty
        iv["remaining_sequence"] = iv["remaining_sequence"][1:]
        iv["question_number"] += 1

    # ---- if interview is finished, wrap it up ----
    if iv["current_question"] is None and not iv["remaining_sequence"]:
        finish_interview()
        return

    cq = iv["current_question"]
    st.markdown(f"## 🎤 Question {iv['question_number']} / {iv['total_questions']}")
    prog = iv["question_number"] / max(iv["total_questions"], 1)
    st.progress(min(prog, 1.0))

    st.markdown('<div class="card">', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    c1.markdown(f"**Category:** {cq['category']}")
    c2.markdown(f"**Difficulty:** {cq['difficulty']}")
    st.markdown("##### AI Interviewer")
    st.info(cq["text"])
    st.markdown('</div>', unsafe_allow_html=True)

    if not iv["awaiting_feedback"]:
        answer = st.text_area("Your Answer", key=f"answer_{cq['db_id']}", height=160,
                               placeholder="Type your answer here...")
        if st.button("Submit Answer", type="primary"):
            db.add_answer(cq["db_id"], answer)
            result = evaluator.evaluate(cq["text"], answer, cq["category"], cq["difficulty"], cq["keywords"])
            db.add_evaluation(cq["db_id"], result["scores"], result["overall"], result["feedback"])

            iv["category_scores_accum"][cq["category"]].append(result["overall"])
            iv["last_score"] = result["overall"]
            iv["awaiting_feedback"] = True
            st.session_state.last_eval = result
            st.rerun()
    else:
        result = st.session_state.last_eval
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("##### Answer Evaluation")
        cols = st.columns(6)
        labels = ["correctness", "relevance", "completeness", "technical_depth", "clarity", "reasoning"]
        nice = ["Correctness", "Relevance", "Completeness", "Depth", "Clarity", "Reasoning"]
        for col, lbl, name in zip(cols, labels, nice):
            col.metric(name, f"{result['scores'][lbl]}/10")
        st.markdown(f"**Feedback:** {result['feedback']}")
        st.markdown('</div>', unsafe_allow_html=True)

        label = "Finish Interview" if not iv["remaining_sequence"] else "Next Question"
        if st.button(label, type="primary"):
            iv["current_question"] = None
            iv["awaiting_feedback"] = False
            st.session_state.last_eval = None
            st.rerun()


def finish_interview():
    student = current_student()
    iv = st.session_state.interview
    weights = iv["plan"].get("weights", DEFAULT_WEIGHTS)

    category_scores = {}
    for cat, scores in iv["category_scores_accum"].items():
        if scores:
            category_scores[cat] = ScoringAgent.category_average(scores)
    if not category_scores:
        category_scores = {c: 0.0 for c in CATEGORIES}

    overall = ScoringAgent.weighted_overall(category_scores, weights)
    passing_pct = float(settings().get("passing_percentage", 70))
    passed = PassFailAgent.evaluate(overall, passing_pct)

    db.complete_interview(iv["id"], overall, category_scores, passed)
    db.add_history(student["id"], iv["id"], iv["attempt_number"], overall,
                    "Pass" if passed else "Fail")

    gaps = SkillGapAgent.identify_gaps(category_scores, passing_pct)
    for g in gaps:
        db.add_skill_gap(iv["id"], g["category"], g["score"], g["priority"])
    st.session_state.skill_gaps = gaps

    st.session_state.result_status = "PASS" if passed else "FAIL"
    st.session_state.interview["final_overall"] = overall
    st.session_state.interview["final_category_scores"] = category_scores
    st.session_state.interview["final_passed"] = passed
    goto("results")


# ============================================================================
# PAGE 5 - RESULTS
# ============================================================================
def page_results():
    student = current_student()
    iv = st.session_state.interview
    if not student or not iv or "final_overall" not in iv:
        st.warning("No completed interview to show yet.")
        if st.button("Go to Home"):
            goto("home")
        return

    overall = iv["final_overall"]
    category_scores = iv["final_category_scores"]
    passed = iv["final_passed"]
    passing_pct = float(settings().get("passing_percentage", 70))
    ai = get_ai()

    st.markdown('<div class="score-big">' + f"{overall}%" + '</div>', unsafe_allow_html=True)
    badge = '<span class="badge badge-pass">PASS</span>' if passed else '<span class="badge badge-fail">NOT PASSED</span>'
    st.markdown(f'<div style="text-align:center; margin-bottom:1rem;">{badge}</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div style="text-align:center; color:#635f7a;">Required: {passing_pct}% &nbsp;|&nbsp; Your Score: {overall}%</div>',
        unsafe_allow_html=True,
    )

    st.markdown('<div class="card">', unsafe_allow_html=True)
    fig = go.Figure(go.Bar(
        x=list(category_scores.values()), y=list(category_scores.keys()),
        orientation="h", marker_color=["#1a8a4a" if v >= passing_pct else "#c0392b" for v in category_scores.values()],
    ))
    fig.add_vline(x=passing_pct, line_dash="dash", line_color="#7c6ff2")
    fig.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10), xaxis_title="Score (%)", plot_bgcolor="white")
    st.plotly_chart(fig, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    summary = ai.generate_feedback_summary(student["target_role"], category_scores, overall,
                                            "PASS" if passed else "FAIL")

    if passed:
        st.markdown("# 🎉 Interview Passed")
        st.success("Congratulations! You have achieved the required interview score.")
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown(f"**Career Readiness:** {overall}%")
        st.write(summary)
        best_cats = sorted(category_scores, key=category_scores.get, reverse=True)[:2]
        st.markdown("**Strengths:** " + ", ".join(best_cats))
        st.markdown('</div>', unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            if st.button("View Detailed Report"):
                goto("history")
        with c2:
            if st.button("Take Another Interview"):
                start_new_interview("initial")
    else:
        gap = round(passing_pct - overall, 1)
        st.markdown("# Practice Recommended")
        st.warning(f"Your Score: {overall}%  |  Required: {passing_pct}%  |  "
                    f"You are {gap} percentage points below the required score.")
        st.write(summary)

        gaps = st.session_state.skill_gaps
        if gaps:
            st.markdown("### Why you didn't pass")
            for g in gaps:
                st.markdown(f"- **{g['category']}** — {g['score']}%")

        controller = ImprovementLoopController(int(settings().get("max_reassessments", 3)))
        decision = controller.decide(passed, iv["attempt_number"])

        if decision == "MAX_ATTEMPTS_REACHED":
            st.error(
                f"You have reached the maximum of {settings().get('max_reassessments')} reassessment "
                f"attempts. Please review your weak areas and try again later with a fresh profile."
            )
        else:
            st.markdown("# Your Personalised Practice Plan")
            practice_agent = PracticeAgent(ai)
            plan = practice_agent.build_plan(gaps, int(settings().get("num_practice_questions", 5)),
                                              student["target_role"])
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown("**PERSONALISED PRACTICE PLAN**")
            for entry in plan:
                st.markdown(f"- **{entry['category']}** → {entry['count']} practice question(s)")
            st.markdown('</div>', unsafe_allow_html=True)

            if st.button("💪 Start Practice", type="primary"):
                st.session_state.practice_cycle += 1
                items = practice_agent.generate_items(plan, student["target_role"])
                registered = []
                for item in items:
                    db_id = db.add_practice_item(student["id"], st.session_state.practice_cycle,
                                                  item["category"], item["question"])
                    registered.append({**item, "db_id": db_id})
                st.session_state.practice_items = registered
                st.session_state.practice_index = 0
                goto("practice")

    report = build_text_report(student, iv, category_scores, overall, passed, summary)
    st.download_button("⬇️ Download Report (TXT)", data=report, file_name="interview_report.txt")


def build_text_report(student, iv, category_scores, overall, passed, summary):
    lines = [
        "PERSONALISED STUDENT INTERVIEW SYSTEM - REPORT",
        "=" * 50,
        f"Student Name: {student['name']}",
        f"Target Role: {student['target_role']}",
        f"Interview Date: {datetime.date.today().isoformat()}",
        "",
        f"Overall Score: {overall}%",
        f"Result: {'PASS' if passed else 'NOT PASSED'}",
        "",
        "Category Scores:",
    ]
    for cat, score in category_scores.items():
        lines.append(f"  - {cat}: {score}%")
    lines += ["", "Summary:", summary, ""]
    gaps = st.session_state.skill_gaps
    if gaps:
        lines.append("Weaknesses:")
        for g in gaps:
            lines.append(f"  - {g['category']} ({g['score']}%)")
    lines += ["", "Final Recommendation:",
              "Keep practicing your weaker categories and retake the interview to improve your score."
              if not passed else "You're ready - keep your skills sharp with regular practice."]
    return "\n".join(lines)


# ============================================================================
# PAGE 6 - PRACTICE
# ============================================================================
def page_practice():
    student = current_student()
    items = st.session_state.practice_items
    idx = st.session_state.practice_index

    if not student or not items:
        st.warning("No practice session in progress.")
        if st.button("Go to Results"):
            goto("results")
        return

    ai = get_ai()
    practice_agent = PracticeAgent(ai)

    if idx >= len(items):
        st.success("✅ Practice complete! You're ready for reassessment.")
        if st.button("Continue to Reassessment", type="primary"):
            goto("reassess_ready")
        return

    item = items[idx]
    st.markdown("## 💪 Personalised Practice")
    st.markdown(f"**Focus Area:** {item['category']}")
    st.markdown(f"### Question {idx + 1} / {len(items)}")
    st.progress((idx) / len(items))

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.info(item["question"])
    st.markdown('</div>', unsafe_allow_html=True)

    feedback_key = f"practice_feedback_{item['db_id']}"

    if feedback_key not in st.session_state:
        answer = st.text_area("Your Answer", key=f"practice_answer_{item['db_id']}", height=140)
        if st.button("Submit Answer", type="primary"):
            score, feedback = practice_agent.evaluate_practice_answer(
                item["question"], answer, item["category"]
            )
            db.submit_practice_answer(item["db_id"], answer, score, feedback)
            st.session_state[feedback_key] = {"score": score, "feedback": feedback}
            st.rerun()
    else:
        fb = st.session_state[feedback_key]
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.metric("Score", f"{fb['score']}/10")
        st.markdown(f"**Feedback:** {fb['feedback']}")
        st.markdown('</div>', unsafe_allow_html=True)
        if st.button("Next", type="primary"):
            st.session_state.practice_index += 1
            st.rerun()


# ============================================================================
# PAGE 7 - REASSESSMENT READY
# ============================================================================
def page_reassess_ready():
    student = current_student()
    if not student:
        st.warning("Please create a student profile first.")
        return

    prior_interviews = db.get_student_interviews(student["id"])
    if not prior_interviews:
        st.warning("Complete an interview first.")
        if st.button("Go to Profile"):
            goto("profile")
        return

    last_interview = prior_interviews[-1]
    prev_score = last_interview["overall_score"] or 0

    practice_items = db.get_practice_cycle(student["id"], st.session_state.practice_cycle)
    practice_scores = [p["score"] for p in practice_items if p["score"] is not None]
    practice_avg = round(sum(practice_scores) / len(practice_scores) * 10, 1) if practice_scores else 0
    improvement = round(practice_avg - prev_score, 1)

    st.markdown("# Ready for Reassessment?")
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown(f"**Previous Score:** {prev_score}%")
    st.markdown(f"**Practice Improvement:** {'+' if improvement >= 0 else ''}{improvement}%")
    st.markdown("**Focus Areas:**")
    for g in st.session_state.skill_gaps:
        st.markdown(f"- {g['category']}")
    st.markdown('</div>', unsafe_allow_html=True)

    controller = ImprovementLoopController(int(settings().get("max_reassessments", 3)))
    if not controller.can_reassess_again(last_interview["attempt_number"]):
        st.error("Maximum reassessment attempts reached for this profile.")
        return

    if st.button("🔁 Start Reassessment", type="primary"):
        start_new_interview(interview_type="reassessment")


# ============================================================================
# PAGE 8 - PROGRESS DASHBOARD
# ============================================================================
def page_dashboard():
    student = current_student()
    if not student:
        st.warning("Please create a student profile first.")
        if st.button("Go to Profile"):
            goto("profile")
        return

    interviews = [i for i in db.get_student_interviews(student["id"]) if i["status"] == "completed"]
    practice_all = db.get_all_practice(student["id"])
    passing_pct = float(settings().get("passing_percentage", 70))

    st.markdown("## 📈 Progress Dashboard")

    col1, col2, col3, col4, col5 = st.columns(5)
    current_score = interviews[-1]["overall_score"] if interviews else 0
    status = "PASS" if interviews and interviews[-1]["passed"] else "Not Passed"
    completed_practice = len([p for p in practice_all if p["completed"]])

    col1.metric("Current Score", f"{current_score or 0}%")
    col2.metric("Passing Score", f"{passing_pct}%")
    col3.metric("Status", status)
    col4.metric("Practice Completed", completed_practice)
    col5.metric("Interview Attempts", len(interviews))

    if interviews:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("#### Score Progress Across Attempts")
        df = pd.DataFrame({
            "Attempt": [f"Attempt {i['attempt_number']}" for i in interviews],
            "Score": [i["overall_score"] for i in interviews],
        })
        fig = go.Figure(go.Scatter(x=df["Attempt"], y=df["Score"], mode="lines+markers",
                                    line=dict(color="#7c6ff2", width=3), marker=dict(size=10)))
        fig.add_hline(y=passing_pct, line_dash="dash", line_color="#c0392b",
                       annotation_text="Passing Score")
        fig.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10), plot_bgcolor="white",
                           yaxis_title="Score (%)")
        st.plotly_chart(fig, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

        if len(interviews) >= 2:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown("#### Skill Improvement")
            first_scores = interviews[0]["category_scores"]
            last_scores = interviews[-1]["category_scores"]
            for cat in CATEGORIES:
                before = first_scores.get(cat)
                after = last_scores.get(cat)
                if before is not None and after is not None:
                    delta = round(after - before, 1)
                    st.markdown(f"**{cat}** — Before: {before}% | After: {after}% | "
                                f"Improvement: {'+' if delta >= 0 else ''}{delta}%")
            st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.info("Complete your first interview to see progress here.")


# ============================================================================
# PAGE 9 - INTERVIEW HISTORY
# ============================================================================
def page_history():
    student = current_student()
    if not student:
        st.warning("Please create a student profile first.")
        if st.button("Go to Profile"):
            goto("profile")
        return

    history = db.get_history(student["id"])
    st.markdown("## 🕘 Interview History")

    if not history:
        st.info("No interview attempts yet.")
        return

    df = pd.DataFrame([{
        "Attempt": h["attempt_number"],
        "Date": h["created_at"][:10],
        "Score": f"{h['score']}%",
        "Status": h["status"],
    } for h in history])
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.markdown("#### Detailed Report")
    for h in history:
        with st.expander(f"Attempt {h['attempt_number']} — {h['score']}% — {h['status']}"):
            details = db.get_interview_full(h["interview_id"])
            for d in details:
                q = d["question"]
                a = d["answer"]
                e = d["evaluation"]
                st.markdown(f"**Q{q['question_number']} [{q['category']} / {q['difficulty']}]:** {q['question_text']}")
                if a:
                    st.markdown(f"*Answer:* {a['answer_text']}")
                if e:
                    st.markdown(f"*Score:* {e['overall']}/10 — {e['feedback']}")
                st.markdown("---")


# ============================================================================
# ROUTER
# ============================================================================
PAGES = {
    "home": page_home,
    "profile": page_profile,
    "analysis": page_analysis,
    "interview": page_interview,
    "results": page_results,
    "practice": page_practice,
    "reassess_ready": page_reassess_ready,
    "dashboard": page_dashboard,
    "history": page_history,
}

sidebar()
PAGES.get(st.session_state.page, page_home)()
