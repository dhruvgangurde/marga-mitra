"""A photo's fingerprint: photos that look alike have fingerprints a small distance apart."""
from io import BytesIO

import imagehash
from PIL import Image


def fingerprint(data: bytes) -> str:
    return str(imagehash.phash(Image.open(BytesIO(data)).convert("RGB")))


def distance(a: str, b: str) -> int:
    return int(imagehash.hex_to_hash(a) - imagehash.hex_to_hash(b))


def alike_percent(d: int) -> int:
    return round((1 - d / 64) * 100)
