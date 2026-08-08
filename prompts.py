"""
prompts.py
Centralised prompt templates used by ai_service.py when the
application is running in AI (API) mode. Keeping every prompt in
one place makes the AI behaviour easy to audit and tune.
"""

PROFILE_ANALYSIS_PROMPT = """You are an expert technical recruiter and career coach.
Analyse the following student profile and resume text. Return ONLY a JSON object
(no markdown, no commentary) with this exact shape:

{{
  "skills": ["..."],
  "projects": ["..."],
  "education": "short string",
  "experience_level": "Beginner | Intermediate | Advanced",
  "strengths": ["..."],
  "weaknesses": ["..."],
  "strategy_summary": "one short paragraph describing how the interview should be focused"
}}

Student Name: {name}
Target Role: {target_role}
Stated Experience Level: {experience_level}
Stated Skills: {skills}
Career Goal: {career_goal}
Resume Text:
{resume_text}
"""

QUESTION_GENERATION_PROMPT = """You are an AI interviewer conducting a {interview_type} interview
for the role of {target_role}. The candidate's experience level is {experience_level}.

Current category to focus on: {category}
Target difficulty: {difficulty}

Previously asked questions (do not repeat these or ask near-duplicates):
{asked_questions}

Candidate's recent performance signal: {performance_signal}

Write exactly ONE interview question for this category and difficulty.
Return ONLY the question text, nothing else - no numbering, no preamble.
"""

ANSWER_EVALUATION_PROMPT = """You are grading a candidate's interview answer.

Question ({category}, {difficulty}): {question}
Candidate answer: {answer}

Score the answer from 0-10 on each metric: correctness, relevance, completeness,
technical_depth, clarity, reasoning.
Then write a short (1-2 sentence) constructive feedback comment.
Do not reveal your reasoning process, only the final result.

Return ONLY a JSON object with this exact shape:
{{
  "correctness": 0-10,
  "relevance": 0-10,
  "completeness": 0-10,
  "technical_depth": 0-10,
  "clarity": 0-10,
  "reasoning": 0-10,
  "feedback": "short feedback string"
}}
"""

PRACTICE_GENERATION_PROMPT = """You are creating a personalised practice question to help a
candidate improve in the weak category "{category}" for the role of {target_role}.
Their weakest sub-topics observed so far: {weak_topics}
This is practice question number {practice_number} for this category.

Return ONLY the practice question text, nothing else.
"""

REASSESSMENT_QUESTION_PROMPT = """You are generating a reassessment interview question that tests
the SAME underlying skill as this original question, but phrased differently and at a
slightly deeper / more applied level, to check for genuine improvement (not memorised answers).

Original question ({category}, {difficulty}): {original_question}
Target role: {target_role}

Return ONLY the new question text, nothing else.
"""

FEEDBACK_SUMMARY_PROMPT = """Summarise the candidate's overall interview performance for role
{target_role} in 2-3 encouraging but honest sentences, referencing their strongest and
weakest categories.

Category scores: {category_scores}
Overall score: {overall_score}
Result: {result}

Return ONLY the summary text.
"""
