from flask import Flask
from imap_tools import MailBox
import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta
import json

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

def save_clicked_ids():
    with open(CLICKED_IDS_FILE, "w") as f:
        json.dump(list(clicked_message_ids), f)

clicked_message_ids = load_clicked_ids()

def check_email_and_click():
    now = datetime.now(timezone.utc)
    five_hours_ago = now - timedelta(hours=5)
    found_email = False
    already_processed = False

    print(f"Checking emails from {SENDER} since {five_hours_ago.isoformat()}")

    with MailBox('imap.gmail.com').login(EMAIL, PASSWORD) as mailbox:
        for msg in mailbox.fetch(criteria=f'FROM {SENDER}'):
            if msg.date < five_hours_ago:
                continue
            found_email = True
            if msg.subject != "An Opening Has Become Available":
                continue
            if msg.uid in clicked_message_ids:
                print(f"Already processed email with subject: {msg.subject}, UID: {msg.uid}")
                already_processed = True
                continue

            print(f"Found new email: {msg.subject}, UID: {msg.uid}")

            html_content = msg.html or ""
            if not html_content:
                print("No HTML content to parse, skipping.")
                continue

            soup = BeautifulSoup(html_content, "html.parser")
            accept_link = None
            for a_tag in soup.find_all("a"):
                if a_tag.text.strip().lower() == "accept":
                    accept_link = a_tag.get("href")
                    break

            if accept_link:
                print("Clicking Accept link:", accept_link)
                try:
                    response = requests.get(accept_link)
                    print("Clicked! Status code:", response.status_code)
                    clicked_message_ids.add(msg.uid)
                    save_clicked_ids()
                    return "clicked"
                except Exception as e:
                    print("Error clicking link:", e)
                    return f"error: {e}"

    if already_processed:
        return "already_processed"
    if not found_email:
        return "no_emails"
    return "no_accept_link"

@app.route("/")
def home():
    result = check_email_and_click()

    if result == "clicked":
        return "<h2>Success! 'Accept' link clicked.</h2>"
    elif result == "already_processed":
        return "<h2>No new emails, but one or more matching emails have already been processed.</h2>"
    elif result == "no_emails":
        return "<h2>No new emails from Smash Champs found in the last 5 hours.</h2>"
    elif result.startswith("error"):
        return f"<h2>Error occurred: {result[6:]}</h2>"
    else:
        return "<h2>No new 'Accept' links found in the emails.</h2>"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)