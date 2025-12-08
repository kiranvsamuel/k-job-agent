from pydantic import BaseModel, Field
from typing import List

SYSTEM_PROMPT = """You are an expert career writer.
Write concise, specific, US-English cover letters for new-grad or junior candidates (0–2 years).
Never invent facts not present in the resume. Keep a friendly, confident tone.
"""

USER_PROMPT_TEMPLATE = """Company: {company}
Role title: {title}

Job description:
<<<JD>>>
{jd_text}
<<<END JD>>>

Resume:
<<<RESUME>>>
{resume_text}
<<<END RESUME>>>

Tasks:
1) Briefly summarize fit (1–3 sentences).
2) List up to 5 concrete strengths directly supported by the resume and relevant to the JD.
3) List willingness to learn and fill gaps or lighter areas (no deal-breaker tone).
4) Write a tailored cover letter of **180–220 words**. Do not restate the resume; show alignment with the JD. Keep it single-paragraph or two short paragraphs, no headings or bullets. No placeholders.

Only return JSON that matches the provided schema.
"""

class CoverLetterOut(BaseModel):
    match_summary: str = Field(..., description="1–3 sentences summarizing fit")
    strengths: List[str] = Field(..., description="Up to 5")
    #gaps: List[str] = Field(..., description="Up to 3")
    cover_letter: str = Field(..., description="180–220 words")
    email_body: str = Field(..., description="150–320 words")
