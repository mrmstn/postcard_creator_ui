import json
from pathlib import PosixPath, Path

import pandas as pd
import streamlit as st
from PIL import Image
from pyarrow import ArrowTypeError
from streamlit_drawable_canvas import st_canvas

from postcard_creator import postcard_img_util
from postcard_ui import helper

text_canvas_w = 720
text_canvas_h = 744

st.markdown("# Edit page 🎈")

if "selected_postcard" not in st.session_state:
    st.switch_page("pages/01_list_postcards.py")

selected_postcard: PosixPath = st.session_state.selected_postcard

data_path = helper.filename_data(selected_postcard)
image_message_path: Path = helper.filename_text(selected_postcard)
image_cover_path: Path = helper.filename_cover(selected_postcard)
initial_drawing = helper.maybe_load_data(data_path)
st.header("Vorderseite")

if not image_cover_path.is_file():
    image_cover = postcard_img_util.make_cover_image(selected_postcard)
    image_cover_path.write_bytes(image_cover)

st.image(str(image_cover_path))

st.header("Configuration")

# Canvas Tool Selection
tool_options = ["freedraw", "line", "rect", "circle", "transform", "polygon", "point", "text"]
selected_tool = st.radio("Choose drawing tool:", tool_options)
drawing_mode = selected_tool

# Canvas settings
stroke_width = st.slider("Stroke width: ", 1, 25, 3)
stroke_color = st.color_picker("Stroke color hex: ")
bg_color = st.color_picker("Background color hex: ", "#fff")
realtime_update = st.checkbox("Update in realtime", True)

# Displaying and updating the canvas
canvas_result = st_canvas(
    fill_color="rgba(255, 165, 0, 0.3)",
    stroke_width=stroke_width,
    stroke_color=stroke_color,
    initial_drawing=initial_drawing,
    background_color=bg_color,
    update_streamlit=realtime_update,
    height=text_canvas_h,
    width=text_canvas_w,
    drawing_mode=drawing_mode,
    key="full_app",
)

# Display the result
if canvas_result.image_data is not None:
    st.image(canvas_result.image_data)
if canvas_result.json_data is not None:
    objects = pd.json_normalize(canvas_result.json_data["objects"])
    try:
        st.dataframe(objects)
    except ArrowTypeError:
        pass

# Save and send functions
if st.button("Save"):
    with open(data_path, "w") as f:
        json.dump(canvas_result.json_data, f)
    st.success("Drawing data saved.")
    img = Image.fromarray(canvas_result.image_data.astype('uint8'), 'RGBA')
    img.convert("RGB").save(image_message_path, format="jpeg")
    st.success("Canvas saved as JPEG.")
