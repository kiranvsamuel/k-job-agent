# Command-line interface

import argparse
from .generator import generate_cover_data, save_to_markdown
from ..parse_resume import extract_text_from_pdf

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume", required=True, help="Path to resume PDF")
    parser.add_argument("--job-id", required=True, help="Job ID from database")
    args = parser.parse_args()

    # Fetch job data (mock example)
    job = {
        "company": "Google",
        "title": "Junior Python Developer",
        "jd_text": "Must know Python, SQL, and AWS...",
    }
    
    # Extract resume text
    resume_text = extract_text_from_pdf(args.resume)
    
    # Generate cover letter
    data = generate_cover_data(
        company=job["company"],
        title=job["title"],
        jd_text=job["jd_text"],
        resume_text=resume_text,
    )
    
    # Save to Markdown
    filename = f"{job['company'].lower()}_{job['title'].replace(' ', '_')}"
    save_to_markdown(data, filename)
    print(f"Saved to data/drafts/{filename}.md")

if __name__ == "__main__":
    main()