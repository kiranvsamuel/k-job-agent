from typing import Dict
from pydantic import ValidationError
from ollama import chat
from .templates import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE, CoverLetterOut
import json
import re
from typing import Optional
from urllib.parse import urlparse
import time


SCHEMA = CoverLetterOut.model_json_schema()  # JSON Schema for structured outputs

def _word_count(s: str) -> int:
    return len((s or "").split())

def generate_cover_letter(company: str, title: str, jd_text: str, resume_text: str,
                          model: str = "llama3.2:8b-instruct",
                          temperature: float = 0.3) -> CoverLetterOut:
    """
    Returns a validated CoverLetterOut (match_summary, strengths, gaps, cover_letter).
    Enforces 180–220 words by optionally issuing one revision round.
    """
    user_prompt = USER_PROMPT_TEMPLATE.format(
        company=company.strip(),
        title=title.strip(),
        jd_text=jd_text.strip(),
        resume_text=resume_text.strip()
    )
    print(user_prompt)
    # 1) First pass with strict schema
    resp = chat(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        # JSON Schema -> model must return only that JSON
        format=SCHEMA,
        stream=False,
        options={
            "temperature": temperature,
            "num_predict": 500,      # plenty for JSON + 220-word letter
            "top_p": 0.9,
        },
    )
    content = resp.message.content  # JSON string
    print(f"[LLM] Raw output: {content[:500]}...")  # Show first 500 chars for debugging
    #def _parse_out(json_text: str) -> CoverLetterOut:
    #   return CoverLetterOut.model_validate_json(json_text)
    def parse_out(json_text: str) -> CoverLetterOut:
        """Parse and validate the LLM output with better error handling"""
        try:
            # First try direct JSON parsing
            return CoverLetterOut.model_validate_json(json_text)
        except json.JSONDecodeError:
            # If that fails, try to extract JSON from the text
            json_match = re.search(r'\{.*\}', json_text, re.DOTALL)
            if json_match:
                try:
                    return CoverLetterOut.model_validate_json(json_match.group())
                except:
                    pass
            
            # If still failing, provide a fallback
            print(f"WARNING: Failed to parse LLM output as JSON. Using fallback.")
            print(f"Raw output: {json_text[:500]}...")  # Show first 500 chars for debugging
            
            # Create a fallback response
            return CoverLetterOut(
                cover_letter="[Failed to generate cover letter - LLM returned invalid format]",
                match_summary="Unable to generate match analysis",
                strengths=["Analysis unavailable"],
                #gaps=["Analysis unavailable"],
                email_body="N/A"
            )
        except Exception as e:
            print(f"ERROR parsing LLM output: {e}")
            # Fallback response
            return CoverLetterOut(
                cover_letter="[Error generating cover letter]",
                match_summary="Error in analysis",
                strengths=["Analysis failed"],
                email_body=["emailbody failed"],
                #gaps=["Analysis failed"]
            )
    try:
        out = parse_out(content)
    except ValidationError:
        # Fallback: strip accidental code fences or comments if any
        import re
        fixed = re.sub(r"^```json|```$", "", content.strip(), flags=re.I|re.M)
        out = parse_out(fixed)

    # 2) Enforce 180–220 words with a single revision if needed
    wc = _word_count(out.cover_letter)
    if wc < 180 or wc > 220:
        target = 200
        revision_schema = {
            "type": "object",
            "properties": {"cover_letter": {"type": "string"}},
            "required": ["cover_letter"],
        }
        rev_prompt = (
            f"Revise the following letter to land between 180 and 220 words "
            f"(target ≈ {target}). Keep all facts. Return ONLY JSON with 'cover_letter'.\n\n"
            f"---\n{out.cover_letter}\n---"
        )
        rev = chat(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": rev_prompt},
            ],
            format=revision_schema,
            stream=False,
            options={"temperature": 0.2, "num_predict": 400},
        )
        import json
        new_letter = json.loads(rev.message.content)["cover_letter"]
        # Keep original analysis fields
        out.cover_letter = new_letter
        print(f"[LLM] Revised letter from {wc} to {_word_count(new_letter)} words.")
    return out

def generate_email_body(company: str, title: str, jd_text: str, resume_text: str,
                        model: str = "llama3.2:8b-instruct",
                        temperature: float = 0.3) -> str:
    """
    Generates a concise, professional email body for applying to a job via email.
    Targets 125–175 words. Includes fallback if parsing fails.
    """
    EMAIL_PROMPT_TEMPLATE = f"""
You are a helpful assistant that writes professional and concise job application emails.

Write a short email body to apply for the position of "{title}" at "{company}".
Use the resume below to highlight relevant skills and experience.
Also consider the job description to tailor the message.

Guidelines:
- Do NOT copy or repeat the cover letter format
- Aim for 125–175 words
- Be concise, warm, and confident
- Include a reference to the job title and a brief mention of alignment
- No need to sign the email (e.g., don't include name or contact info)
- Do not format as JSON

---
[Job Description]
{jd_text.strip()}

---
[Resume]
{resume_text.strip()}
"""

    resp = chat(
        model=model,
        messages=[
            {"role": "system", "content": "You are a helpful assistant that generates job application emails."},
            {"role": "user", "content": EMAIL_PROMPT_TEMPLATE}
        ],
        stream=False,
        options={
            "temperature": temperature,
            "num_predict": 400,
            "top_p": 0.9,
        }
    )

    content = resp.message.content.strip()
    print(f"[LLM] Raw email output: {content[:500]}...")

    # Optional: enforce word count range
    wc = _word_count(content)
    if wc < 125 or wc > 175:
        print(f"[LLM] Email length {wc} words. Triggering revision to target 150.")
        revision_prompt = (
            f"Revise the following email to land between 125 and 175 words (target ≈ 150). "
            f"Keep all facts and tone. Return only the revised email text.\n\n---\n{content}\n---"
        )
        rev = chat(
            model=model,
            messages=[
                {"role": "system", "content": "You revise job application emails to meet length requirements."},
                {"role": "user", "content": revision_prompt},
            ],
            stream=False,
            options={"temperature": 0.2, "num_predict": 350},
        )
        content = rev.message.content.strip()
        print(f"[LLM] Revised email to {_word_count(content)} words.")

    return content

def generate_cover_letter_and_email_body(company: str, title: str, jd_text: str, resume_text: str,
                         model: str = "llama3:8b",
                         temperature: float = 0.3) -> CoverLetterOut:
    """
    Optimized for Ollama + Llama3 on multi-core Mac. Single call generates both cover letter and email.
    Email body is formatted professionally with salutation, signature, and contact information.
    """
    # Streamlined prompt for better Llama3 comprehension
    COMBINED_PROMPT = """Generate a job application package.

CONTEXT: Applying for {title} at {company}

JOB REQUIREMENTS:
{jd_text}

MY BACKGROUND:
{resume_text}

Generate ONE output:

1. EMAIL BODY (200 words): Professional email format that:
   - Starts with "Dear Hiring Manager,"
   - Has concise, impactful content tailored for email
   - Includes a sentence asking to consider for junior software positions
   - Ends with the exact signature:
     <<REDACTED_NAME>>
     <<REDACTED_EMAIL>> | phone: <<REDACTED_PHONE>>
     <<REDACTED_LINKEDIN>>
     <<REDACTED_GITHUB>>
   - Contains different content from the cover letter but same key qualifications

Return VALID JSON with these exact fields:
{{
  "cover_letter": "full email body text here",
  "email_body": "full email body text here", 
  "match_summary": "2-3 sentence summary of qualifications match",
  "strengths": ["strength1"]
}}"""

#Generate TWO outputs:
#1. COVER LETTER (200 words): Formal business letter format with full address header, date, and signature

    user_prompt = COMBINED_PROMPT.format(
        company=company.strip(),
        title=title.strip(),
        jd_text=jd_text.strip()[:2000],  # Limit input size
        resume_text=resume_text.strip()[:2000]
    )

    print(f"[DEBUG] Prompt sent to LLM: {user_prompt[:200]}...")

    # Ollama-optimized schema
    SCHEMA = {
        "type": "object",
        "properties": {
            "cover_letter": {"type": "string"},
            "email_body": {"type": "string"},
            "match_summary": {"type": "string"},
            "strengths": {"type": "array", "items": {"type": "string"}}
        },
        "required": ["cover_letter", "email_body", "match_summary", "strengths"]
    }

    # Ollama-optimized parameters for 16-core Mac
    resp = chat(
        model=model,
        messages=[
            {"role": "system", "content": "You are a career advisor. Provide concise, professional job application content. Return ONLY valid JSON."},
            {"role": "user", "content": user_prompt},
        ],
        format=SCHEMA,
        stream=False,
        options={
            "temperature": temperature,
            "num_predict": 1024,  # Increased for combined output
            "top_k": 40,
            "top_p": 0.9,
            "repeat_penalty": 1.1,
            "num_thread": 14,  # Utilize 14 cores (leaves 2 for system)
            "num_gpu": 1,  # Use Metal acceleration if available
        },
    )

    content = resp.message.content
    print(f"[DEBUG] Raw LLM response: {content}")
    
    # Fast parsing with minimal overhead
    def fast_parse(json_text: str) -> CoverLetterOut:
        # Quick cleanup for common Llama3 output issues
        clean_text = json_text.strip()
        print(f"[DEBUG] Cleaned text: {clean_text[:500]}...")
        
        # Remove JSON code fences if present
        if clean_text.startswith('```json'):
            clean_text = clean_text[7:]
        if clean_text.endswith('```'):
            clean_text = clean_text[:-3]
        clean_text = clean_text.strip()
        
        try:
            print("[DEBUG] Attempting direct JSON parse...")
            return CoverLetterOut.model_validate_json(clean_text)
        except Exception as e:
            print(f"[DEBUG] Direct parse failed: {e}")
            # Fallback: extract JSON pattern with more robust regex
            import re
            json_match = re.search(r'\{[\s\S]*\}', clean_text)
            if json_match:
                try:
                    json_str = json_match.group()
                    print(f"[DEBUG] Extracted JSON: {json_str[:500]}...")
                    return CoverLetterOut.model_validate_json(json_str)
                except Exception as e2:
                    print(f"[DEBUG] Extracted JSON parse failed: {e2}")
                    pass
            
            # Ultimate fallback - construct better response with proper signature
            print("[DEBUG] Using fallback response")
            return CoverLetterOut(
                cover_letter=f"""Dear Hiring Manager,

I am writing to apply for the {title} position at {company}. With my background in AI engineering and system development, I am excited about the opportunity to contribute to your configuration management team.

My experience includes deploying end-to-end AI systems, cloud-native development, and secure system design. I am confident that my skills align well with the requirements for this role.

Thank you for considering my application. I look forward to discussing how I can contribute to Rocket Lab's innovative projects.

Sincerely,
<<REDACTED_NAME>>""",
                email_body=f"""Dear Hiring Manager,

I am writing to apply for the {title} position at {company}. My experience in AI-driven automation and secure system development aligns well with your requirements.

I have successfully deployed end-to-end AI systems and have strong skills in cloud-native development. I am excited about the opportunity to bring these capabilities to Rocket Lab's configuration management team.

Please also consider my resume for any other junior software positions that may be available, as I am eager to contribute to your organization's success.

Best regards,

<<REDACTED_NAME>>
<<REDACTED_EMAIL>> | phone: <<REDACTED_PHONE>>
<<REDACTED_LINKEDIN>>
<<REDACTED_GITHUB>>""",
                match_summary=f"AI engineer with full-stack development experience seeking to apply technical skills to configuration management at {company}",
                strengths=["AI-driven automation", "Cloud-native development", "Secure system design", "End-to-end system deployment"]
            )

    out = fast_parse(content)
    print(f"[DEBUG] Parsed output - Cover letter words: {_word_count(out.cover_letter)}, Email words: {_word_count(out.email_body)}")
    
    # Ensure email body has proper formatting with signature
    def ensure_email_format(email_text: str) -> str:
        """Ensure email has proper salutation, junior positions mention, and signature"""
        email_text = email_text.strip()
        
        # Ensure it starts with proper salutation
        if not email_text.startswith(('Dear', 'Dear Hiring Manager', 'Dear Recruiter')):
            email_text = f"Dear Hiring Manager,\n\n{email_text}"
        
        # Ensure it includes the junior positions mention
        junior_keywords = ['junior', 'other positions', 'consider my resume', 'other roles']
        if not any(keyword in email_text.lower() for keyword in junior_keywords):
            # Insert before the closing
            if 'Best regards' in email_text:
                parts = email_text.split('Best regards')
                email_text = parts[0] + "\nPlease also consider my resume for any other junior software positions that may be available, as I am eager to contribute to your organization's success.\n\nBest regards" + parts[1]
            else:
                email_text += "\n\nPlease also consider my resume for any other junior software positions that may be available."
        
        # Ensure proper signature
        signature = """<<REDACTED_NAME>>
<<REDACTED_EMAIL>> | phone: <<REDACTED_PHONE>>
<<REDACTED_LINKEDIN>>
<<REDACTED_GITHUB>>"""
        
        if signature not in email_text:
            # Remove any existing signature and add the correct one
            email_text = re.sub(r'(Best regards|Sincerely|Regards),?\s*\n.*$', '', email_text, flags=re.MULTILINE | re.DOTALL)
            email_text = email_text.rstrip() + f'\n\nBest regards,\n\n{signature}'
            
        return email_text

    # Apply email formatting if needed
    original_email = out.email_body
    out.email_body = ensure_email_format(out.email_body)
    if original_email != out.email_body:
        print("[DEBUG] Applied proper email structure with signature")

    # Smart revision - only if seriously out of bounds
    cl_words = _word_count(out.cover_letter)
    email_words = _word_count(out.email_body)
    
    needs_fix = (cl_words < 100 or cl_words > 400 or email_words < 100 or email_words > 400)
    
    if needs_fix:
        print(f"[REVISION] Cover letter: {cl_words} words, Email: {email_words} words")
        
        FIX_PROMPT = f"""Fix word counts while maintaining professional format:
- Cover letter: {cl_words} words → make it ~200 words (keep formal business letter format)
- Email: {email_words} words → make it ~200 words (keep "Dear Hiring Manager," opening, junior positions mention, and exact signature)

Keep the same key qualifications and professional tone. Just adjust length.

Current cover letter:
{out.cover_letter}

Current email:
{out.email_body}

Return JSON with 'cover_letter' and 'email_body'."""

        fix_schema = {
            "type": "object", 
            "properties": {
                "cover_letter": {"type": "string"},
                "email_body": {"type": "string"}
            },
            "required": ["cover_letter", "email_body"]
        }

        try:
            rev_resp = chat(
                model=model,
                messages=[{"role": "user", "content": FIX_PROMPT}],
                format=fix_schema,
                stream=False,
                options={
                    "temperature": 0.1,  # Lower temp for revisions
                    "num_predict": 512,
                    "num_thread": 14,
                },
            )
            
            fixed = fast_parse(rev_resp.message.content)
            out.cover_letter = fixed.cover_letter
            out.email_body = ensure_email_format(fixed.email_body)  # Re-apply formatting
            print(f"[FIXED] Cover letter: {_word_count(out.cover_letter)} words, Email: {_word_count(out.email_body)} words")
        except Exception as e:
            print(f"[REVISION FAILED] {e}")

    return out
def extract_company_emails(company: str, company_url: str, 
                          model: str = "llama3:8b-instruct-q6_K",
                          temperature: float = 0.1) -> Optional[str]:
    """
    Extract company email addresses using Ollama model for general inquiries, careers, HR, or recruiting purposes.
    Automatically extracts domain from job URL for email construction.
    Returns comma-separated string of emails or None if extraction fails.
    """
    # Extract domain from URL
    try:
        parsed_url = urlparse(company_url)
        domain = parsed_url.netloc
        
        # Remove www. if present and get the base domain
        if domain.startswith('www.'):
            domain = domain[4:]
        
        # Extract the main domain name (e.g., wise.com from wise.com)
        domain_parts = domain.split('.')
        if len(domain_parts) >= 2:
            company_domain = f"{domain_parts[-2]}.{domain_parts[-1]}"
        else:
            company_domain = domain
        
    except Exception as e:
        print(f"Error parsing URL {company_url}: {e}")
        return None
    # Pause for 5 seconds before the Ollama call
    time.sleep(10)
    # Construct the prompt
    prompt = f"""
                Find all general email addresses publicly associated with the company {company} (website: {company_domain}). The output should be a list of comma-separated email addresses in the following style:

                hello@{company_domain},careers@{company_domain},hr@{company_domain},talent@{company_domain},recruiting@{company_domain},recruit@{company_domain},jobs@{company_domain}

                Include common variations like:

                Anything starting with recruit → example: recruiting@{company_domain}
                Anything starting with talent → example: TalentAcquisition@{company_domain}
                Anything starting with career → example: careers@{company_domain}
                Anything starting with job → example: jobs@{company_domain}

                Do NOT include emails containing:
                "accommodat", "access", "compliance", "dpo", "security", "humans", "people-team", "g.biow", "support", "benefit"

                Only return emails suitable for general inquiries, careers, HR, or recruiting purposes. Avoid personal emails of employees or any internal-only addresses. The final output should be a single line, comma-separated list with no additional text.
                """
    try:
        
        # Make the call to Ollama
        response = chat(
            model=model,
            messages=[
                {"role": "system", "content": "You are an expert at extracting and formatting company contact information. Return only the requested data with no additional commentary."},
                {"role": "user", "content": prompt},
            ],
            stream=False,
            options={
                "temperature": temperature,
                "num_predict": 300,
                "top_p": 0.9,
                "num_thread": 12,
                "num_ctx": 4096, 
            },
        )
        
        # Pause for 2 seconds after the Ollama call
        time.sleep(14)
        # Extract and clean the response
        email_list = response.message.content.strip()
        
        # Validate that the response contains emails with the correct domain
        email_pattern = r'\b[A-Za-z0-9._%+-]+@' + re.escape(company_domain) + r'\b'
        valid_emails = re.findall(email_pattern, email_list)
        
        if valid_emails:
            # Remove duplicates and return as comma-separated string
            unique_emails = list(dict.fromkeys(valid_emails))
            return ','.join(unique_emails)
        else:
            # Fallback: check if there are any emails at all (in case domain extraction was wrong)
            fallback_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
            fallback_emails = re.findall(fallback_pattern, email_list)
            if fallback_emails:
                unique_emails = list(dict.fromkeys(fallback_emails))
                return ','.join(unique_emails)
            return None
            
    except Exception as e:
        print(f"Error extracting emails for {company}: {e}")
        # Pause for 2 seconds after the Ollama call
        time.sleep(10)
        return None
    

