import os
from pathlib import PosixPath

import streamlit as st
from dotenv import dotenv_values

from postcard_creator import helper
from postcard_creator.postcard_creator import PostcardCreator, Postcard, Token, Recipient, Sender


@st.cache_resource
def init_token():
    config = dotenv_values(".env")
    token = Token()
    token.fetch_token(username=config['USERNAME'], password=config['PASSWORD'])
    token.has_valid_credentials(username=config['USERNAME'], password=config['PASSWORD'])
    return token


token = init_token()

st.markdown("# Send Postcard 🎈")

if "selected_postcard" not in st.session_state:
    st.switch_page("pages/01_list_postcards.py")

selected_postcard: PosixPath = st.session_state.selected_postcard

message_image_file = helper.filename_text(selected_postcard)
cover_file = helper.filename_cover(selected_postcard)

# Address Inputs for postcard
st.header("Address Information")
recipient_data = st.columns(2)
sender_data = st.columns(2)

# Define recipient and sender information input fields
with recipient_data:
    st.subheader("Recipient")
    # Retrieve each environment variable using os.getenv
    recipient_prename = st.text_input("Prename", os.getenv('RECIPIENT_PRENAME'), key="recipient_prename")
    recipient_lastname = st.text_input("Lastname", os.getenv('RECIPIENT_LASTNAME'), key="recipient_lastname")
    recipient_street = st.text_input("Street", os.getenv('RECIPIENT_STREET'), key="recipient_street")
    recipient_place = st.text_input("Place", os.getenv('RECIPIENT_PLACE'), key="recipient_place")
    recipient_zip_code = st.text_input("Zip Code", os.getenv('RECIPIENT_ZIP_CODE'), key="recipient_zip_code")

with sender_data:
    st.subheader("Sender")
    sender_prename = st.text_input("Prename", os.getenv('SENDER_PRENAME'), key="sender_prename")
    sender_lastname = st.text_input("Lastname", os.getenv('SENDER_LASTNAME'), key="sender_lastname")
    sender_street = st.text_input("Street", os.getenv('SENDER_STREET'), key="sender_street")
    sender_place = st.text_input("Place", os.getenv('SENDER_PLACE'), key="sender_place")
    sender_zip_code = st.text_input("Zip Code", os.getenv('SENDER_ZIP_CODE'), key="sender_zip_code")

if st.button("Send Postcard"):
    recipient = Recipient(
        prename=recipient_prename or None,
        lastname=recipient_lastname or None,
        street=recipient_street or None,
        place=recipient_place or None,
        zip_code=int(recipient_zip_code))
    sender = Sender(
        prename=sender_prename or None,
        lastname=sender_lastname or None,
        street=sender_street or None,
        place=sender_place or None,
        zip_code=int(sender_zip_code)
    )
    card = Postcard(
        recipient=recipient,
        sender=sender,
        picture_stream=open(cover_file, 'rb'),
        message_image_stream=open(message_image_file, 'rb')
    )

    w = PostcardCreator(token)
    success = w.send_free_card(postcard=card, mock_send=True, image_export=True)
    if success:
        st.success("Postcard sent successfully!")
    else:
        st.error("Failed to send postcard.")
