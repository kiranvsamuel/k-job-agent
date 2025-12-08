# Core logic

import subprocess
import json
from typing import Dict
from pathlib import Path

def query_llama3(prompt: str) -> str:
    """Run Ollama with Llama3 and return output."""
    cmd = ["ollama", "run", "llama3", prompt]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout.strip()

def generate_cover_data(
    company: str,
    title: str,
    jd_text: str,
    resume_text: str,
) -> Dict[str, str]:
    """Generate analysis and cover letter."""
    # Step 1: Analyze fit
    analysis = query_llama3(
        ANALYSIS_PROMPT.format(
            title=title,
            company=company,
            jd_text=jd_text,
            resume_text=resume_text,
        )
    )
    
    # Step 2: Generate cover letter
    cover_letter = query_llama3(
        COVER_LETTER_PROMPT.format(
            title=title,
            company=company,
            jd_text=jd_text,
            resume_text=resume_text,
        )
    )
    
    return {
        "match_summary": analysis.split("\n")[-1],  # Last line = summary
        "strengths": [line for line in analysis.split("\n") if "strengths" in line.lower()],
        "gaps": [line for line in analysis.split("\n") if "gaps" in line.lower()],
        "cover_letter": cover_letter,
    }

def save_to_markdown(data: Dict, filename: str):
    """Save results to data/drafts/ as .md."""
    Path("data/drafts").mkdir(exist_ok=True)
    with open(f"data/drafts/{filename}.md", "w") as f:
        f.write(f"# Cover Letter for {data.get('company')}\n\n")
        f.write(f"**Role**: {data.get('title')}\n\n")
        f.write("## Match Summary\n")
        f.write(f"{data['match_summary']}\n\n")
        f.write("## Strengths\n")
        f.write("\n".join(f"- {s}" for s in data["strengths"]) + "\n\n")
        f.write("## Gaps\n")
        f.write("\n".join(f"- {g}" for g in data["gaps"]) + "\n\n")
        f.write("## Cover Letter\n")
        f.write(data["cover_letter"])