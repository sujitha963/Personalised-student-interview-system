# Personalised Student Interview System

Agentic AI-based adaptive interview, practice, and reassessment platform.

Built with **Python + Streamlit + SQLite**. Runs immediately in **Demo Mode**
(no API key required), or with a real LLM if you provide an API key.

---

## 1. Setup

```bash
python -m venv venv
```

Activate the virtual environment:

**Windows:**
```bash
venv\Scripts\activate
```

**macOS / Linux:**
```bash
source venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the app:

```bash
streamlit run app.py
```

Streamlit will automatically open the application in your browser
(usually at `http://localhost:8501`). The SQLite database
(`interview_system.db`) is created automatically the first time you run
the app - no manual setup required.

---

## 2. Demo Mode vs AI Mode

The app **automatically detects** whether an API key is configured:

- **No key present → Demo Mode.** The app uses a realistic, deterministic
  mock AI: it grades answers using keyword coverage and answer depth, picks
  questions from a hand-built adaptive question bank, and generates
  believable feedback/practice content. You can fully demo the product
  without paying for an API.
- **Key present → AI Mode.** The app calls the Anthropic API (via
  `ai_service.py`) for profile analysis, question generation, answer
  evaluation, practice generation, and feedback summaries.

To enable AI Mode:

```bash
cp .env.example .env
```

Then edit `.env` and set:

```text
AI_API_KEY=your_key_here
```

You can also force a mode from the sidebar **Settings → AI Mode**
(`auto` / `demo` / `api`), regardless of whether a key is present.

The current mode is always shown as a badge in the sidebar.

---

## 3. Using the App - Full Walkthrough

### Step 1 - Load a demo student
Go to **Student Profile** and click **⚡ Load Demo Student**. This fills in
a sample student ("Alex Kumar", targeting a Data Scientist role) so you
don't have to type anything. You can also fill the form manually and
optionally upload a resume (`.pdf` or `.txt` - try `sample_resume.txt`
included in this project), or paste resume text directly.

### Step 2 - Analyse the profile
Click **Create Profile & Analyse**. The Profile Agent extracts skills,
projects, strengths and weaknesses, and the Interview Planner Agent builds
a personalised category weightage plan (different students get different
plans).

### Step 3 - Run the interview
Click **Begin Interview**. Answer each question honestly:

- **To trigger a FAIL** (and see the practice/reassessment loop): keep
  your answers short (a few words) or off-topic. The demo grader scores
  low on brief/irrelevant answers, so the difficulty will also drop and
  your overall score will likely land below the passing percentage
  (default 70%).
- **To trigger a PASS immediately:** write detailed, on-topic answers
  (3-5+ sentences, using relevant terminology for the question).

After each answer you'll see an evaluation (Correctness, Relevance,
Completeness, Depth, Clarity, Reasoning + feedback) before moving to the
next adaptive question.

### Step 4 - View results
On the **Results** page you'll see your overall score, PASS/NOT PASSED
status, and a category breakdown chart.

- If you **passed**, you'll see a congratulations screen with your
  strengths and a "Take Another Interview" option.
- If you **did not pass**, you'll see exactly which categories pulled your
  score down (Skill Gap Agent) and a personalised practice plan weighted
  toward your weakest areas.

### Step 5 - Practice
Click **Start Practice** and answer each targeted practice question. Write
noticeably better answers than before (more detail, more relevant
keywords) - this is what drives the visible improvement in your score.

### Step 6 - Reassess
After practice, click **Continue to Reassessment**, review the improvement
summary, then click **Start Reassessment**. You'll get a *new* set of
questions on the same skills (not verbatim repeats) - answer them well and
you should now clear the passing bar.

### Step 7 - Dashboard & History
- **Progress Dashboard**: current score vs. passing score, attempt count,
  a line chart of your score across attempts, and before/after skill
  improvement per category.
- **Interview History**: a table of every attempt with a detailed,
  expandable transcript of every question, answer, and evaluation.

The improvement loop (Interview → Evaluate → Score → Pass? → Practice →
Reassess) is capped at a configurable **Maximum Reassessments** (default 3)
so it can never run forever.

---

## 4. Settings (sidebar)

| Setting | Default | Effect |
|---|---|---|
| Passing Percentage | 70% | Score required to pass |
| Interview Questions | 10 | Questions per interview attempt |
| Practice Questions | 5 | Questions generated after a failed attempt |
| Maximum Reassessments | 3 | Hard cap on retry attempts |
| AI Mode | auto | `auto` detects a key, or force `demo` / `api` |

Click **💾 Save Settings** to persist changes to the database.

---

## 5. Project Structure

```text
personalised-student-interview/
│
├── app.py            Streamlit UI - all 9 pages + session-state workflow
├── agents.py          Agentic logic: planner, interviewer, adaptive
│                        questioning, scoring, pass/fail, skill gap,
│                        practice, reassessment, improvement loop
├── ai_service.py      Centralised AI layer (Demo Mode + live API mode)
├── database.py        SQLite schema + all data access functions
├── prompts.py          Prompt templates used in AI Mode
├── requirements.txt
├── .env.example
├── sample_resume.txt   Example resume you can upload during the demo
└── README.md
```

---

## 6. Notes

- No Docker, no Node.js, no external services required for Demo Mode.
- The database file `interview_system.db` is created next to `app.py` on
  first run. Delete it any time to reset all data.
- All AI calls go through the single `ai_service.py` module - nothing else
  in the app talks to an LLM directly.
