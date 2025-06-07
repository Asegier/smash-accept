from flask import Flask
from imap_tools import MailBox
import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta
import json
import smtplib
from email.mime.text import MIMEText

app = Flask(__name__)

EMAIL = os.getenv("EMAIL")
PASSWORD = os.getenv("EMAIL_PASSWORD")
SENDER = "no-reply@clubautomation.com"

if not EMAIL or not PASSWORD:
    raise ValueError("EMAIL or EMAIL_PASSWORD environment variables are missing")

CLICKED_IDS_FILE = "clicked_ids.json"

def load_clicked_ids():
    try:
        with open(CLICKED_IDS_FILE, "r") as f:
            return set(json.load(f))
    except FileNotFoundError:
        return set()

def save_clicked_ids(clicked_message_ids):
    with open(CLICKED_IDS_FILE, "w") as f:
        json.dump(list(clicked_message_ids), f)

clicked_message_ids = load_clicked_ids()

def send_notification(subject, body):
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = EMAIL
    msg["To"] = EMAIL  # Send to yourself

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL, PASSWORD)
            server.send_message(msg)
        print("Notification email sent.")
    except Exception as e:
        print(f"Failed to send notification email: {e}")

def check_email_and_click():
    now = datetime.now(timezone.utc)
    five_hours_ago = now - timedelta(hours=5)
    since_date = now.strftime('%d-%b-%Y')

    print(f"Checking emails from {SENDER} since {since_date} (last 5 hours filtered)...")

    try:
        with MailBox('imap.gmail.com').login(EMAIL, PASSWORD) as mailbox:
            for msg in mailbox.fetch(criteria=f'FROM {SENDER} SINCE {since_date}'):
                print(f"Processing email UID {msg.uid}, Subject: {msg.subject}, Date: {msg.date}")

                if msg.date < five_hours_ago:
                    print(f"Skipping email UID {msg.uid} because it's older than 5 hours.")
                    continue

                if msg.subject != "An Opening Has Become Available":
                    print(f"Skipping email UID {msg.uid} due to subject mismatch.")
                    continue

                if msg.uid in clicked_message_ids:
                    log_msg = f"Already processed email with UID {msg.uid}, subject '{msg.subject}'."
                    print(log_msg)
                    return log_msg

                html_content = msg.html or ""
                if not html_content:
                    print(f"No HTML content in email UID {msg.uid}. Skipping.")
                    continue

                soup = BeautifulSoup(html_content, "html.parser")
                accept_link = None
                for a_tag in soup.find_all("a"):
                    if a_tag.text.strip().lower() == "accept":
                        accept_link = a_tag.get("href")
                        break

                if accept_link:
                    print(f"Clicking Accept link for email UID {msg.uid}: {accept_link}")
                    try:
                        response = requests.get(accept_link, timeout=5)
                    except Exception as click_err:
                        error_msg = f"❌ Failed to click Accept link: {click_err}"
                        print(error_msg)
                        return error_msg

                    if response.status_code == 200:
                        clicked_message_ids.add(msg.uid)
                        save_clicked_ids(clicked_message_ids)

                        # Try to read response text
                        try:
                            page_soup = BeautifulSoup(response.text, "html.parser")
                            body_text = page_soup.get_text(separator="\n", strip=True)
                            body_text_preview = body_text[:500] + "..." if len(body_text) > 500 else body_text
                        except Exception as parse_err:
                            body_text_preview = f"(Could not parse page text: {parse_err})"

                        success_msg = (
                            f"✅ Clicked 'Accept' link for email UID {msg.uid}.\n"
                            f"Link: {accept_link}\n\n"
                            f"📄 Page text preview:\n{body_text_preview}"
                        )
                        print(success_msg)
                        send_notification("🏸 Badminton Spot Accepted", success_msg)
                        return success_msg
                    else:
                        error_msg = f"⚠️ Failed to click 'Accept' link for UID {msg.uid} (status code {response.status_code})."
                        print(error_msg)
                        return error_msg
                else:
                    print(f"No 'Accept' link found in email UID {msg.uid}.")
                    return "No 'Accept' link found in email."

        no_email_msg = f"No new emails from {SENDER} with subject 'An Opening Has Become Available' in the last 5 hours."
        print(no_email_msg)
        return no_email_msg

    except Exception as e:
        error_msg = f"❌ Error during email check: {e}"
        print(error_msg)
        return error_msg

@app.route("/")
def home():
    result_message = check_email_and_click()
    return f"<h2>{result_message}</h2>"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
