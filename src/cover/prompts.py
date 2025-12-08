 # LLM prompt templates

COVER_LETTER_PROMPT = """\
You are a career advisor. Write a tailored cover letter (180–220 words) for this job:

**Job Title**: {title}
**Company**: {company}
**Job Description**: {jd_text}

**Applicant Resume Summary**: {resume_text}

Guidelines:
- First paragraph: Express enthusiasm for the role/company.
- Second paragraph: Highlight 2-3 key strengths matching the job.
- Third paragraph: Address gaps (if any) and eagerness to learn.
- Tone: Professional but conversational.
"""

ANALYSIS_PROMPT = """\
Analyze this job description and resume:
- List TOP 3 strengths (resume skills that match the job).
- List TOP 2 gaps (missing but desired skills).
- Summarize fit in 1 sentence.
"""