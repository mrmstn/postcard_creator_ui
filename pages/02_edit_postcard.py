import json
import os
from pathlib import PosixPath, Path

import pandas as pd
import streamlit as st
from PIL import Image
from dotenv import load_dotenv, dotenv_values
from openai import OpenAI
from pyarrow import ArrowTypeError
from streamlit_drawable_canvas import st_canvas

from postcard_creator import helper
from postcard_creator import postcard_img_util

# logging.getLogger('postcard_creator.postcard_creator').setLevel(logging.DEBUG)
load_dotenv()
config = dotenv_values(".env")


@st.cache_resource
def init_client():
    client = OpenAI(
        # This is the default and can be omitted
        api_key=os.environ.get("OPENAI_API_KEY"),
    )
    return client


def get_canvas_json(theme):
    chat_completion = client.chat.completions.create(
        messages=[
            {
                "role": "system",
                "content": "You are a highly specialized service tasked with generating Fabric.js JSON configurations tailored to user-provided themes."
                           " Your key responsibilities include:\n"
                           "- Placing each emoji in its own separate textbox, ensuring diverse styling for each to enhance visual interest.\n"
                           f"- Randomly positioning these textboxes within the fixed canvas dimensions of W:{text_canvas_w} H:{text_canvas_h}\n"
                           "- Utilizing appropriate emojis and decorative elements that visually align with the specified theme.\n"
                           "- Make the emojis big.\n"
                           "- Providing detailed specifications for each element on the canvas, including type, position, font size, and any other attributes necessary for effective rendering on a Fabric.js canvas.\n\n"
                           "The output should strictly be the JSON configuration, containing all necessary details for rendering the canvas effectively, with no additional text or explanations. No markdown, just the json string\n"
            },
            {
                "role": "user",
                "content": theme,
            }
        ],
        model="gpt-4o",
    )

    return chat_completion.choices[0].message.content


def ask_chatgpt():
    global initial_drawing
    st.title("Initial Canvas Generator")

    theme = st.text_input("Was soll automatisch gezeichnet werden? (Leer lassen für nichts ;))")

    if st.button("Generate Canvas"):
        if theme:
            try:
                json_output = get_canvas_json(theme)
                generated_struct = json.loads(json_output)
                initial_drawing = generated_struct
                # st.text_area("JSON Output:", json_output, height=300)
                with open(data_path, "w") as f:
                    json.dump(generated_struct, f)

                return draw_canvas()

            except Exception as e:
                st.error(f"Error in generating Canvas: {str(e)}")
        else:
            initial_drawing = {}
            st.warning("Starting with empty Canvas")
            return draw_canvas()

    return draw_canvas()


def draw_canvas():
    # Canvas Tool Selection
    tool_options = ["transform", "freedraw", "line", "text"]
    selected_tool = st.radio("Choose drawing tool:", tool_options)
    drawing_mode = selected_tool

    # Canvas settings
    stroke_width = st.slider("Stroke width: ", 1, 25, 3)
    stroke_color = st.color_picker("Stroke color hex: ")
    bg_color = st.color_picker("Background color hex: ", "#fff")
    realtime_update = st.checkbox("Update in realtime", True)

    # Displaying and updating the canvas
    return st_canvas(
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


client = init_client()
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

image_cover = postcard_img_util.make_cover_image(selected_postcard)
image_cover_path.write_bytes(image_cover)

st.image(str(image_cover_path))

canvas_result = None
if initial_drawing is None or len(initial_drawing['objects']) == 0:
    canvas_result = ask_chatgpt()
else:
    st.header("Zeichnen")
    canvas_result = draw_canvas()

if canvas_result:
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
