from datetime import datetime
from io import BytesIO

from PIL import ExifTags, Image

from backend.app.verify.exif import INDIA, read_photo_facts
from backend.app.verify.phash import alike_percent, distance, fingerprint


def _tagged_jpeg() -> bytes:
    img = Image.new("RGB", (64, 48), (90, 110, 80))
    exif = Image.Exif()
    exif[ExifTags.IFD.GPSInfo] = {ExifTags.GPS.GPSLatitudeRef: "N", ExifTags.GPS.GPSLatitude: (13.0, 0.0, 36.39),
                                  ExifTags.GPS.GPSLongitudeRef: "E", ExifTags.GPS.GPSLongitude: (74.0, 47.0, 34.8)}
    exif[ExifTags.IFD.Exif] = {ExifTags.Base.DateTimeOriginal: "2026:11:10 08:12:00"}
    buf = BytesIO()
    img.save(buf, "JPEG", quality=85, exif=exif)
    return buf.getvalue()


def _png() -> bytes:
    buf = BytesIO()
    Image.new("RGB", (64, 48), (90, 110, 80)).save(buf, "PNG")
    return buf.getvalue()


def test_facts_in_the_photo():
    assert read_photo_facts(_tagged_jpeg()) == (13.010108, 74.793, datetime(2026, 11, 10, 8, 12, tzinfo=INDIA))


def test_no_facts():
    assert read_photo_facts(_png()) == (None, None, None)
    assert read_photo_facts(b"\xff\xd8\xff" + b"\x00" * 100) == (None, None, None)


def test_fingerprint():
    data = _tagged_jpeg()
    assert fingerprint(data) == fingerprint(data)
    assert len(fingerprint(data)) == 16
    assert distance(fingerprint(data), fingerprint(data)) == 0
    assert (alike_percent(0), alike_percent(4), alike_percent(8)) == (100, 94, 88)
