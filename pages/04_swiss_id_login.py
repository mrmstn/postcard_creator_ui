import os
from pathlib import Path

import streamlit as st

from postcard_creator.enc_token_provider import EncTokenProvider

ACCOUNTS_DIR = Path(os.getenv("ACCOUNTS_DIR"))


def get_token_manager() -> EncTokenProvider:
    token_mngr = EncTokenProvider(ACCOUNTS_DIR)

    if "token" in st.session_state:
        token_mngr.token = st.session_state.token

    return token_mngr


# List all saved tokens
st.header('Saved Tokens')

token_mngt = get_token_manager()
tokens = token_mngt.list_tokens()
token_names = [None] + [token.name for token in tokens]

selected_token = st.selectbox('Select a token to refresh', token_names)

if selected_token:
    token_file = ACCOUNTS_DIR.joinpath(selected_token)
    token_mngt.decrypt_token(token_file)
    token_mngt.maybe_refresh_token()

    w = token_mngt.postcard_creator
    st.write(w.get_quota())
    st.write(w.get_user_info())

st.title('Login App')

email = st.text_input('Email')
password = st.text_input('Password', type='password')

if "requires_two_fa" not in st.session_state:
    st.session_state.requires_two_fa = False

token_mngr = get_token_manager()
if st.button('Login'):
    token = token_mngr.token
    st.session_state.token = token_mngr.token
    # Do first step
    token_mngr.authenticate_username_password(username=email, password=password)

    finalize = False
    # Check if 2Fa is necessary
    if token.next_action != token.AUTHENTICATE_MTAN:
        st.session_state.requires_two_fa = False
        token_mngr.finish_auth()
        st.success('Login successful')
    else:
        st.session_state.requires_two_fa = True

if st.session_state.requires_two_fa or False:
    two_fa_token = st.text_input('SMS Code')
    # Do two fa step
    if st.button('2FA Login', key="two_fa_login"):
        session = token_mngr.token.authenticate_mtan(two_fa_token)
        token_mngr.finish_auth()
        st.success('Login successful')
