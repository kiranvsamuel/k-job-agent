#!/usr/bin/env python3
"""
SMTP Connection Test - Diagnose why emails aren't sending
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

print("\n" + "="*60)
print("📧 SMTP CONNECTION TEST")
print("="*60)

# Get SMTP credentials from environment
smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
smtp_port = int(os.getenv("SMTP_PORT", 587))
smtp_user = os.getenv("SMTP_USER")
smtp_pass = os.getenv("SMTP_PASS")

print(f"\n✉️  Configuration:")
print(f"   Host: {smtp_host}")
print(f"   Port: {smtp_port}")
print(f"   User: {smtp_user}")
print(f"   Pass: {'*' * 10 if smtp_pass else 'NOT SET!'}")

if not smtp_user or not smtp_pass:
    print("\n❌ ERROR: SMTP_USER or SMTP_PASS not set in .env file!")
    exit(1)

# Test 1: Basic connection
print("\n" + "="*60)
print("TEST 1: Connecting to SMTP server...")
print("="*60)

try:
    print(f"   Connecting to {smtp_host}:{smtp_port}...")
    server = smtplib.SMTP(smtp_host, smtp_port, timeout=10)
    print("   ✅ Connected successfully")
    
    print("   Starting TLS...")
    server.starttls()
    print("   ✅ TLS started successfully")
    
    server.quit()
    print("   ✅ Connection test passed!")
    
except Exception as e:
    print(f"   ❌ Connection failed: {e}")
    print(f"   Error type: {type(e).__name__}")
    exit(1)

# Test 2: Authentication
print("\n" + "="*60)
print("TEST 2: Testing authentication...")
print("="*60)

try:
    server = smtplib.SMTP(smtp_host, smtp_port, timeout=10)
    server.starttls()
    
    print(f"   Logging in as {smtp_user}...")
    server.login(smtp_user, smtp_pass)
    print("   ✅ Authentication successful!")
    
    server.quit()
    
except smtplib.SMTPAuthenticationError as e:
    print(f"   ❌ Authentication failed!")
    print(f"   Error: {e}")
    print(f"\n   Possible reasons:")
    print(f"   1. Wrong username or password")
    print(f"   2. App Password expired (if using Gmail)")
    print(f"   3. 2FA not enabled (if using Gmail)")
    print(f"   4. 'Less secure app access' disabled")
    print(f"\n   For Gmail, generate a new App Password:")
    print(f"   https://myaccount.google.com/apppasswords")
    exit(1)
    
except Exception as e:
    print(f"   ❌ Authentication error: {e}")
    print(f"   Error type: {type(e).__name__}")
    exit(1)

# Test 3: Send a test email
print("\n" + "="*60)
print("TEST 3: Sending test email...")
print("="*60)

test_recipient = input("\n   Enter email to send test to (or press Enter to skip): ").strip()

if test_recipient:
    try:
        server = smtplib.SMTP(smtp_host, smtp_port, timeout=10)
        server.set_debuglevel(1)  # Enable debug output
        server.starttls()
        server.login(smtp_user, smtp_pass)
        
        # Create test message
        msg = MIMEText("This is a test email from k-job-agent SMTP diagnostic script.", "plain")
        msg["Subject"] = "SMTP Test - k-job-agent"
        msg["From"] = smtp_user
        msg["To"] = test_recipient
        
        print(f"\n   Sending test email to {test_recipient}...")
        server.sendmail(smtp_user, [test_recipient], msg.as_string())
        server.quit()
        
        print(f"\n   ✅ Test email sent successfully!")
        print(f"   Check {test_recipient} inbox")
        
    except Exception as e:
        print(f"\n   ❌ Failed to send test email: {e}")
        print(f"   Error type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        exit(1)
else:
    print("   ⏭️  Skipping test email")

# Test 4: Timeout test
print("\n" + "="*60)
print("TEST 4: Testing with longer timeout (30s)...")
print("="*60)

try:
    print("   This simulates your actual k_send_email function...")
    server = smtplib.SMTP(smtp_host, smtp_port, timeout=30)
    server.starttls()
    server.login(smtp_user, smtp_pass)
    server.quit()
    print("   ✅ Connection with 30s timeout successful!")
    
except Exception as e:
    print(f"   ❌ Timeout test failed: {e}")
    exit(1)

# Summary
print("\n" + "="*60)
print("✅ ALL TESTS PASSED!")
print("="*60)
print("\nYour SMTP configuration is working correctly.")
print("The issue might be:")
print("1. Network firewall blocking outgoing SMTP")
print("2. Rate limiting (too many emails sent recently)")
print("3. Recipient email addresses are invalid")
print("4. Python script hanging on something else")
print("\nTry running your k-run_submit script again.")
print("="*60 + "\n")