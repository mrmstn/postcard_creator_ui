import json
import os
from datetime import datetime
from pathlib import Path

from cryptography.fernet import Fernet

from postcard_creator.postcard_creator import PostcardCreator
from postcard_creator.token import Token


class EncTokenProvider:
    def __init__(self, accounts_location: Path):
        self.ACCOUNTS_DIR = accounts_location
        self.token: Token = Token()
        self.postcard_creator: PostcardCreator = None

    def list_tokens(self):
        return [f for f in self.ACCOUNTS_DIR.glob('*-token.json.enc')]

    def on_access_token_received(self, access_token: dict, token: Token):
        self.token = token
        self.postcard_creator = PostcardCreator(self.token)

        user_info: dict = self.postcard_creator.get_user_info()

        if user_info:
            filename = f"{user_info['firstName']}_{user_info['name']}"
            self.encrypt_and_store_token(token.to_json(), filename)
            return True
        else:
            return False

    def decrypt_token(self, file_path: Path):
        key = os.getenv("ENC_KEY").encode()
        cipher_suite = Fernet(key)

        with open(file_path, 'rb') as token_file:
            cipher_text = token_file.read()
            plain_text = cipher_suite.decrypt(cipher_text)
            self.token_data = json.loads(plain_text)

    def encrypt_and_store_token(self, token: str, filename: str):
        key = os.getenv("ENC_KEY")
        cipher_suite = Fernet(key)
        cipher_text = cipher_suite.encrypt(json.dumps(token).encode())

        full_file_name = self.ACCOUNTS_DIR.joinpath(f'{filename}-token.json.enc')

        with open(full_file_name, 'wb') as token_file:
            token_file.write(cipher_text)

    def maybe_refresh_token(self):
        now = datetime.now().timestamp()
        fetched_at = self.token_data['fetched_at']
        expires_in = self.token_data['expires_in']

        # if fetched_at + expires_in < now:
        if True:
            refresh_token = self.token_data['refresh_token']
            self.token.fetch_token_by_refresh_token(refresh_token, self.on_access_token_received)

    def authenticate_username_password(self, username, password):
        self.token.authenticate_username_password(username, password)

    def finish_auth(self):
        self.token.finish_auth(self.on_access_token_received)
