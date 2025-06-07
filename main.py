from flask import Flask
from imap_tools import MailBox
import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta
import json
import time

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

def check_email_and_click():
    now = datetime.now(timezone.utc)
    five_hours_ago = now - timedelta(hours=5)
    since_date = now.strftime('%d-%b-%Y')

    print(f"Checking emails from {SENDER} since {since_date} (last 5 hours filtered)...")
    with MailBox('imap.gmail.com').login(EMAIL, PASSWORD) as mailbox:
        count_checked = 0
        for msg in mailbox.fetch(criteria=f'FROM {SENDER} SINCE {since_date}'):
            # Only check the latest 10 emails
            if count_checked >= 10:
                break
            count_checked += 1

            # Filter messages received within last 5 hours
            if msg.date < five_hours_ago:
                continue

            if msg.subject != "An Opening Has Become Available":
                continue

            if msg.uid in clicked_message_ids:
                print(f"Already processed email with subject: {msg.subject}, UID: {msg.uid}")
                return "already_processed"

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
                    response = requests.get(accept_link, timeout=5)
                    print("Clicked! Status code:", response.status_code)
                    clicked_message_ids.add(msg.uid)
                    save_clicked_ids(clicked_message_ids)
                    return "clicked"
                except Exception as e:
                    print("Error clicking link:", e)
                    return f"error_clicking_link: {e}"
            else:
                print("No 'Accept' link found in email.")
                return "no_accept_link"

    print("No new emails from Smash Champs.")
    return "no_emails"

@app.route("/")
def home():
    start = time.time()
    result = check_email_and_click()
    end = time.time()
    print(f"check_email_and_click took {end - start:.2f} seconds")

    if result == "clicked":
        return "<h2>Success! 'Accept' link clicked.</h2>"
    elif result == "already_processed":
        return "<h2>Email already processed.</h2>"
    elif result == "no_emails":
        return "<h2>No new emails from Smash Champs.</h2>"
    elif result == "no_accept_link":
        return "<h2>No 'Accept' link found in email.</h2>"
    else:
        return f"<h2>Error: {result}</h2>"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
