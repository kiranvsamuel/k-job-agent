import re
import yaml
from pathlib import Path
import requests
from playwright.sync_api import sync_playwright
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
import os
from src.submit.k_pushover import push  # new import

def parse_draft_parts(draft_path) -> dict:
    """
    Parses a job draft markdown file using line-by-line parsing for maximum reliability.
    FIXED: Now handles YAML with extra indentation.
    """
    if isinstance(draft_path, str):
        draft_path = Path(draft_path)
    print(f"Parsing draft: {draft_path}")
    
    try:
        text = draft_path.read_text(encoding="utf-8")
        print(f"File exists: {draft_path.exists()}")
        print(f"File size: {len(text)} bytes")
        print(f"First 200 chars: '{text[:200]}'")
    except Exception as e:
        print(f"❌ Error reading file: {e}")
        return {}
    
    # --- Extract YAML front matter ---
    meta = {}
    yaml_match = re.search(r"^---\s*(.*?)\s*---", text, re.DOTALL | re.MULTILINE)
    
    if yaml_match:
        yaml_text = yaml_match.group(1)
        print(f"YAML found: {len(yaml_text)} chars")
        try:
            # FIX: Remove ALL leading whitespace from each line
            # This handles the extra indentation in your YAML
            cleaned_lines = []
            for line in yaml_text.splitlines():
                stripped = line.strip()
                if stripped:  # Only add non-empty lines
                    cleaned_lines.append(stripped)
            
            cleaned_yaml = '\n'.join(cleaned_lines)
            print(f"Cleaned YAML (first 200 chars): '{cleaned_yaml[:200]}'")
            
            meta = yaml.safe_load(cleaned_yaml) or {}
            print(f"✅ YAML parsed successfully: {list(meta.keys())}")
        except yaml.YAMLError as e:
            print(f"❌ YAML parsing error: {e}")
            # Continue anyway - we can still parse the markdown sections
    else:
        print("⚠️ No YAML front matter found!")
    
    # Remove YAML front matter
    content = re.sub(r"^---.*?---\s*", "", text, flags=re.DOTALL | re.MULTILINE)
    print(f"Content after YAML removal: {len(content)} chars")
    print(f"First 100 chars of content: '{content[:100]}'")
    
    # --- Line-by-line parsing ---
    sections = {
        "cover_letter": "",
        "match_summary": "", 
        "strengths": "",
        "email_body": "",
        "emails_to": ""
    }
    
    current_section = None
    lines = content.split('\n')
    
    print(f"Total lines to parse: {len(lines)}")
    
    for i, line in enumerate(lines):
        line = line.strip()
        
        # Debug: print first few lines to see structure
        if i < 10:
            print(f"Line {i}: '{line}'")
        
        # Check if this line starts a new section
        if line.startswith('#'):
            print(f"Found header: '{line}'")
            if 'Cover Letter' in line:
                current_section = 'cover_letter'
                print("→ Switching to cover_letter section")
            elif 'Match summary' in line:
                current_section = 'match_summary'
                print("→ Switching to match_summary section")
            elif 'Strengths' in line:
                current_section = 'strengths'
                print("→ Switching to strengths section")
            elif 'EmailBody' in line:
                current_section = 'email_body'
                print("→ Switching to email_body section")
            elif 'EmailsTo' in line:
                current_section = 'emails_to'
                print("→ Switching to emails_to section")
            continue
        
        # Add content to current section
        if current_section and line:
            if sections[current_section]:
                sections[current_section] += '\n' + line
            else:
                sections[current_section] = line
    
    # Print what we found
    print("\n=== PARSING RESULTS ===")
    for section_name, content in sections.items():
        print(f"{section_name}: '{content[:100]}{'...' if len(content) > 100 else ''}'")
    
    # --- Format email body ---
    if sections['email_body']:
        sections['email_body'] = sections['email_body'].replace('Dear Hiring Manager,', 'Dear Hiring Manager,\n')
        sections['email_body'] = sections['email_body'].replace('Sincerely,', '\nSincerely,\n')
        sections['email_body'] = sections['email_body'].replace('Best regards,', '\nBest regards,\n')

    # Prepare emails_to list
    emails_to = []
    if sections['emails_to']:
        emails_to = [e.strip() for e in sections['emails_to'].split(",") if e.strip()]
    
    print(f"Final emails_to: {emails_to}")
    
    return {
        **meta,
        "cover_letter": sections["cover_letter"],
        "match_summary": sections["match_summary"], 
        "strengths": sections["strengths"],
        "email_body": sections["email_body"],
        "emails_to": emails_to,
    }


def submit_via_email_and_send_push_notification(job, draft_md_path, sender_email, smtp_config):
    """
    Send the parsed draft cover letter as an email.
    """
    print("submit_via_email")
    draft_data = parse_draft_parts(Path(draft_md_path))
    email_body = draft_data["email_body"]

    msg = MIMEText(email_body, "plain")
    # SEND EMAIL
    k_send_email(
        email_subject=f"Application for {job.title}",
        email_body=email_body,
        to_emails=job.contact_email,
        sender_email=sender_email,
        smtp_config=smtp_config,
        pdf_path="./data/resumes/resume-latest.pdf"
    )
    # PUSH NOTIFICATION
    user_key = os.getenv("PUSHOVER_USER")
    api_token = os.getenv("PUSHOVER_API_TOKEN")
    push_msg = f"EMAIL SENT TO:\n {job.contact_email} \n\nJOB TITLE:\n {job.title} \n\nEMAIL DETAILS:\n {email_body}"
    push(push_msg, f"Applied for Job #{job.id} : {job.title}", user_key, api_token)
    user_key2 = os.getenv("PUSHOVER_USER_3")
    api_token2 = os.getenv("PUSHOVER_API_TOKEN_3")
    push(push_msg, f"Applied for Job #{job.id} : {job.title}", user_key2, api_token2)


def k_send_email_text(email_subject, email_body, to_emails, sender_email, smtp_config):
    print('test email function called - k_send_email_text')
    
    TO_emails = to_emails.split(",")
    
    msg = MIMEText(email_body, "plain")
    msg["Subject"] = email_subject
    msg["From"] = sender_email
    msg["To"] = to_emails
    
    with smtplib.SMTP(smtp_config["host"], smtp_config["port"]) as server:
        server.starttls()
        server.login(smtp_config["user"], smtp_config["password"])
        server.sendmail(sender_email, TO_emails, msg.as_string())

    print(f"[submit] Test Email sent to {len(TO_emails)} recipients")


def k_send_email(email_subject, email_body, to_emails, sender_email, smtp_config, pdf_path=None):
    TO_emails = [email.strip() for email in to_emails.split(",")]
    msg = MIMEMultipart()
    msg["Subject"] = email_subject
    msg["From"] = sender_email
    msg["To"] = to_emails
    msg["cc"] = os.getenv("EMAIL_CC", "")
    msg.attach(MIMEText(email_body, "plain"))
    
    pdf_path = os.getenv("EMAIL_ATTACHMENT", None)
    if pdf_path and os.path.exists(pdf_path):
        try:
            with open(pdf_path, "rb") as pdf_file:
                pdf_attachment = MIMEApplication(pdf_file.read(), _subtype="pdf")
                pdf_attachment.add_header(
                    "Content-Disposition",
                    "attachment",
                    filename=os.path.basename(pdf_path)
                )
                msg.attach(pdf_attachment)
        except Exception as e:
            print(f"[error] Failed to attach PDF: {e}")
    
    with smtplib.SMTP(smtp_config["host"], smtp_config["port"]) as server:
        server.starttls()
        server.login(smtp_config["user"], smtp_config["password"])
        server.sendmail(sender_email, TO_emails, msg.as_string())

    print(f"\n* [submit] Email with attachment sent to {len(TO_emails)} recipients")


def submit_via_greenhouse(job, draft_md_path):
    print("\nSubmitting via Greenhouse ATS...")
    draft_data = parse_draft_parts(Path(draft_md_path))
    email_body = draft_data["email_body"]
    resume_pdf = os.getenv("EMAIL_ATTACHMENT", None)
    url = draft_data["url"]
    path_parts = url.rstrip('/').split('/')
    job_id = path_parts[-1]
    slug = path_parts[-3]
    api_url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs/{job_id}/applications"
    print(f"[submit] Submitting to Greenhouse API: {api_url}")
    pdf_path = os.getenv("EMAIL_ATTACHMENT", None)
    print(f"[submit] Using resume PDF: {pdf_path}")
    files = {"resume": open(resume_pdf, "rb")}
    data = {"cover_letter": email_body}
    r = requests.post(api_url, files=files, data=data)
    print(f"[submit] Greenhouse response: {r.status_code}")
    return r.status_code == 200


def submit_via_form(job, draft_md, resume_pdf):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(job.url)
        page.fill("input[name='name']", "Your Name")
        page.fill("input[name='email']", "your@email.com")
        page.fill("textarea[name='cover_letter']", draft_md)
        page.set_input_files("input[type='file']", resume_pdf)
        page.click("button[type='submit']")
        browser.close()
    print(f"[submit] Form submitted -> {job.url}")