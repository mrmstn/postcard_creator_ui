import io
import os
import textwrap
from math import floor
from time import strftime, gmtime

import pkg_resources
from PIL import Image, ImageFilter, ImageOps, ImageDraw, ImageFont

from postcard_creator.postcard_creator import logger, _get_trace_postcard_sent_dir


def make_cover_image(file, **kwargs) -> Image:
    kwargs['image_target_width'] = 1819
    kwargs['image_quality_factor'] = 1
    kwargs['image_target_height'] = 1311
    kwargs['img_format'] = 'jpeg'
    kwargs['enforce_size'] = True
    return rotate_and_scale_image(file, **kwargs)


def rotate_and_scale_image(file, image_target_width=154,
                           image_target_height=111,
                           image_quality_factor=20,
                           image_rotate=True,
                           image_export=False,
                           enforce_size=False,
                           # = True, will not make image smaller than given w/h, for high resolution submissions
                           fallback_color_fill=False,  # = False, will force resize cover even if image is too small.
                           img_format='PNG',
                           **kwargs):
    with Image.open(file) as image:
        if image_rotate and image.width < image.height:
            image = image.rotate(90, expand=True)
            logger.debug('rotating image by 90 degrees')

        if not enforce_size and \
                (image.width < image_quality_factor * image_target_width
                 or image.height < image_quality_factor * image_target_height):
            factor_width = image.width / image_target_width
            factor_height = image.height / image_target_height

            factor = min([factor_height, factor_width])

            logger.debug('image is smaller than default for resize/fill. '
                         'using scale factor {} instead of {}'.format(factor, image_quality_factor))
            image_quality_factor = factor

        width = image_target_width * image_quality_factor
        height = image_target_height * image_quality_factor
        logger.debug('resizing image from {}x{} to {}x{}'
                     .format(image.width, image.height, width, height))

        cover = process_image(image, image_target_width, image_target_height)

        cover = cover.convert("RGB")
        with io.BytesIO() as f:
            cover.save(f, img_format)
            scaled = f.getvalue()

        if image_export:
            name = strftime("postcard_creator_export_%Y-%m-%d_%H-%M-%S_cover.jpg", gmtime())
            path = os.path.join(_get_trace_postcard_sent_dir(), name)
            logger.info('exporting image to {} (image_export=True)'.format(path))
            cover.save(path)

    return scaled


def process_image(img: Image, target_width, target_height, max_crop_percentage=0.11) -> Image:
    original_width, original_height = img.size
    original_aspect_ratio = original_width / original_height
    target_aspect_ratio = target_width / target_height

    # Determine whether to crop or resize with a blur background
    if abs(original_aspect_ratio - target_aspect_ratio) < max_crop_percentage:
        # Perform cropping
        img = ImageOps.fit(img, (target_width, target_height), method=Image.Resampling.LANCZOS)
        return img
    else:
        # Resize the image to fit within the target dimensions while maintaining aspect ratio
        img = resize_image_no_crop(img, target_height)
        resized_width, resized_height = img.size

        # Create a background with the target dimensions
        background = img.copy().filter(ImageFilter.GaussianBlur(15))
        background = background.resize((target_width, target_height), Image.Resampling.LANCZOS)

        # Calculate the position to paste the resized image
        paste_x = (target_width - resized_width) // 2
        paste_y = (target_height - resized_height) // 2

        # Paste the resized image onto the background
        background.paste(img, (paste_x, paste_y))
        return background


def resize_image_no_crop(img, new_height):
    width, height = img.size
    # Calculate the new width to keep the aspect ratio
    aspect_ratio = width / height
    new_width = int(new_height * aspect_ratio)

    # Resize the image with the new dimensions
    return img.resize((new_width, new_height), Image.Resampling.LANCZOS)


def create_text_image(text, image_export=False, **kwargs):
    """
    Create a jpg with given text and return in bytes format
    """
    text_canvas_w = 720
    text_canvas_h = 744
    text_canvas_bg = 'white'
    text_canvas_fg = 'black'
    text_canvas_font_name = 'open_sans_emoji.ttf'

    def load_font(size):
        return ImageFont.truetype(pkg_resources.resource_stream(__name__, text_canvas_font_name), size)

    def find_optimal_size(msg, min_size=20, max_size=400, min_line_w=1, max_line_w=80, padding=0):
        """
        Find optimal font size and line width for a given text
        """

        if min_line_w >= max_line_w:
            raise Exception("illegal arguments, min_line_w < max_line_w needed")

        def line_width(font_size, line_padding=70):
            l = min_line_w
            r = max_line_w
            font = load_font(font_size)
            while l < r:
                n = floor((l + r) / 2)
                t = ''.join([char * n for char in '1'])
                font_w, font_h = font.getbbox(t)[-2:]
                font_w = font_w + (2 * line_padding)
                if font_w >= text_canvas_w:
                    r = n - 1
                    pass
                else:
                    l = n + 1
                    pass
            return n

        size_l = min_size
        size_r = max_size
        last_line_w = 0
        last_size = 0

        while size_l < size_r:
            size = floor((size_l + size_r) / 2.0)
            last_size = size

            line_w = line_width(size)
            last_line_w = line_w

            lines = []
            for line in msg.splitlines():
                cur_lines = textwrap.wrap(line, width=line_w)
                for cur_line in cur_lines:
                    lines.append(cur_line)

            font = load_font(size)
            total_w, line_h = font.getbbox(msg)[-2:]
            tot_height = len(lines) * line_h

            if tot_height + (2 * padding) < text_canvas_h:
                start_y = (text_canvas_h - tot_height) / 2
            else:
                start_y = 0

            if start_y == 0:
                size_r = size - 1
            else:
                # does fit
                size_l = size + 1

        return last_size, last_line_w

    def center_y(lines, font_h):
        tot_height = len(lines) * font_h
        if tot_height < text_canvas_h:
            return (text_canvas_h - tot_height) // 2
        else:
            return 0

    size, line_w = find_optimal_size(text, padding=50)
    logger.debug(f'using font with size: {size}, width: {line_w}')

    font = load_font(size)
    font_w, font_h = font.getbbox(text)[-2:]

    lines = []
    for line in text.splitlines():
        cur_lines = textwrap.wrap(line, width=line_w)
        for cur_line in cur_lines:
            lines.append(cur_line)
    text_y_start = center_y(lines, font_h)

    canvas = Image.new('RGB', (text_canvas_w, text_canvas_h), text_canvas_bg)
    draw = ImageDraw.Draw(canvas)
    for line in lines:
        width, height = font.getbbox(line)[-2:]
        draw.text(((text_canvas_w - width) // 2, text_y_start), line,
                  font=font,
                  fill=text_canvas_fg,
                  embedded_color=True)
        text_y_start += (height)

    if image_export:
        name = strftime("postcard_creator_export_%Y-%m-%d_%H-%M-%S_text.jpg", gmtime())
        path = os.path.join(_get_trace_postcard_sent_dir(), name)
        logger.info('exporting image to {} (image_export=True)'.format(path))
        canvas.save(path)

    img_byte_arr = io.BytesIO()
    canvas.save(img_byte_arr, format='jpeg')
    return img_byte_arr.getvalue()
