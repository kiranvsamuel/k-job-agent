from pathlib import Path
import click
import os 
import glob
import time 
from dotenv import load_dotenv
from ..db.db import SessionLocal
from src.db.models import Job, Company, JobsApplied
from src.submit.k_submit import submit_via_email_and_send_push_notification, parse_draft_parts, submit_via_greenhouse, submit_via_form, k_send_email, k_send_email_text
from datetime import datetime
from src.submit.k_pushover import push

#
#@click.command()
#@click.option("--resume-pdf", required=True, type=click.Path(exists=True))
#@click.option("--draft-dir", default="data/drafts")
#@click.option("--smtp-user", envvar="SMTP_USER")
#@click.option("--smtp-pass", envvar="SMTP_PASS")
#@click.option("--smtp-host", default="smtp.gmail.com")
#@click.option("--smtp-port", default=587)
load_dotenv()
@click.command()
@click.option( "--resume-pdf",required=True, type=click.Path(exists=True), envvar="RESUME_PDF",)# new -> pick from .env 
@click.option("--draft-dir", default=os.getenv("DRAFT_DIR", "data/drafts"),)  # .env fallback
@click.option( "--smtp-user", envvar="SMTP_USER",  required=True,)
@click.option("--smtp-pass", envvar="SMTP_PASS", required=True, )
@click.option( "--smtp-host", default=os.getenv("SMTP_HOST", "smtp.gmail.com"), )
@click.option( "--smtp-port", default=int(os.getenv("SMTP_PORT", 587)), )

def main(resume_pdf, draft_dir, smtp_user, smtp_pass, smtp_host, smtp_port):
    session = SessionLocal() 
    jobs = session.query(Job).filter(Job.applied_at == None).all()
    smtp_cfg = {"user": smtp_user, "password": smtp_pass, "host": smtp_host, "port": smtp_port}
    i = 0
    alljobs = ""
    for job in jobs:
        if(i==55):
            break  
        else:
            i += 1 
        pattern = f"{draft_dir}/{job.id}_*.md"
        matching_files = glob.glob(pattern)
        log_file_path = f"{draft_dir}/missing_drafts.log"
        is_file_missing = False

        # Skip this job if no draft file exists
        if not matching_files:
            print(f"{job.id} - {i} 🚫 Skipping {job.title} at {job.company.name} - no draft file found")
            alljobs += f"\n{i} - [skip] No draft file for {job.title} at {job.company.name}"
            # Write to log file
            with open(log_file_path, "a") as log_file:
                log_file.write(f"{job.id} - No draft file for {job.title} at {job.company.name} - Pattern: {pattern}\n")
            is_file_missing = True
            continue
            
        draft_file = os.path.basename(matching_files[0])
        path = os.path.join(draft_dir, draft_file)
        
        # Double-check the file exists (good practice)
        if not os.path.exists(path):
            print(f"{job.id} - 🚫 File not found: {path}")
            alljobs += f"\n{i} - [skip] Draft file not found: {draft_file}"
            # Write to log file
            with open(log_file_path, "a") as log_file:
                log_file.write(f"{job.id} - No draft file for {job.title} at {job.company.name} - Pattern: {pattern}\n")
            is_file_missing = True
            continue
        
        ### SEND EMAIL#################
        is_email_sent = False
        try:
            if not is_file_missing and job.contact_email:
                submit_via_email_and_send_push_notification(job, path, sender_email=smtp_user, smtp_config=smtp_cfg)
                is_email_sent=True
                # Add 5-second delay
                time.sleep(5)       
            else:
                alljobs += f"\n{i} - [skip] No contact email for {job.title} at {job.company.name}"
                # Write to log file
                with open(log_file_path, "a") as log_file:
                    log_file.write(f"{job.id} - No contact email for {job.title} at {job.company.name} - Pattern: {pattern}\n") 
                continue
        except Exception as e:
            alljobs += f"\n{i} - [error] Failed to submit {job.title}: {str(e)}"
            continue
        
        #if job.source == "greenhouse": 
        #    submit_via_greenhouse(job, path) #draft_md, resume_pdf)
        #else:
        #    submit_via_form(job, draft_md, resume_pdf)
        
        # Mark as applied
        if not is_file_missing and is_email_sent:
            from datetime import datetime, UTC
            job.applied_at = datetime.now(UTC)
            # Insert into jobs_applied table
            applied_job = JobsApplied(
                job_id=job.id,
                job_name=job.title,
                company_name=job.company.name,
                response_received=False,  # Default to False
                #cover_letter_sent="Email Sent to:" + job.contact_email + " Path: " + path #draft_md[:550]  # Store first 550 characters
                cover_letter_sent = f"Email Sent to: {job.contact_email or 'N/A'} Path: {path}"
            )

            session.add(applied_job)
            session.commit()
            session.refresh(applied_job) 

            print("-> ",applied_job.id, applied_job.job_name)
            print(f"\n Completed Applying Job # {i+1}\n----------------------------\n")
        else:
            continue

        
        # draft_md = f""" Subject: Interest in [Job Title] Role | Python Dev & Quick Learner
        #                 To: { job.contact_email }
        #                 Body:
        #                 Dear [{job.company.name} Talent Acquisition Team,

        #                 I am writing to express my strong interest in the [Job Title] position at [Company Name]. I was particularly drawn to this opportunity because of your team's focus on [mention a key aspect of the job, e.g., "maintaining data integrity and supporting critical sales systems" or "behind-the-scenes operations that power mission-driven teams"].

        #                 While many candidates with my level of experience have academic projects, I have already taken the initiative to build and deploy real-world applications. For instance, I single-handedly developed a Heart Disease Prediction app, taking it from a concept to a live tool by engineering the machine learning model, building the API, and creating an interactive front-end. This hands-on experience has given me a practical understanding of the full development lifecycle that I am eager to apply to the challenges your team is solving.

        #                 What I can bring:
        #                 * Proven Technical Foundation: This experience, along with projects like my full-stack application CloudatHand, has given me a hands-on understanding of data systems, APIs, and the end-to-end development lifecycle.
        #                 * Detail-Oriented & Efficient: I am proficient in using modern AI-assisted tools (like Cursor and GitHub Copilot) to enhance accuracy, troubleshoot issues, and accelerate my workflow.
        #                 * A Quick Learner, Eager to Contribute: I am excited by the prospect of diving into your specific tech stack and contributing to your team's mission.

        #                 My resume is attached for your detail. You can see the code and results of my projects directly on my GitHub: <<REDACTED_GITHUB>>

        #                 I am very keen to learn more about the [Job Title] role and am also open to any other junior developer or systems support positions where my skills could be a good fit for [Company Name]'s needs.

        #                 Thank you for your time and consideration.

        #                 Sincerely,
        #                 {os.getenv("K_NAME", "")}
        #                 {os.getenv("K_PHONE","")} | {os.getenv("K_EMAIL","")}   
        #                 LinkedIn: {os.getenv("K_LINKEDIN","")} 
        #                 GitHub: {os.getenv("K_GITHUB")} """
       
    #test_email(alljobs, sender_email=smtp_user, smtp_config=smtp_cfg)
    #smtp_cfg = {"user": smtp_user, "password": smtp_pass, "host": smtp_host, "port": smtp_port}
    # test_smtp_config = {
    #     "host": smtp_host, #"smtp.gmail.com",
    #     "port": smtp_port,# 587,
    #     "user": smtp_user,
    #     "password": smtp_pass
    #     }

    # k_send_email_text(
    #     email_subject="Test - NO PDF",
    #     email_body="This is a test email body -- " + alljobs,
    #     to_emails="<<REDACTED_EMAIL>>,<<REDACTED_EMAIL>>,<<REDACTED_EMAIL>>",
    #     sender_email=smtp_user,
    #     smtp_config=test_smtp_config
    # )

    # k_send_email(
    #     email_subject="Test - with PDF",
    #     email_body="This is a test email body with PDF attachment -- ", # + alljobs,
    #     to_emails="<<REDACTED_EMAIL>>,<<REDACTED_EMAIL>>,<<REDACTED_EMAIL>>",
    #     sender_email=smtp_user,
    #     smtp_config=test_smtp_config,
    #     pdf_path="./data/resumes/resume.pdf"  # Add the PDF file path here
    # )

    # def submit_via_email_(job, draft_md_path, sender_email, smtp_config):
    #     """
    #     Send the parsed draft cover letter as an email.
    #     """
    #     print("#######49#####")
    #     draft_path = Path(draft_md_path)
    #     print("\n#######51#####")
    #     email_body = parse_draft_md(draft_path)
    #     print("\n#######53#####")
        
    #     msg = MIMEText(email_body, "plain")
    #     print("\n#######56#####")
        
    #     msg["Subject"] = f"Application for {job.title}"
    #     msg["From"] = sender_email
    #     msg["To"] = "<<REDACTED_EMAIL>>" #job.contact_email
    #     print(f"\nsubmit_via_email ===========> Sending email to: {job.contact_email}")
    #     print("\n#######ERROR ##### TBD \n")
    #     with smtplib.SMTP(smtp_config["host"], smtp_config["port"]) as server:
    #         server.starttls()
    #         server.login(smtp_config["user"], smtp_config["password"])
    #         server.sendmail(sender_email, [job.contact_email], msg.as_string())

    #     print(f"[submit] Email sent -> {job.contact_email}")



if __name__ == "__main__":
    main()

###########################
#Cron job (Linux/macOS)

# run every day at 8 AM:
#command:
#   0 8 * * * /path/to/your/venv/bin/python -m src.submit.k-run_submit >> /path/to/logs/run_submit.log 2>&1

#Make sure to activate the virtual environment. Use absolute paths for Python, virtual environment, and project files.
############################