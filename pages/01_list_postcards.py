import os
from pathlib import Path

import streamlit as st

from postcard_creator import helper
from postcard_creator.helper import list_complete_postcards

POSTCARD_DIR = Path(os.getenv("POSTCARD_DIR"))
ALLOWED_EXTENSIONS = ['.png', '.jpg', '.jpeg', '.gif']


def select_postcard():
    """Display a gallery of postcards for selection and allow file upload."""
    st.header("Upload New Postcard")
    uploaded_file = st.file_uploader("Choose a file", type=ALLOWED_EXTENSIONS)
    if uploaded_file is not None:
        file_path = POSTCARD_DIR.joinpath(uploaded_file.name)
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getvalue())
        st.success("Uploaded successfully!")

    st.header("Current Statistics")
    complete_postcards = list_complete_postcards(POSTCARD_DIR)

    archive_folder = POSTCARD_DIR.joinpath('archive')
    sent_postcards = list_complete_postcards(archive_folder)

    st.write(f"Versandbereit: {len(complete_postcards)}")
    st.write(f"Versendet: {len(sent_postcards)}")
    st.write(f"Ziel: 60")

    st.header("Postcard Gallery")
    postcards = list_postcards()
    if not postcards:
        st.write("No postcards available.")
        return

    # Display each postcard horizontally
    for postcard in postcards:
        # Create a row for each postcard
        with st.container():
            cols = st.columns([2, 2, 1])  # Adjust ratio based on your preference for spacing

            cols[0].image(str(postcard), use_column_width=True)

            # Check for message image
            image_message = helper.filename_text(postcard)
            if image_message.is_file():
                cols[1].image(str(image_message), use_column_width=True)

            # Button to select the postcard
            if cols[2].button(f"Bearbeiten", key=postcard.name):
                st.session_state.selected_postcard = postcard
                st.switch_page("pages/02_edit_postcard.py")


def list_postcards():
    """List all image postcards in the postcards directory."""
    # List all image files, primarily focusing on common formats
    postcards = []
    exclusions = [
        helper.is_text,
        helper.is_cover,
        helper.is_stamp,
    ]

    for file in POSTCARD_DIR.iterdir():
        if file.suffix.lower() not in ALLOWED_EXTENSIONS:
            continue

        if helper.is_generated_image(file):
            continue

        postcards.append(file)

    return postcards


select_postcard()
