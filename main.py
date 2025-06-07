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
    thirty_minutes_ago = now - timedelta(minutes=30)
    since_date = now.strftime('%d-%b-%Y')

    print(f"Checking emails from {SENDER} since {since_date} (last 30 mins filtered)...")
    with MailBox('imap.gmail.com').login(EMAIL, PASSWORD) as mailbox:
        for msg in mailbox.fetch(criteria=f'FROM {SENDER} SINCE {since_date}'):
            # Filter messages received within last 30 minutes
            if msg.date < thirty_minutes_ago:
                continue

            if msg.uid in clicked_message_ids:
                print(f"Already processed: {msg.subject}")
                continue

            print(f"Found new email: {msg.subject}")
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
                    return True  # Success: stop after first accepted link clicked
                except Exception as e:
                    print("Error clicking link:", e)
                    return False
            else:
                print("No 'Accept' link found in email.")
    return False

@app.route("/")
def home():
    clicked = check_email_and_click()
    if clicked:
        return "<h2>Success! 'Accept' link clicked.</h2>"
    else:
        return "<h2>No new 'Accept' links found or already processed.</h2>"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
