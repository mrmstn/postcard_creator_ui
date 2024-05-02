from pathlib import Path

SUFFIX_COVER = "_cover"
SUFFIX_TEXT = "_text"
SUFFIX_STAMP = "_stamp"
SUFFIX_DATA = "_data"

image_stem_suffix = [SUFFIX_COVER, SUFFIX_TEXT, SUFFIX_STAMP]
IMAGE_EXTENSION = ".jpeg"


def filename_cover(file: Path) -> Path:
    return _make_image_filename(file, SUFFIX_COVER)


def is_cover(file: Path) -> bool:
    return file.stem.endswith(SUFFIX_COVER) and file.suffix == IMAGE_EXTENSION


def filename_text(file: Path) -> Path:
    return _make_image_filename(file, SUFFIX_TEXT)


def is_text(file: Path) -> bool:
    return file.stem.endswith(SUFFIX_TEXT)


def filename_stamp(file: Path) -> Path:
    return _make_image_filename(file, SUFFIX_STAMP)


def is_stamp(file: Path) -> bool:
    return file.stem.endswith(SUFFIX_STAMP)


def is_generated_image(file: Path) -> bool:
    if not file.suffix.endswith(IMAGE_EXTENSION):
        return False

    for suffix in image_stem_suffix:
        if file.stem.endswith(suffix):
            return True
    return False


def _maybe_update_stem(file: Path, suffix: str) -> Path:
    stem = file.stem
    if stem.endswith(suffix):
        return file

    new_stem = stem + suffix
    return file.with_stem(new_stem)


def _make_image_filename(file: Path, suffix: str) -> Path:
    return _maybe_update_stem(file, suffix).with_suffix(IMAGE_EXTENSION)


def maybe_load_data(file: Path):
    data = None
    if file.is_file():
        with open(file, "r") as f:
            import json
            data = json.load(f)

    return data


def filename_data(file: Path) -> Path:
    new_file = _maybe_update_stem(file, SUFFIX_DATA).with_suffix('.json')

    return new_file
