"""Uploaded photos on disk. The server makes every file name; an uploaded name is never used."""
from io import BytesIO
from pathlib import Path

from PIL import Image

from backend.app.config import get_settings

MAX_PHOTO_BYTES = 8 * 1024 * 1024


def photo_type(data: bytes) -> str | None:
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    return None


def check_photo(data: bytes) -> str:
    """The file extension of a valid photo; ValueError with a message for the person otherwise."""
    if len(data) > MAX_PHOTO_BYTES:
        raise ValueError("The photo is larger than 8 MB.")
    ext = photo_type(data)
    if ext is None:
        raise ValueError("The photo must be a JPEG or PNG file.")
    try:
        Image.open(BytesIO(data)).verify()
    except Exception as e:  # Pillow raises many kinds of errors for a broken file
        raise ValueError("The photo could not be read.") from e
    return ext


def save_photo(work_id: str, evidence_id: str, data: bytes, ext: str) -> str:
    rel = f"{work_id}/{evidence_id}.{ext}"
    path = Path(get_settings().uploads_dir) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return rel


def resolve(rel_path: str) -> Path | None:
    """The file for a stored path, or None when it is missing or outside the uploads folder."""
    base = Path(get_settings().uploads_dir).resolve()
    p = (base / rel_path).resolve()
    return p if p.is_relative_to(base) and p.is_file() else None


def file_url(rel_path: str) -> str:
    return f"{get_settings().public_base_url.rstrip('/')}/files/{rel_path}"
