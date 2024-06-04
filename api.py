from typing import Union

from fastapi import FastAPI

app = FastAPI()

import os
import json
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime

# Function to check available credits
def check_credits(credentials):
    for credential in credentials:
        if credential['available_credits'] > 0:
            return credential
    return None

# Load queue from disk
def load_queue(queue_file):
    if os.path.exists(queue_file):
        with open(queue_file, 'r') as file:
            return json.load(file)
    return []

# Load done list from disk
def load_done_list(done_file):
    if os.path.exists(done_file):
        with open(done_file, 'r') as file:
            return json.load(file)
    return []

# Save done list to disk
def save_done_list(done_file, done_list):
    with open(done_file, 'w') as file:
        json.dump(done_list, file)

# Save queue to disk
def save_queue(queue_file, queue):
    with open(queue_file, 'w') as file:
        json.dump(queue, file)

# Send email with pictures
def send_email(smtp_server, port, login, password, from_addr, to_addr, subject, body, attachments):
    msg = MIMEMultipart()
    msg['From'] = from_addr
    msg['To'] = to_addr
    msg['Subject'] = subject

    for file_path in attachments:
        part = MIMEBase('application', 'octet-stream')
        with open(file_path, 'rb') as file:
            part.set_payload(file.read())
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename={os.path.basename(file_path)}')
        msg.attach(part)

    with smtplib.SMTP(smtp_server, port) as server:
        server.starttls()
        server.login(login, password)
        server.sendmail(from_addr, to_addr, msg.as_string())

# Archive pictures
def archive_pictures(pictures, archive_folder):
    if not os.path.exists(archive_folder):
        os.makedirs(archive_folder)
    for picture in pictures:
        os.rename(picture, os.path.join(archive_folder, os.path.basename(picture)))

def run_flow():
    credentials = [
        {'name': 'account1', 'available_credits': 10},
        {'name': 'account2', 'available_credits': 0},
    ]
    queue_file = 'queue.json'
    done_file = 'done.json'
    archive_folder = 'archive'

    # Step 1: Check credentials for available credits
    credential = check_credits(credentials)
    if not credential:
        print("No available credits")
        return

    # Step 3: Load queue from disk
    queue = load_queue(queue_file)

    # Step 4: Load done list
    done_list = load_done_list(done_file)

    # Step 5-9: Process queue
    for item in queue[:]:
        if item not in done_list:
            # Load pictures (Assuming item is a filename for simplicity)
            pictures = [item]

            # Send email
            try:
                send_email('smtp.example.com', 587, 'your_email@example.com', 'password',
                           'your_email@example.com', 'recipient@example.com',
                           'Subject Here', 'Email body here', pictures)

                # Archive pictures
                archive_pictures(pictures, archive_folder)

                # Update done list and queue
                done_list.append(item)
                queue.remove(item)
            except Exception as e:
                print(f"Failed to send email for {item}: {e}")

    # Save updated done list and queue
    save_done_list(done_file, done_list)
    save_queue(queue_file, queue)

@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/items/{item_id}")
def read_item(item_id: int, q: Union[str, None] = None):
    return {"item_id": item_id, "q": q}