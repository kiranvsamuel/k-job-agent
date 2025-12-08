from sqlalchemy.orm import declarative_base, relationship, Mapped, mapped_column 
from sqlalchemy import String, Text, DateTime, ForeignKey, JSON, func, Integer, Boolean 

Base = declarative_base()

class Company(Base):
    __tablename__ = "companies"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    website: Mapped[str | None] = mapped_column(String(512))
    ats_type: Mapped[str | None] = mapped_column(String(50))   # "greenhouse" | "lever"
    ats_slug: Mapped[str | None] = mapped_column(String(255))
    domain: Mapped[str | None] = mapped_column(String(255), index=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
    jobs = relationship("Job", back_populates="company")

class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    title: Mapped[str] = mapped_column(String(255), index=True)
    location: Mapped[str | None] = mapped_column(String(255))
    jd_text: Mapped[str] = mapped_column(Text)
    url: Mapped[str] = mapped_column(String(1024), unique=True)
    posted_at: Mapped[DateTime | None] = mapped_column(DateTime)
    source: Mapped[str] = mapped_column(String(50))  # "greenhouse" | "lever"
    raw_json: Mapped[dict] = mapped_column(JSON)
    contact_email:  Mapped[str] = mapped_column(String(255), index=True)
    applied_at: Mapped[DateTime | None] = mapped_column(DateTime, nullable=True)  # <-- new column
    company = relationship("Company", back_populates="jobs")

# Add this to your models.py file
class JobsApplied(Base):
    __tablename__ = "jobs_applied"  
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    applied_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
    job_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    job_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    response_received: Mapped[bool | None] = mapped_column(Boolean, default=False)
    cover_letter_sent: Mapped[str | None] = mapped_column(String(550), nullable=True)