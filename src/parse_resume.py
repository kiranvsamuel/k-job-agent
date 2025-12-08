import json
import sys
from dataclasses import dataclass
from typing import Set, Dict
from unidecode import unidecode
import fitz  # PyMuPDF

from .match.skills import CATALOG, SkillDef

@dataclass
class ResumeProfile:
    text: str
    skills: Dict[str, float]  # canonical skill -> weight (from catalog)

def extract_text_from_pdf(pdf_path: str) -> str:
    doc = fitz.open(pdf_path)
    chunks = []
    for page in doc:
        chunks.append(page.get_text())
    text = "\n".join(chunks)
    # normalize to improve regex hits (preserve punctuation for C++/C#)
    return unidecode(text)

def find_skills(text: str) -> Dict[str, float]:
    found = {}
   # print(CATALOG.items())
    for canonical, sdef in CATALOG.items():
        assert isinstance(sdef, SkillDef)
        for pat in sdef.patterns:
            if pat.search(text):
                found[canonical] = sdef.weight
                break
    return found

def build_profile(pdf_path: str) -> ResumeProfile:
    text = extract_text_from_pdf(pdf_path)
    #print(text)
    skills = find_skills(text)
    #print(skills)
    return ResumeProfile(text=text, skills=skills)

def main():
    if len(sys.argv) < 2:
        print("Usage: python -m src.parse_resume data/resumes/resume.pdf")
        sys.exit(1)
    pdf_path = sys.argv[1]
    #print(f"[resume] Parsing {pdf_path} ...")
    prof = build_profile(pdf_path)
    print(f"[resume] Extracted {len(prof.skills)} skills from {len(prof.text)} chars")
    out = {
        "skills": prof.skills,
        "char_count": len(prof.text),
    }
    # Save a compact JSON for the matcher
    out_path = "data/resume_profile.json"
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"[resume] Extracted {len(prof.skills)} skills -> {out_path}")
    for k in sorted(prof.skills, key=prof.skills.get, reverse=True):
        print(f"  - {k} ({prof.skills[k]})")

if __name__ == "__main__":
    main()
