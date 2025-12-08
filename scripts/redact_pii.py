#!/usr/bin/env python3
"""
Redact specific personal PII across the repository.
This script replaces exact strings we found with safer placeholders.
Run from the repository root.
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Strings to replace -> placeholder
REPLACEMENTS = {
    # Names
    "<<REDACTED_NAME>>": "<<REDACTED_NAME>>",
    "<<REDACTED_NAME>>": "<<REDACTED_NAME>>",
    # Emails
    "<<REDACTED_EMAIL>>": "<<REDACTED_EMAIL>>",
    "<<REDACTED_EMAIL>>": "<<REDACTED_EMAIL>>",
    "<<REDACTED_EMAIL>>": "<<REDACTED_EMAIL>>",
    "<<REDACTED_EMAIL>>": "<<REDACTED_EMAIL>>",
    "<<REDACTED_EMAIL>>": "<<REDACTED_EMAIL>>",
    # Phone
    "<<REDACTED_PHONE>>": "<<REDACTED_PHONE>>",
    # LinkedIn / GitHub
    "<<REDACTED_LINKEDIN>>": "<<REDACTED_LINKEDIN>>",
    "<<REDACTED_GITHUB>>": "<<REDACTED_GITHUB>>",
    # Alternative email form (no dot)
    "<<REDACTED_EMAIL>> ": "<<REDACTED_EMAIL>>",
    # Variants used in prompts
    "<<REDACTED_EMAIL>> | phone: <<REDACTED_PHONE>>": "<<REDACTED_CONTACT_LINE>>",
}

FILE_EXT = {'.py', '.md', '.txt', '.yaml', '.yml', '.json', '.ini', '.cfg'}

changed_files = []

for path in ROOT.rglob('*'):
    # Skip .git and scripts folder if this script itself
    if any(part == '.git' for part in path.parts):
        continue
    if path.is_file() and path.suffix in FILE_EXT:
        try:
            text = path.read_text(encoding='utf-8')
        except Exception:
            continue
        new_text = text
        for old, new in REPLACEMENTS.items():
            if old in new_text:
                new_text = new_text.replace(old, new)
        if new_text != text:
            path.write_text(new_text, encoding='utf-8')
            changed_files.append(str(path.relative_to(ROOT)))

print("Redaction complete.")
if changed_files:
    print(f"Modified {len(changed_files)} files:")
    for f in changed_files:
        print(" - ", f)
else:
    print("No files modified.")
