import json
import os
from datetime import datetime
from pathlib import Path

import streamlit as st
from cryptography.fernet import Fernet

from postcard_creator.postcard_creator import PostcardCreator, Token

ACCOUNTS_DIR = Path(os.getenv("ACCOUNTS_DIR"))

def on_access_token_received(access_token: dict, token: Token):
    w = PostcardCreator(token)

    user_info: dict = w.get_user_info()

    if user_info:
        filename = f"{user_info['firstName']}_{user_info['name']}"
        encrypt_and_store_token(token.to_json(), filename)
        st.success('Login successful and token saved.')
    else:
        st.error('Failed to get user info.')

def init_token():
    token = Token()
    token.add_access_token_listener(on_access_token_received)

    return token

def decrypt_token(file_path: Path) -> dict:
    key = os.getenv("ENC_KEY").encode()
    cipher_suite = Fernet(key)

    with open(file_path, 'rb') as token_file:
        cipher_text = token_file.read()
        plain_text = cipher_suite.decrypt(cipher_text)
        return json.loads(plain_text)

def encrypt_and_store_token(token: str, filename: str):
    key = os.getenv("ENC_KEY")
    cipher_suite = Fernet(key)
    cipher_text = cipher_suite.encrypt(json.dumps(token).encode())

    full_file_name = ACCOUNTS_DIR.joinpath(f'{filename}-token.json.enc')

    with open(full_file_name, 'wb') as token_file:
        token_file.write(cipher_text)

def list_tokens():
    return [f for f in ACCOUNTS_DIR.glob('*-token.json.enc')]


def maybe_refresh_token(token_data: dict):
    now = datetime.now().timestamp()
    fetched_at = token_data['fetched_at']
    expires_in = token_data['expires_in']
    token = init_token()

    # if fetched_at + expires_in < now:
    if True:
        refresh_token = token_data['refresh_token']
        token.fetch_token_by_refresh_token(refresh_token)
    else:
        token = init_token()

    return token


# List all saved tokens
st.header('Saved Tokens')
tokens = list_tokens()
token_names = [None] + [token.name for token in tokens]

selected_token = st.selectbox('Select a token to refresh', token_names)

if selected_token:
    token_file = ACCOUNTS_DIR.joinpath(selected_token)
    token_data = decrypt_token(token_file)
    token = maybe_refresh_token(token_data)

    w = PostcardCreator(token)
    st.write(w.get_quota())
    st.write(w.get_user_info())



st.title('Login App')

email = st.text_input('Email')
password = st.text_input('Password', type='password')

if st.button('Login'):
    token = init_token()

    access_token = token.fetch_token(username=email, password=password)