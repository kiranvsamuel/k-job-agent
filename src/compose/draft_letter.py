import glob
import argparse, datetime as dt, os, re, json
from typing import Optional
from unidecode import unidecode
import fitz  # PyMuPDF

from ..db.db import SessionLocal
from ..db.models import Job, Company
from ..llm.ollama_client import generate_cover_letter, generate_email_body, generate_cover_letter_and_email_body
from src.match.rank import score_job
import time
from time import sleep

def _extract_resume_text(pdf_path: str) -> str:
    doc = fitz.open(pdf_path)
    chunks = [p.get_text() for p in doc]
    return unidecode("\n".join(chunks)).strip()

def _trim_text(s: str, max_chars: int = 12000) -> str:
    s = s.strip()
    return s if len(s) <= max_chars else s[:max_chars] + "\n...[trimmed]"

def _safe_name(s: str) -> str:
    return re.sub(r"[^\w\-]+", "_", s).strip("_")

def _word_count(s: str) -> int:
    return len((s or "").split())

def write_md(outdir: str, job, company: str, result, model_name: str) -> str:
    os.makedirs(outdir, exist_ok=True)
    fname = f"{job.id}_{_safe_name(company)}_{_safe_name(job.title or 'role')}_{dt.date.today().isoformat()}.md"
   # print(job.contact_email)
    path = os.path.join(outdir, fname)
    md = f"""---
            company: "{company}"
            role: "{job.title or ''}"
            location: "{job.location or ''}"
            url: "{job.url or ''}"
            source: "{job.source or ''}"
            posted_at: "{(job.posted_at.isoformat() if job.posted_at else '')}"
            generated_at: "{dt.datetime.now().isoformat(timespec='seconds')}"
            model: "{model_name}"
            word_count: {_word_count(result.cover_letter)}
            ---

            # Cover Letter

            {result.cover_letter} 

            ---

            ## Match summary
            {result.match_summary}

            ## Strengths
            {chr(10).join(f"- {s}" for s in result.strengths)}

            ## EmailBody
            {result.email_body or 'N/A'}

            ## EmailsTo
            {job.contact_email or 'N/A'}


            """
    with open(path, "w", encoding="utf-8") as f:
        f.write(md)
    return path

def main():
    ap = argparse.ArgumentParser(description="Draft a tailored cover letter with Llama.")
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--job-id", type=int, help="Draft for a single job id")
    group.add_argument("--top-n", type=int, help="Draft for top N ranked jobs")
    group.add_argument("--all-jobs", action="store_true", help="Draft for all jobs")
    group.add_argument("--batch", type=str, help="Process specific batch (e.g., '1/4', '2/4')")

    ap.add_argument("--resume-pdf", type=str, default="data/resumes/resume.pdf")
    ap.add_argument("--resume-profile", type=str, default="data/resume_profile.json",
                    help="JSON resume skills profile (for ranking)")
    ap.add_argument("--model", type=str, default="llama3:8b")
    ap.add_argument("--outdir", type=str, default="data/drafts")
    args = ap.parse_args()

    # Load resume text (for LLM letter generation)
    resume_text = _extract_resume_text(args.resume_pdf)
    print(f"[resume] Extracted {len(resume_text)} chars from {args.resume_pdf}")
    
    # Load resume profile for scoring if needed
    resume_skills = {}
    if args.top_n or args.all_jobs or args.batch:
        with open(args.resume_profile) as f:
            profile = json.load(f)
        resume_skills = {k: float(v) for k, v in profile.get("skills", {}).items()}

    s = SessionLocal()
    
    if args.job_id:
        results = (
            s.query(Job, Company)
             .join(Company, Company.id == Job.company_id)
             .filter(Job.id == args.job_id)
             .filter(Job.applied_at.is_(None)) 
             .all()
        )
    elif args.batch:
        # Parse batch argument (e.g., "1/4", "2/4")
        batch_num, total_batches = map(int, args.batch.split('/'))
        print(f"Processing batch {batch_num} of {total_batches}")
        
        rows = (
            s.query(Job, Company)
             .join(Company, Company.id == Job.company_id)
             .filter(Job.applied_at.is_(None)) 
             .all()
        )
        scored = []
        for job, comp in rows:
            score, _ = score_job(resume_skills, job)
            scored.append((score, job, comp))

        scored.sort(key=lambda x: x[0], reverse=True)
        
        # Calculate batch boundaries
        total_jobs = len(scored)
        jobs_per_batch = total_jobs // total_batches
        start_idx = (batch_num - 1) * jobs_per_batch
        end_idx = start_idx + jobs_per_batch if batch_num < total_batches else total_jobs
        
        results = [(job, comp) for _, job, comp in scored[start_idx:end_idx]]
        print(f"Batch {batch_num}: processing jobs {start_idx + 1} to {end_idx} ({len(results)} jobs)")
        
    elif args.all_jobs:
        print("Processing all jobs")
        rows = (
            s.query(Job, Company)
             .join(Company, Company.id == Job.company_id)
             .filter(Job.applied_at.is_(None)) 
             .all()
        )
        scored = []
        for job, comp in rows:
            score, _ = score_job(resume_skills, job)
            scored.append((score, job, comp))

        scored.sort(key=lambda x: x[0], reverse=True)
        results = [(job, comp) for _, job, comp in scored]
    else:  # top-n mode
        print(f"Processing top {args.top_n} jobs")
        rows = (
            s.query(Job, Company)
             .join(Company, Company.id == Job.company_id)
             .all()
        )
        scored = []
        for job, comp in rows:
            score, _ = score_job(resume_skills, job)
            scored.append((score, job, comp))

        scored.sort(key=lambda x: x[0], reverse=True)
        results = [(job, comp) for _, job, comp in scored[: args.top_n]]

    s.close()

    if not results:
        raise SystemExit("No jobs found.")

    print(f"Processing {len(results)} jobs...")
    
    # Loop over jobs
    for i, (job, comp) in enumerate(results, 1):
        print(f"Processing job {i}/{len(results)}: {comp.name} - {job.title}")
        #print(f"\nEmail CONTACTTTTTTTTTTTT: {job.contact_email}\n")
        is_file_existing = False
        fname = f"{job.id}_{_safe_name(comp.name)}_{_safe_name(job.title or 'role')}_{dt.date.today().isoformat()}.md"
        path = os.path.join(args.outdir, fname)

        #print(f"[PATH - {i}/{len(results)}] {path} ")
        # Check if any file exists that starts with {job.id}_
        pattern = os.path.join(args.outdir, f"{job.id}_*")
        matching_files = glob.glob(pattern)
        
        # If any files match the pattern, skip this job
        if matching_files:
            print(f"[draft {i}/{len(results)}] Skipping -> Found existing files for job {job.id}: {[os.path.basename(f) for f in matching_files]}")
            continue

        jd_text = _trim_text(job.jd_text or "", max_chars=12000)
        
        try:
            result = generate_cover_letter_and_email_body(  #generate_email_body(  #generate_cover_letter
                company=comp.name,
                title=job.title or "",
                jd_text=jd_text,
                resume_text=resume_text,
                model=args.model,
            )
            
            out_path = write_md(args.outdir, job, comp.name, result, args.model)
            print(f"[draft {i}/{len(results)}] Saved -> {out_path}")
            
            # Add delay between requests to avoid overwhelming the LLM
            if i < len(results):
                sleep(10)
                
        except Exception as e:
            print(f"Error processing job {job.id}: {e}")
            continue

if __name__ == "__main__":
    main()