import asyncio
import json
import os
import random
import smtplib
import ssl
from datetime import datetime
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Dict

from dateutil import parser
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from postcard_creator import helper
from postcard_creator.enc_token_provider import EncTokenProvider
from postcard_creator.postcard_creator import Sender, Recipient, Postcard, PostcardCreator, \
    PostcardCreatorTokenInvalidException
from postcard_creator.token import NoopToken

load_dotenv()
app = FastAPI()


class NoAccountAvailableException(Exception):
    pass


class PostcardFlow:
    def __init__(self):
        self.mock_send = os.getenv("POSTCARD_MOCK", 'False').lower() in ('true', '1', 't')
        self.selected_account: PostcardCreator | None = None
        self.data_folder = Path(os.getenv("DATA_DIR"))
        self.image_folder = Path(os.getenv("POSTCARD_DIR"))
        self.accounts_folder = Path(os.getenv("ACCOUNTS_DIR"))

        self.done_file = self.data_folder.joinpath('done.json')
        self.archive_folder = self.image_folder.joinpath('archive')

        self.token_mngt = EncTokenProvider(self.accounts_folder)

    # Function to check available credits
    def check_credits(self, credentials) -> PostcardCreator | None:
        for credential in credentials:
            try:
                self.token_mngt.decrypt_token(credential)
                self.token_mngt.maybe_refresh_token()

                w: PostcardCreator = self.token_mngt.postcard_creator
                quota = w.get_quota()

                if quota['available']:
                    return w
            except PostcardCreatorTokenInvalidException as e:
                pass

        if self.mock_send:
            return PostcardCreator(NoopToken("1234"))

        return None

    def list_postcards(self):
        """List all image postcards in the postcards directory."""
        # List all image files, primarily focusing on common formats
        postcards = []
        covers = []
        text = []

        exclusions = [
            helper.is_text,
            helper.is_cover,
            helper.is_stamp,
        ]

        for file in self.image_folder.iterdir():
            if helper.is_cover(file):
                covers.append(file)
                continue

            if helper.is_text(file):
                text.append(file)
                continue

            # postcards.append(file)

        for text_file in text:
            origin = helper.filename_origin(text_file)
            if helper.filename_cover(origin).is_file():
                postcards.append(origin)

        return postcards

    def list_files_with_prefix(self, prefix):
        directory = self.image_folder
        matched_files = []

        # Walk through the directory
        for root, dirs, files in os.walk(directory):
            for file in files:
                if file.startswith(prefix):
                    matched_files.append(os.path.join(root, file))

        return matched_files

    # Load queue from disk
    def load_queue(self):
        return self.list_postcards()

    # Load done list from disk
    def load_done_list(self):
        if os.path.exists(self.done_file):
            with open(self.done_file, 'r') as file:
                return json.load(file)
        return []

    # Save done list to disk
    def save_done_list(self, done_list):
        with open(self.done_file, 'w') as file:
            json.dump(done_list, file)

    # Send email with pictures
    def send_email(self, smtp_server, port, login, password, from_addr, to_addr, subject, body: str, attachments,
                   order_id=None):
        msg = MIMEMultipart()
        msg['From'] = from_addr
        msg['To'] = to_addr
        msg['Subject'] = subject

        msg.attach(MIMEText(body, "plain"))

        for file_path in attachments:
            part = MIMEBase('application', 'octet-stream')
            with open(file_path, 'rb') as file:
                part.set_payload(file.read())
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f'attachment; filename={os.path.basename(file_path)}')
            msg.attach(part)

        context = ssl.create_default_context()

        with smtplib.SMTP_SSL(smtp_server, port, context=context) as server:
            server.login(login, password)
            server.sendmail(from_addr, to_addr, msg.as_string())

    # Archive pictures
    def archive_pictures(self, picture: Path, postcard_status: dict | bool = False):
        if not os.path.exists(self.archive_folder):
            os.makedirs(self.archive_folder)

        if isinstance(postcard_status, dict):
            new_stem = picture.stem + "_submit"
            status_file = picture.with_stem(new_stem).with_suffix(".json")
            with open(status_file, 'w') as file:
                json.dump(postcard_status, file)

        files = self.list_files_with_prefix(picture.stem)
        for picture in files:
            os.rename(picture, os.path.join(self.archive_folder, os.path.basename(picture)))

    def send_postcard(self, sender: Sender, recipient: Recipient, cover_file, message_image_file):
        card = Postcard(
            recipient=recipient,
            sender=sender,
            picture_stream=open(cover_file, 'rb'),
            message_image_stream=open(message_image_file, 'rb')
        )

        w = self.selected_account
        success = w.send_free_card(postcard=card, mock_send=self.mock_send, image_export=True)
        return success

    @staticmethod
    def build_recipient():
        recipient_prename = os.getenv('RECIPIENT_PRENAME')
        recipient_lastname = os.getenv('RECIPIENT_LASTNAME')
        recipient_street = os.getenv('RECIPIENT_STREET')
        recipient_place = os.getenv('RECIPIENT_PLACE')
        recipient_zip_code = os.getenv('RECIPIENT_ZIP_CODE')

        recipient = Recipient(
            prename=recipient_prename or None,
            lastname=recipient_lastname or None,
            street=recipient_street or None,
            place=recipient_place or None,
            zip_code=int(recipient_zip_code))

        return recipient

    def run_flow(self):

        # Step 1: Check credentials for available credits
        enc_tokens = self.token_mngt.list_tokens()
        credential = self.check_credits(enc_tokens)
        if not credential:
            print("No available credits")
            raise NoAccountAvailableException("No available credits")

        self.selected_account: PostcardCreator = credential

        # Step 3: Load queue from disk
        queue = self.load_queue()

        # Step 4: Load done list
        done_list = self.load_done_list()

        # Step 5-9: Process queue
        item = random.choice(queue)
        if item not in done_list:
            # Load pictures (Assuming item is a filename for simplicity)
            cover_file = helper.filename_cover(item)
            message_image_file = helper.filename_text(item)

            sender = self.build_sender()
            recipient = self.build_recipient()

            # Send email
            success = self.send_postcard(sender, recipient, cover_file, message_image_file)

            order_id = None
            if isinstance(success, dict) and "orderId" in success:
                order_id = success["orderId"]

            mail_text = self.make_mail_text(sender, recipient, order_id=order_id)

            try:
                self.send_email(os.getenv("SMTP_SERVER"),
                                int(os.getenv("SMTP_PORT")),
                                os.getenv("SMTP_LOGIN"),
                                os.getenv("SMTP_PASSWORD"),

                                os.getenv("MAIL_FROM_ADDR"),
                                os.getenv("MAIL_TO_ADDR"),
                                'Postcard <3',
                                mail_text,
                                attachments=[
                                    cover_file,
                                    message_image_file,
                                ])
            except Exception as e:
                print(f"Failed to send email for {item}: {e}")

            # Archive pictures
            self.archive_pictures(item, success)

            # Update done list and queue
            done_list.append(str(item))
            queue.remove(item)

        # Save updated done list and queue
        self.save_done_list(done_list)

    def build_sender(self):
        # TODO: Fetch from swisspost instance
        w = self.token_mngt.postcard_creator
        post_profile = w.get_user_info()
        return Sender(
            prename=post_profile["firstName"],
            lastname=post_profile["name"],
            street=post_profile["street"],
            place=post_profile["city"],
            zip_code=post_profile["zip"]
        )

    def make_mail_text(self, sender, recipient, order_id=None):
        import datetime
        now = datetime.datetime.now()

        return f"""
Datum: {now.strftime("%Y-%m-%d %H:%M:%S")}
Auftragsnummer: {order_id}
Absender:
{sender.prename} {sender.lastname}
{sender.street} 
{sender.zip_code} {sender.place}

Empfänger:
{recipient.prename} {recipient.lastname}
{recipient.street}
{recipient.zip_code} {recipient.place}
"""


# In-memory cache
cache: Dict[int, datetime] = {}
pc = PostcardFlow()

last_submission = None
last_run = None


# Background task to check dates in cache
async def check_dates():
    global cache, last_run, last_submission

    while True:
        now = datetime.now()  # Make it offset-aware in UTC

        for account_id, date in list(cache.items()):
            if date < now:
                try:
                    pc.run_flow()
                    last_submission = datetime.now()
                except Exception as e:
                    pass

                cache = make_cache()

        last_run = now
        await asyncio.sleep(60)  # Check every minute


def make_cache():
    enc_tokens = pc.token_mngt.list_tokens()
    mapping = {}
    for enc_token in enc_tokens:
        try:
            pc.token_mngt.decrypt_token(enc_token)
            pc.token_mngt.maybe_refresh_token()

            w: PostcardCreator = pc.token_mngt.postcard_creator
            quota = w.get_quota()
            next_date = parser.parse(quota['next'])
            mapping[enc_token] = next_date.replace(tzinfo=None)
        except Exception as e:
            pass

    return mapping


@app.on_event("startup")
async def startup_event():
    global run_task, cache
    # Populate the cache with some initial data
    cache = make_cache()

    # Start the background task
    run_task = asyncio.create_task(check_dates())


@app.exception_handler(NoAccountAvailableException)
async def no_account_available_exception_handler(request, exc: NoAccountAvailableException):
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc)},
    )


@app.get("/api/status")
def get_status():
    return {"last_run": last_run, "last_submission": last_submission, "cache": cache}


@app.get("/api/health")
def health():
    return "OK"
