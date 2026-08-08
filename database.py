"""
database.py
Handles all SQLite database setup and access for the
Personalised Student Interview System.

No manual database creation is required - init_db() is called
automatically on application start and creates the schema if
it does not already exist.
"""

import sqlite3
import json
import datetime
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "interview_system.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create all tables if they do not already exist."""
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT,
        department TEXT,
        year TEXT,
        target_role TEXT,
        experience_level TEXT,
        skills TEXT,
        career_goal TEXT,
        resume_text TEXT,
        profile_json TEXT,
        created_at TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS interviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER,
        attempt_number INTEGER,
        interview_type TEXT,          -- 'initial' or 'reassessment'
        plan_json TEXT,
        status TEXT,                  -- 'in_progress', 'completed'
        overall_score REAL,
        category_scores_json TEXT,
        passed INTEGER,
        created_at TEXT,
        completed_at TEXT,
        FOREIGN KEY(student_id) REFERENCES students(id)
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        interview_id INTEGER,
        question_number INTEGER,
        category TEXT,
        difficulty TEXT,
        question_text TEXT,
        question_key TEXT,
        created_at TEXT,
        FOREIGN KEY(interview_id) REFERENCES interviews(id)
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS answers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        question_id INTEGER,
        answer_text TEXT,
        created_at TEXT,
        FOREIGN KEY(question_id) REFERENCES questions(id)
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS evaluations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        question_id INTEGER,
        correctness REAL,
        relevance REAL,
        completeness REAL,
        technical_depth REAL,
        clarity REAL,
        reasoning REAL,
        overall REAL,
        feedback TEXT,
        created_at TEXT,
        FOREIGN KEY(question_id) REFERENCES questions(id)
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS practice_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER,
        cycle_number INTEGER,
        focus_area TEXT,
        question_text TEXT,
        answer_text TEXT,
        score REAL,
        feedback TEXT,
        completed INTEGER DEFAULT 0,
        created_at TEXT,
        FOREIGN KEY(student_id) REFERENCES students(id)
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS skill_gaps (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        interview_id INTEGER,
        category TEXT,
        score REAL,
        priority INTEGER,
        created_at TEXT,
        FOREIGN KEY(interview_id) REFERENCES interviews(id)
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS interview_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER,
        interview_id INTEGER,
        attempt_number INTEGER,
        score REAL,
        status TEXT,
        created_at TEXT,
        FOREIGN KEY(student_id) REFERENCES students(id),
        FOREIGN KEY(interview_id) REFERENCES interviews(id)
    )
    """)

    conn.commit()

    # seed default settings if not present
    defaults = {
        "passing_percentage": "70",
        "num_interview_questions": "10",
        "num_practice_questions": "5",
        "max_reassessments": "3",
        "ai_mode_override": "auto",  # auto / demo / api
    }
    for k, v in defaults.items():
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))
    conn.commit()
    conn.close()


def now():
    return datetime.datetime.now().isoformat(timespec="seconds")


# ---------------------------------------------------------------- settings
def get_setting(key, default=None):
    conn = get_conn()
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    conn.close()
    if row is None:
        return default
    return row["value"]


def set_setting(key, value):
    conn = get_conn()
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, str(value)),
    )
    conn.commit()
    conn.close()


def get_all_settings():
    conn = get_conn()
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    conn.close()
    return {r["key"]: r["value"] for r in rows}


# ---------------------------------------------------------------- students
def create_student(data: dict) -> int:
    conn = get_conn()
    cur = conn.execute(
        """INSERT INTO students
           (name, email, department, year, target_role, experience_level,
            skills, career_goal, resume_text, profile_json, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (
            data.get("name"),
            data.get("email"),
            data.get("department"),
            data.get("year"),
            data.get("target_role"),
            data.get("experience_level"),
            json.dumps(data.get("skills", [])),
            data.get("career_goal"),
            data.get("resume_text", ""),
            json.dumps(data.get("profile", {})),
            now(),
        ),
    )
    conn.commit()
    sid = cur.lastrowid
    conn.close()
    return sid


def update_student_profile(student_id: int, profile: dict):
    conn = get_conn()
    conn.execute(
        "UPDATE students SET profile_json=? WHERE id=?",
        (json.dumps(profile), student_id),
    )
    conn.commit()
    conn.close()


def get_student(student_id: int):
    conn = get_conn()
    row = conn.execute("SELECT * FROM students WHERE id=?", (student_id,)).fetchone()
    conn.close()
    if row is None:
        return None
    d = dict(row)
    d["skills"] = json.loads(d.get("skills") or "[]")
    d["profile"] = json.loads(d.get("profile_json") or "{}")
    return d


# ---------------------------------------------------------------- interviews
def create_interview(student_id, attempt_number, interview_type, plan):
    conn = get_conn()
    cur = conn.execute(
        """INSERT INTO interviews
           (student_id, attempt_number, interview_type, plan_json, status, created_at)
           VALUES (?,?,?,?,?,?)""",
        (student_id, attempt_number, interview_type, json.dumps(plan), "in_progress", now()),
    )
    conn.commit()
    iid = cur.lastrowid
    conn.close()
    return iid


def complete_interview(interview_id, overall_score, category_scores, passed):
    conn = get_conn()
    conn.execute(
        """UPDATE interviews SET status=?, overall_score=?, category_scores_json=?,
           passed=?, completed_at=? WHERE id=?""",
        ("completed", overall_score, json.dumps(category_scores), int(passed), now(), interview_id),
    )
    conn.commit()
    conn.close()


def get_interview(interview_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM interviews WHERE id=?", (interview_id,)).fetchone()
    conn.close()
    if row is None:
        return None
    d = dict(row)
    d["plan"] = json.loads(d.get("plan_json") or "{}")
    d["category_scores"] = json.loads(d.get("category_scores_json") or "{}")
    return d


def get_student_interviews(student_id):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM interviews WHERE student_id=? ORDER BY attempt_number ASC",
        (student_id,),
    ).fetchall()
    conn.close()
    out = []
    for row in rows:
        d = dict(row)
        d["plan"] = json.loads(d.get("plan_json") or "{}")
        d["category_scores"] = json.loads(d.get("category_scores_json") or "{}")
        out.append(d)
    return out


# ---------------------------------------------------------------- questions/answers/evals
def add_question(interview_id, question_number, category, difficulty, question_text, question_key):
    conn = get_conn()
    cur = conn.execute(
        """INSERT INTO questions
           (interview_id, question_number, category, difficulty, question_text, question_key, created_at)
           VALUES (?,?,?,?,?,?,?)""",
        (interview_id, question_number, category, difficulty, question_text, question_key, now()),
    )
    conn.commit()
    qid = cur.lastrowid
    conn.close()
    return qid


def get_interview_questions(interview_id):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM questions WHERE interview_id=? ORDER BY question_number ASC",
        (interview_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_answer(question_id, answer_text):
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO answers (question_id, answer_text, created_at) VALUES (?,?,?)",
        (question_id, answer_text, now()),
    )
    conn.commit()
    aid = cur.lastrowid
    conn.close()
    return aid


def add_evaluation(question_id, scores: dict, overall, feedback):
    conn = get_conn()
    conn.execute(
        """INSERT INTO evaluations
           (question_id, correctness, relevance, completeness, technical_depth,
            clarity, reasoning, overall, feedback, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (
            question_id,
            scores.get("correctness"),
            scores.get("relevance"),
            scores.get("completeness"),
            scores.get("technical_depth"),
            scores.get("clarity"),
            scores.get("reasoning"),
            overall,
            feedback,
            now(),
        ),
    )
    conn.commit()
    conn.close()


def get_evaluation_for_question(question_id):
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM evaluations WHERE question_id=? ORDER BY id DESC LIMIT 1", (question_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_interview_full(interview_id):
    """Return list of dicts: question + answer + evaluation, joined."""
    questions = get_interview_questions(interview_id)
    conn = get_conn()
    out = []
    for q in questions:
        arow = conn.execute(
            "SELECT * FROM answers WHERE question_id=? ORDER BY id DESC LIMIT 1", (q["id"],)
        ).fetchone()
        erow = conn.execute(
            "SELECT * FROM evaluations WHERE question_id=? ORDER BY id DESC LIMIT 1", (q["id"],)
        ).fetchone()
        out.append({
            "question": q,
            "answer": dict(arow) if arow else None,
            "evaluation": dict(erow) if erow else None,
        })
    conn.close()
    return out


# ---------------------------------------------------------------- skill gaps
def add_skill_gap(interview_id, category, score, priority):
    conn = get_conn()
    conn.execute(
        "INSERT INTO skill_gaps (interview_id, category, score, priority, created_at) VALUES (?,?,?,?,?)",
        (interview_id, category, score, priority, now()),
    )
    conn.commit()
    conn.close()


def get_skill_gaps(interview_id):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM skill_gaps WHERE interview_id=? ORDER BY priority ASC", (interview_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------- practice
def add_practice_item(student_id, cycle_number, focus_area, question_text):
    conn = get_conn()
    cur = conn.execute(
        """INSERT INTO practice_sessions
           (student_id, cycle_number, focus_area, question_text, created_at)
           VALUES (?,?,?,?,?)""",
        (student_id, cycle_number, focus_area, question_text, now()),
    )
    conn.commit()
    pid = cur.lastrowid
    conn.close()
    return pid


def submit_practice_answer(practice_id, answer_text, score, feedback):
    conn = get_conn()
    conn.execute(
        """UPDATE practice_sessions SET answer_text=?, score=?, feedback=?, completed=1
           WHERE id=?""",
        (answer_text, score, feedback, practice_id),
    )
    conn.commit()
    conn.close()


def get_practice_cycle(student_id, cycle_number):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM practice_sessions WHERE student_id=? AND cycle_number=? ORDER BY id ASC",
        (student_id, cycle_number),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_practice(student_id):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM practice_sessions WHERE student_id=? ORDER BY id ASC", (student_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------- history
def add_history(student_id, interview_id, attempt_number, score, status):
    conn = get_conn()
    conn.execute(
        """INSERT INTO interview_history
           (student_id, interview_id, attempt_number, score, status, created_at)
           VALUES (?,?,?,?,?,?)""",
        (student_id, interview_id, attempt_number, score, status, now()),
    )
    conn.commit()
    conn.close()


def get_history(student_id):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM interview_history WHERE student_id=? ORDER BY attempt_number ASC",
        (student_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def reset_student_data(student_id):
    """Wipe everything tied to a student so a fresh demo run can start."""
    conn = get_conn()
    interview_ids = [r["id"] for r in conn.execute(
        "SELECT id FROM interviews WHERE student_id=?", (student_id,)).fetchall()]
    for iid in interview_ids:
        qids = [r["id"] for r in conn.execute(
            "SELECT id FROM questions WHERE interview_id=?", (iid,)).fetchall()]
        for qid in qids:
            conn.execute("DELETE FROM answers WHERE question_id=?", (qid,))
            conn.execute("DELETE FROM evaluations WHERE question_id=?", (qid,))
        conn.execute("DELETE FROM questions WHERE interview_id=?", (iid,))
        conn.execute("DELETE FROM skill_gaps WHERE interview_id=?", (iid,))
    conn.execute("DELETE FROM interviews WHERE student_id=?", (student_id,))
    conn.execute("DELETE FROM practice_sessions WHERE student_id=?", (student_id,))
    conn.execute("DELETE FROM interview_history WHERE student_id=?", (student_id,))
    conn.commit()
    conn.close()
