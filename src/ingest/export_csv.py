import csv
from . import run_ingest  # optional: ensure latest data
from ..db.db import SessionLocal
from ..db.models import Job, Company

def export(path="data/junior_jobs.csv"):
    s = SessionLocal()
    rows = (
        s.query(Job, Company)
        .join(Company, Company.id==Job.company_id)
        .order_by(Job.posted_at.desc().nullslast())
        .all()
    )
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["company","title","location","posted_at","url"])
        for j,c in rows:
            w.writerow([c.name, j.title, j.location, j.posted_at, j.url])
    s.close()

if __name__=="__main__":
    export()
