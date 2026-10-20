from io import BytesIO

import pytest
from PIL import Image

from backend.app import storage

JPEG_HEAD = b"\xff\xd8\xff"


def _jpeg() -> bytes:
    buf = BytesIO()
    Image.new("RGB", (32, 24), (120, 90, 60)).save(buf, "JPEG")
    return buf.getvalue()


def test_photo_type():
    assert storage.photo_type(JPEG_HEAD + b"\xe0rest") == "jpg"
    assert storage.photo_type(b"\x89PNG\r\n\x1a\nrest") == "png"
    assert storage.photo_type(b"hello") is None


@pytest.mark.parametrize(("data", "message"), [
    (JPEG_HEAD + b"\0" * (9 * 1024 * 1024), "The photo is larger than 8 MB."),
    (b"hello", "The photo must be a JPEG or PNG file."),
    (JPEG_HEAD + b"junk" * 25, "The photo could not be read."),
], ids=["too-big", "not-a-photo", "broken"])
def test_check_photo_refuses(data, message):
    with pytest.raises(ValueError, match=message):
        storage.check_photo(data)


def test_check_photo_accepts_a_jpeg():
    assert storage.check_photo(_jpeg()) == "jpg"


def test_save_and_resolve(uploads_dir):
    rel = storage.save_photo("W-001", "E-0001", _jpeg(), "jpg")
    assert rel == "W-001/E-0001.jpg"
    assert storage.resolve(rel) == (uploads_dir / "W-001" / "E-0001.jpg").resolve()
    assert storage.resolve("../../etc/passwd") is None
    assert storage.resolve("W-001/../../x") is None
    assert storage.resolve("W-001/missing.jpg") is None


def test_files_route(uploads_dir, client):
    data = _jpeg()
    rel = storage.save_photo("W-001", "E-0001", data, "jpg")
    r = client.get(f"/files/{rel}")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/jpeg"
    assert r.content == data
    missing = client.get("/files/../../etc/passwd")
    assert missing.status_code == 404
    assert client.get("/files/W-001/E-9999.jpg").json() == {"detail": "File not found."}
