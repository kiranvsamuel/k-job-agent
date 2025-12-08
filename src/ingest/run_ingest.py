import re, yaml, requests, datetime as dt, html
from sqlalchemy import select
from ..db.db import SessionLocal
from ..db.models import Company, Job
from ..llm.ollama_client import extract_company_emails  
from typing import Optional, Set

JR = re.compile(r'\b(entry|junior|new\s*grad|intern(ship)?|0\s*[-–]?\s*2\s*years|1[-–]2\s*years)\b', re.I)

EMAIL_RX = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

def extract_contact_email(jd_raw: str, raw_json: dict, company: str, ollama_emails: str) -> Optional[str]:
    """
    Extract contact email by first checking local JD/JSON, then using Ollama for company emails.
    Returns consolidated comma-separated string of unique emails.
    """
    # Define exclusion terms
    exclude_terms = ["accommodat", "access", "compliance", "dpo", "security", 
                    "humans", "people-team", "g.biow", "support", "benefit"]
    
    found_emails = set()
    
    # 1) First, check JD text for emails
    if jd_raw:
        jd_emails = EMAIL_RX.findall(jd_raw)
        for email in jd_emails:
            email_lower = email.lower()
            if not any(term in email_lower for term in exclude_terms):
                found_emails.add(email.strip())
    
    # 2) Check JSON metadata for emails
    if isinstance(raw_json, dict):
        for v in raw_json.values():
            if isinstance(v, str):
                json_emails = EMAIL_RX.findall(v)
                for email in json_emails:
                    email_lower = email.lower()
                    if not any(term in email_lower for term in exclude_terms):
                        found_emails.add(email.strip())
    
    # 3) Use Ollama to get company emails (if company and job_url are provided)
    #ollama_emails = None
    if company and ollama_emails:
        try:
            #ollama_emails = extract_company_emails(company, job_url)
            if ollama_emails:
                # Parse comma-separated string into individual emails
                ollama_email_list = [email.strip() for email in ollama_emails.split(',') if email.strip()]
                for email in ollama_email_list:
                    email_lower = email.lower()
                    if not any(term in email_lower for term in exclude_terms):
                        found_emails.add(email)
        except Exception as e:
            print(f"Warning: Ollama email extraction failed: {e}")
            # Continue with locally found emails
    
    # 4) Return consolidated result
    if found_emails:
        return ','.join(sorted(found_emails))
    return None

def clean_html_text(text):
    if not text:
        return ""
    
    # HTML unescaping
    prev_text = ""
    while prev_text != text:
        prev_text = text
        text = html.unescape(text)
    
    # Replace HTML elements with spaces
    text = re.sub(r'</(div|p|li|h[1-6]|br|ul|ol)>', ' ', text, flags=re.IGNORECASE)
    text = re.sub(r'<(div|p|li|h[1-6]|br|ul|ol)[^>]*>', ' ', text, flags=re.IGNORECASE)
    
    # Remove all other HTML tags
    text = re.sub(r'<[^>]+>', ' ', text)
    
    # Convert specific dash types to standard hyphens
    text = re.sub(r'[—–−]', '-', text)  # Replace em-dash, en-dash, minus with hyphen
    
    # Optionally collapse multiple hyphens
    text = re.sub(r'-{2,}', '-', text)
    
    # Handle HTML entities and whitespace
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'&[a-zA-Z]+;', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\n\s*\n+', '\n', text)
    
    return text.strip()

def junior_ok(title, jd): 
    clean_title = clean_html_text(title)
    clean_jd = clean_html_text(jd)
    return bool(JR.search((clean_title or "") + "\n" + (clean_jd or "")))

def upsert_company(session, c):
    db = session.query(Company).filter_by(name=c["name"]).one_or_none()
    if not db:
        db = Company(**c)
        session.add(db)
        session.flush()
    return db

def run():
    with open("src/ingest/k-companies_seed.yaml") as f:
        data = yaml.safe_load(f)

    companies = data["companies"]

    s = SessionLocal()
    try:
        for c in companies:
            company = upsert_company(s, c)
            s.commit()
            print(f"Processing company: {company.name} ({company.ats_type})")
            ollama_emails = None
            if company.website:
                ollama_emails = extract_company_emails(company.name, company.website)
            print(f"Extracted company emails: {ollama_emails} ")
            
            if c["ats_type"] == "greenhouse":
                url = f"https://boards-api.greenhouse.io/v1/boards/{c['ats_slug']}/jobs?content=true"
                try:
                    jobs = requests.get(url, timeout=30).json().get("jobs", [])
                except (requests.RequestException, ValueError) as e:
                    print(f"Error fetching jobs from {company.name}: {e}")
                    continue
                    
                for j in jobs:
                    title = j["title"]
                    jd_raw = j.get("content", "")
                    
                    if not junior_ok(title, jd_raw): 
                        continue
                    
                    # Clean once for storage
                    jd_clean = clean_html_text(jd_raw)
                    url_job = j["absolute_url"]
                    loc = (j.get("location") or {}).get("name")
                    posted = j.get("updated_at")
                    contact_email = extract_contact_email(jd_raw, j,company.name, ollama_emails)

                    if not s.query(Job).filter_by(url=url_job).first():
                        print(f"Found junior job: {title}")
                        print(f"Clean preview: {jd_clean[:200]}...")
                        print("-" * 60)
                        
                        s.add(Job(
                            company_id=company.id, 
                            title=title, 
                            jd_text=jd_clean, 
                            url=url_job,
                            location=loc, 
                            posted_at=dt.datetime.fromisoformat(posted.replace("Z", "+00:00")) if posted else None,
                            source="greenhouse", 
                            raw_json=j,
                            contact_email=contact_email,  
                        ))
                        
            elif c["ats_type"] == "lever":
                url = f"https://api.lever.co/v0/postings/{c['ats_slug']}?mode=json"
                try:
                    resp = requests.get(url, timeout=30).json()
                except (requests.RequestException, ValueError) as e:
                    print(f"Error fetching jobs from {company.name}: {e}")
                    continue
                
                if isinstance(resp, dict):
                    jobs = resp.get("postings") or resp.get("jobs") or []
                elif isinstance(resp, list):
                    jobs = resp
                else:
                    print(f"Unexpected response format from {company.name}")
                    continue

                for j in jobs:
                    title = j.get("text", "")
                    jd_raw = j.get("description", "")
                    
                    if not junior_ok(title, jd_raw): 
                        continue
                    
                    # Clean once for storage
                    jd_clean = clean_html_text(jd_raw)
                    url_job = j["hostedUrl"]
                    loc = (j.get("categories") or {}).get("location")
                    posted_ms = j.get("createdAt")
                    posted = dt.datetime.utcfromtimestamp(posted_ms/1000) if posted_ms else None
                    contact_email = extract_contact_email(jd_raw, j,company.name, ollama_emails)

                    if not s.query(Job).filter_by(url=url_job).first():
                        print(f"Found junior job: {title}")
                        print(f"Clean preview: {jd_clean[:200]}...")
                        print("-" * 60)
                        
                        s.add(Job(
                            company_id=company.id, 
                            title=title, 
                            jd_text=jd_clean, 
                            url=url_job,
                            location=loc, 
                            posted_at=posted, 
                            source="lever", 
                            raw_json=j,
                            contact_email=contact_email,  
                        ))
            s.commit()
    finally:
        s.close()

if __name__ == "__main__":
    run()