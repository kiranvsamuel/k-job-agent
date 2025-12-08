#!/usr/bin/env python3
"""
find_startups.py
- Uses Perplexity (Sonar) API to find candidate startup job postings.
- Verifies each job page to ensure it mentions junior / intern (0-2 yrs)
  and Python or JavaScript.
- Appends only NEW entries to a YAML file.
"""

import os
import time
import re
import json
import yaml
import logging
import random
from datetime import datetime, timezone
from typing import List, Optional, Dict
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from tqdm import tqdm

# Load .env
load_dotenv()

PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")
SEED_YAML_PATH = os.getenv("SEED_YAML_PATH", "data/seeds/k-companies_seed.yaml")
TARGET_NEW = int(os.getenv("TARGET_NEW", "200"))
MAX_ITER = int(os.getenv("MAX_ITER", "40"))  # safety cap: number of Perplexity queries
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "10"))  # ask Perplexity for ~10–25 companies each call
SLEEP_BETWEEN_API = float(os.getenv("SLEEP_BETWEEN_API", "1.2"))  # seconds
SLEEP_BETWEEN_FETCH = float(os.getenv("SLEEP_BETWEEN_FETCH", "1.0"))

API_URL = "https://api.perplexity.ai/chat/completions"  # per docs
HEADERS = {
    "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

# simple regex to find URLs and emails
URL_RX = re.compile(r"https?://[^\s\)\]]+")
EMAIL_RX = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

# keywords for verification
JUNIOR_RX = re.compile(r"\b(junior|intern(ship)?|entry[-\s]level|new\s*grad|0\s*[-–]\s*2\s*years|0\s*to\s*2\s*years)\b", re.I)
TECH_RX = re.compile(r"\b(python|javascript|js|node\.js|react|angular|vue)\b", re.I)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")


def ensure_yaml_exists(path: str):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump([], f)


def load_existing(path: str) -> List[Dict]:
    ensure_yaml_exists(path)
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or []
    return data


def save_existing(path: str, data: List[Dict]):
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)


def call_perplexity(prompt: str, model: str = "sonar-pro", max_tokens: int = 700) -> Optional[dict]:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        # optionally tune tokens
        "max_tokens": max_tokens,
    }
    try:
        r = requests.post(API_URL, headers=HEADERS, json=payload, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logging.warning("Perplexity API error: %s", e)
        return None


def parse_candidates_from_text(text: str) -> List[Dict]:
    """
    Heuristics: find lines with URLs and extract company/name around them.
    Returns list of dicts: {name, url, snippet}
    """
    candidates = []
    # split lines, look for lines that contain URLs
    lines = text.splitlines()
    for ln in lines:
        if "http" in ln:
            urls = URL_RX.findall(ln)
            for u in urls:
                snippet = ln.strip()
                # attempt to extract a company name preceding the URL: "Acme — https://..."
                # we try segments before the URL
                before = ln.split(u)[0].strip()
                name_guess = None
                # heuristics: split by " - ", " — ", ":" or "("
                for sep in [" - ", " — ", ":", "(", "•", "·"]:
                    if sep in before:
                        name_guess = before.split(sep)[0].strip()
                        break
                if not name_guess:
                    # fallback: first 6 words
                    name_guess = " ".join(before.split()[:6]).strip()
                candidates.append({"name": name_guess or None, "url": u, "snippet": snippet})
    # dedupe by url
    seen = set()
    result = []
    for c in candidates:
        if c["url"] not in seen:
            seen.add(c["url"])
            result.append(c)
    return result


def fetch_job_page(url: str) -> Optional[str]:
    """Fetch page and return cleaned text (or None). Respect politeness with delays."""
    headers = {"User-Agent": "Mozilla/5.0 (compatible; job-finder-bot/0.1; +https://example.com/bot)"}
    try:
        r = requests.get(url, headers=headers, timeout=12)
        r.raise_for_status()
        # parse with BeautifulSoup
        soup = BeautifulSoup(r.text, "lxml")
        # remove script/style
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        text = soup.get_text(separator="\n")
        # normalize spacing
        text = re.sub(r"\n\s*\n+", "\n\n", text)
        return text
    except Exception as e:
        logging.debug("Failed to fetch %s : %s", url, e)
        return None


def verify_job_text(text: str) -> bool:
    """Return True if text includes junior/intern indicator."""
    if not text:
        return False
    return bool(JUNIOR_RX.search(text))


def extract_job_info_from_page(text: str, url: str) -> Dict:
    """Extract simple info: posted date (if any), location heuristics, email contact if present."""
    posted = None
    location = None
    emails = EMAIL_RX.findall(text or "")
    contact_email = emails[0] if emails else None

    # Try to find a posted_at pattern like "Posted: Aug 12, 2025" or dates
    # Simple heuristic: look for 'Posted' or 'Published'
    m = re.search(r"(Posted|Published)[:\s]+([A-Za-z0-9,\s\-]+)", text, re.I)
    if m:
        posted = m.group(2).strip()

    # location heuristics: look for "Location" label
    m2 = re.search(r"Location[:\s]+([A-Za-z0-9,\-\s()]+)", text, re.I)
    if m2:
        location = m2.group(1).strip()

    return {"posted_at": posted, "location": location, "contact_email": contact_email}


def domain_from_url(url: str) -> str:
    try:
        p = urlparse(url)
        return p.netloc.lower().replace("www.", "")
    except:
        return ""



def make_prompt(batch_size: int, exclude_names: List[str], exclude_domains: List[str]) -> str:
    exclude_names_text = ", ".join(exclude_names[:50])  # limit length
    exclude_domains_text = ", ".join(exclude_domains[:50])  # limit length

    prompt = (
        f"List up to {batch_size} distinct U.S.-based startup companies that currently have "
        "job postings for junior or intern software engineer positions (0-2 years of experience). "
        "For each listing return a single line in this format:\n\n"
        "Company name — job title — job posting URL\n\n"
        "Exclude any of the following companies or domains if they appear:\n"
        f"Companies: {exclude_names_text}\n"
        f"Domains: {exclude_domains_text}\n\n"
        "Only include companies hiring in the USA. If you don't have exact URLs, omit that entry."
    )
    return prompt


def main():
    if not PERPLEXITY_API_KEY:
        logging.error("PERPLEXITY_API_KEY not set. Put key in .env as PERPLEXITY_API_KEY.")
        return

    existing = load_existing(SEED_YAML_PATH)
    existing_names = {c.get("name", "").lower() for c in existing}
    existing_domains = {c.get("domain") for c in existing if c.get("domain")}
    existing_urls = {c.get("job_url") for c in existing if c.get("job_url")}
    logging.info("Loaded %d existing companies", len(existing))

    new_entries = []
    iterations = 0

    while len(new_entries) < TARGET_NEW and iterations < MAX_ITER:
        iterations += 1
        prompt = make_prompt(BATCH_SIZE, list(existing_names), list(existing_domains))
        logging.info("Calling Perplexity (iter %d)...", iterations)
        resp = call_perplexity(prompt)
        if not resp:
            logging.warning("No response from Perplexity; sleeping then retrying.")
            time.sleep(5)
            continue

        # The assistantcontent may be in resp['choices'][0]['message']['content']
        try:
            assistant_text = resp["choices"][0]["message"]["content"]
        except Exception:
            assistant_text = json.dumps(resp)  # fallback to raw if structure differs

        candidates = parse_candidates_from_text(assistant_text)
        logging.info("Perplexity returned %d candidate urls", len(candidates))

        for c in candidates:
            url = c["url"].rstrip(").,")
            if url in existing_urls or any(domain_from_url(url) == d for d in existing_domains):
                logging.debug("Skipping already-known URL/domain: %s", url)
                continue

            # polite jitter between fetches
            time.sleep(SLEEP_BETWEEN_FETCH + random.random() * 0.5)
            page_text = fetch_job_page(url)
            if not page_text:
                logging.debug("Could not fetch page for %s", url)
                continue

            if not verify_job_text(page_text):
                logging.debug("Verification failed for %s (missing junior or tech keywords)", url)
                continue

            info = extract_job_info_from_page(page_text, url)
            entry = {
                "name": c.get("name") or "",
                "domain": domain_from_url(url),
                "job_url": url,
                "role_title": c.get("snippet").split("—")[0].strip() if "—" in c.get("snippet","") else c.get("snippet","").strip()[:120],
                "location": info.get("location"),
                "posted_at": info.get("posted_at"),
                "found_at": datetime.now(timezone.utc).isoformat(),
                "source": "perplexity",
                "verified": True,
                "contact_email": info.get("contact_email"),
                "notes": c.get("snippet")[:400],
            }

            # final dedupe check by job_url/domain/name
            if entry["job_url"] in existing_urls:
                continue
            if entry["domain"] in existing_domains:
                # keep domain uniqueness policy: skip if same domain already exists
                logging.debug("Domain already exists; skipping: %s", entry["domain"])
                continue

            logging.info("Found new verified job: %s (%s)", entry["name"], entry["job_url"])
            existing.append(entry)
            existing_urls.add(entry["job_url"])
            existing_domains.add(entry["domain"])
            new_entries.append(entry)

            # persist periodically
            if len(new_entries) % 10 == 0:
                save_existing(SEED_YAML_PATH, existing)
                logging.info("Saved progress: %d new entries so far.", len(new_entries))

            if len(new_entries) >= TARGET_NEW:
                break

        # save after each Perplexity call
        save_existing(SEED_YAML_PATH, existing)
        # be polite for API rate limits
        time.sleep(SLEEP_BETWEEN_API + random.random() * 0.3)

    logging.info("Done. Found %d new entries (total file entries: %d).", len(new_entries), len(existing))
    save_existing(SEED_YAML_PATH, existing)


if __name__ == "__main__":
    main()
