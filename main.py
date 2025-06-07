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

def save_clicked_ids(clicked_message_ids):
    with open(CLICKED_IDS_FILE, "w") as f:
        json.dump(list(clicked_message_ids), f)

clicked_message_ids = load_clicked_ids()

def check_email_and_click():
    now = datetime.now(timezone.utc)
    five_hours_ago = now - timedelta(hours=5)
    since_date = now.strftime('%d-%b-%Y')

    try:
        with MailBox('imap.gmail.com').login(EMAIL, PASSWORD) as mailbox:
            for msg in mailbox.fetch(criteria=f'FROM {SENDER} SINCE {since_date}'):
                if msg.date < five_hours_ago:
                    continue

                if msg.subject != "An Opening Has Become Available":
                    continue

                if msg.uid in clicked_message_ids:
                    return f"Checked email from {msg.from_} already and previously clicked Accept (UID: {msg.uid})"

                html_content = msg.html or ""
                if not html_content:
                    return "No HTML content to parse in the email."

                soup = BeautifulSoup(html_content, "html.parser")
                accept_link = None
                for a_tag in soup.find_all("a"):
                    if a_tag.text.strip().lower() == "accept":
                        accept_link = a_tag.get("href")
                        break

                if accept_link:
                    response = requests.get(accept_link, timeout=5)
                    if response.status_code == 200:
                        clicked_message_ids.add(msg.uid)
                        save_clicked_ids(clicked_message_ids)
                        return f"Clicked 'Accept' link successfully for email UID {msg.uid}."
                    else:
                        return f"Failed to click 'Accept' link (status code {response.status_code})."
                else:
                    return "No 'Accept' link found in email."

        return f"No new emails from {SENDER} with subject 'An Opening Has Become Available' in the last 5 hours."

    except Exception as e:
        return f"Error during email check: {e}"

@app.route("/")
def home():
    result_message = check_email_and_click()
    return f"<h2>{result_message}</h2>"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
