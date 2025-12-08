import argparse
import datetime as dt
import json
from typing import Dict, List, Tuple

from ..db.db import SessionLocal
from ..db.models import Job, Company
from .skills import CATALOG, JR_POS_RX, SENIOR_NEG_RX, REMOTE_RX

NOW = dt.datetime.utcnow()

def _find_skills_in_text(text: str) -> Dict[str, float]:
    # same logic as parse_resume, but inlined to avoid a circular import
    found = {}
    for canonical, sdef in CATALOG.items():
        for pat in sdef.patterns:
            if pat.search(text or ""):
                found[canonical] = sdef.weight
                break
    return found

def _recency_bonus(posted_at) -> float:
    """0..3 bonus. 3 if posted today, decays to ~0 by 90 days."""
    if not posted_at:
        return 0.0
    days = max(0, (NOW - posted_at).days)
    return max(0.0, (90 - days) / 90.0) * 3.0

def score_job(resume_skills: Dict[str, float], job: Job) -> Tuple[float, Dict]:
    jd = job.jd_text or ""
    title = job.title or ""
    loc = (job.location or "") + "\n" + jd

    job_skills = _find_skills_in_text(jd)
    overlap = set(resume_skills).intersection(job_skills)

    skill_score = sum(CATALOG[k].weight for k in overlap)

    title_boost = 3.0 if JR_POS_RX.search(title) else 0.0
    senior_penalty = -4.0 if SENIOR_NEG_RX.search(title) else 0.0
    remote_boost = 1.5 if REMOTE_RX.search(loc) else 0.0
    recency = _recency_bonus(job.posted_at)

    total = skill_score + title_boost + remote_boost + senior_penalty + recency

    detail = {
        "overlap": sorted(list(overlap), key=lambda k: CATALOG[k].weight, reverse=True),
        "skill_score": round(skill_score, 2),
        "title_boost": title_boost,
        "remote_boost": remote_boost,
        "senior_penalty": senior_penalty,
        "recency_bonus": round(recency, 2),
        "posted_at": job.posted_at.isoformat() if job.posted_at else None,
    }
    return total, detail

def main():
    ap = argparse.ArgumentParser(description="Rank jobs against your resume skills.")
    ap.add_argument("--top", type=int, default=20, help="How many to display")
    ap.add_argument("--dump-csv", type=str, default="", help="Optional: path to export CSV")
    ap.add_argument("--resume-profile", type=str, default="data/resume_profile.json")
    args = ap.parse_args()

    # Load resume profile
    with open(args.resume_profile) as f:
        profile = json.load(f)
    resume_skills = {k: float(v) for k, v in profile.get("skills", {}).items()}

    s = SessionLocal()
    rows = (
        s.query(Job, Company)
        .join(Company, Company.id == Job.company_id)
        .all()
    )
    scored = []
    for job, comp in rows:
        score, detail = score_job(resume_skills, job)
        scored.append({
            "score": round(score, 2),
            "company": comp.name,
            "title": job.title,
            "location": job.location,
            "url": job.url,
            "posted_at": job.posted_at.isoformat() if job.posted_at else "",
            "overlap": ", ".join(detail["overlap"]),
            "detail": detail,
        })
    s.close()

    scored.sort(key=lambda r: r["score"], reverse=True)
    topn = scored[: args.top]

    # Pretty print table
    print(f"\nTop {len(topn)} matches:")
    print("-" * 100)
    for i, r in enumerate(topn, 1):
        print(f"{i:2d}. [{r['score']:>5}] {r['company']} — {r['title']} ({r['location'] or 'N/A'})")
        print(f"     Posted: {r['posted_at'] or 'unknown'}  Overlap: {r['overlap']}")
        print(f"     URL: {r['url']}")
    print("-" * 100)

    if args.dump_csv:
        import csv
        with open(args.dump_csv, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["score","company","title","location","posted_at","overlap","url"])
            for r in scored:
                w.writerow([r["score"], r["company"], r["title"], r["location"], r["posted_at"], r["overlap"], r["url"]])
        print(f"CSV saved -> {args.dump_csv}")

if __name__ == "__main__":
    main()
