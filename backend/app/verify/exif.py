"""Where and when a photo was taken, from the facts the camera wrote into it."""
from datetime import datetime, timedelta, timezone
from io import BytesIO
from typing import Any

from PIL import ExifTags, Image

INDIA = timezone(timedelta(hours=5, minutes=30))


def _degrees(gps: dict[int, Any], value_tag: int, ref_tag: int, negative_ref: str) -> float | None:
    parts = gps.get(value_tag)
    if not parts:
        return None
    d, m, s = (float(p) for p in parts)
    value = d + m / 60 + s / 3600
    return round(-value if gps.get(ref_tag) == negative_ref else value, 6)


def read_photo_facts(data: bytes) -> tuple[float | None, float | None, datetime | None]:
    """(lat, lon, taken_at); a missing part is None. A photo time has no zone, so it is read as India time."""
    try:
        ex = Image.open(BytesIO(data)).getexif()
        gps = ex.get_ifd(ExifTags.IFD.GPSInfo)
        lat = _degrees(gps, ExifTags.GPS.GPSLatitude, ExifTags.GPS.GPSLatitudeRef, "S")
        lon = _degrees(gps, ExifTags.GPS.GPSLongitude, ExifTags.GPS.GPSLongitudeRef, "W")
        raw = ex.get_ifd(ExifTags.IFD.Exif).get(ExifTags.Base.DateTimeOriginal)
        taken = datetime.strptime(raw, "%Y:%m:%d %H:%M:%S").replace(tzinfo=INDIA) if raw else None
        return lat, lon, taken
    except Exception:  # a broken or odd file has no usable facts; the checks then ask for them another way
        return None, None, None
