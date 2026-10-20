"""Write the demo's before and after photos to data/fixtures/photos/. Run: python -m scripts.make_demo_photos"""
import json
import random
import sys
from datetime import datetime
from io import BytesIO
from pathlib import Path

from PIL import ExifTags, Image, ImageDraw, ImageEnhance
from shapely.geometry import LineString

from backend.app.verify.exif import INDIA
from contracts.models import Scenario

OUT = Path(__file__).resolve().parents[1] / "data" / "fixtures" / "photos"
METRES_PER_DEGREE_LAT = 111_194.93


def make_photo(scene: str, seed: int) -> Image.Image:
    """A drawn road photo. The seed moves the big shapes, so photos of different sites differ."""
    rng = random.Random(seed)
    w, h = 1280, 960
    horizon = rng.randint(180, 460)
    vx = rng.randint(300, 980)
    img = Image.new("RGB", (w, h), (rng.randint(120, 170), rng.randint(150, 190), rng.randint(170, 215)))
    d = ImageDraw.Draw(img)
    d.rectangle([0, horizon, w, h], fill=(rng.randint(90, 130), rng.randint(110, 140), rng.randint(70, 100)))
    for _ in range(rng.randint(3, 6)):  # buildings and trees beside the road
        x0 = rng.randint(0, w - 120)
        bw = rng.randint(90, 320)
        bh = rng.randint(80, 300)
        shade = rng.randint(40, 220)
        d.rectangle([x0, horizon - bh, x0 + bw, horizon + rng.randint(0, 80)],
                    fill=(shade, rng.randint(40, 200), rng.randint(40, 200)))
    left, right = rng.randint(-200, 300), rng.randint(980, 1480)
    d.polygon([(left, h), (right, h), (vx + 40, horizon), (vx - 40, horizon)], fill=(78, 78, 76))
    tx = rng.randint(-160, 160)
    trench = [(w // 2 - 120 + tx, h), (w // 2 + 60 + tx, h), (vx + 12, horizon + 20), (vx - 12, horizon + 20)]
    if scene == "open":
        d.polygon(trench, fill=(96, 64, 40))
        d.line([((trench[0][0] + trench[1][0]) // 2, h), (vx, horizon + 24)], fill=(40, 90, 200), width=16)
    else:  # "patched" or "dark": the trench is closed and patched
        d.polygon(trench, fill=(52, 52, 55))
    if scene == "dark":
        img = ImageEnhance.Brightness(img).enhance(0.12)
    return img


def reuse_copy(img: Image.Image) -> Image.Image:
    """Another work's photo shot again: a slight crop and brighter."""
    w, h = img.size
    return ImageEnhance.Brightness(img.crop((13, 10, w - 13, h - 10)).resize((w, h))).enhance(1.03)


def _dms(value: float) -> tuple[float, float, float]:
    v = abs(value)
    deg = int(v)
    minutes = int((v - deg) * 60)
    return float(deg), float(minutes), round((v - deg - minutes / 60) * 3600, 2)


def with_facts(img: Image.Image, lat: float | None, lon: float | None, taken: datetime | None) -> bytes:
    """The photo as a JPEG with its place and time written in; a None leaves that fact out."""
    exif = Image.Exif()
    gps = {}
    if lat is not None:
        gps |= {ExifTags.GPS.GPSLatitudeRef: "N" if lat >= 0 else "S", ExifTags.GPS.GPSLatitude: _dms(lat)}
    if lon is not None:
        gps |= {ExifTags.GPS.GPSLongitudeRef: "E" if lon >= 0 else "W", ExifTags.GPS.GPSLongitude: _dms(lon)}
    if gps:
        exif[ExifTags.IFD.GPSInfo] = gps
    if taken is not None:
        exif[ExifTags.IFD.Exif] = {ExifTags.Base.DateTimeOriginal: taken.astimezone(INDIA).strftime("%Y:%m:%d %H:%M:%S")}
    buf = BytesIO()
    img.save(buf, "JPEG", quality=85, exif=exif)
    return buf.getvalue()


def site_point(scenario: Scenario, work_id: str, metres_north: float) -> tuple[float, float]:
    """(lat, lon) halfway along the work's middle segment, moved north."""
    work = next(w for w in scenario.works if w.work_id == work_id)
    seg_id = work.segment_ids[len(work.segment_ids) // 2]
    coords = next(s for s in scenario.segments if s.segment_id == seg_id).coords
    # along the line, not the average of its ends: on a bent road that average sits off the road
    mid = LineString(coords).interpolate(0.5, normalized=True)
    return round(mid.y + metres_north / METRES_PER_DEGREE_LAT, 6), round(mid.x, 6)


def _at(day: int, hour: int, minute: int) -> datetime:
    return datetime(2026, 11, day, hour, minute, tzinfo=INDIA)


def main() -> None:
    try:
        from data.scenario import generate_scenario
    except ModuleNotFoundError:
        print("Run this after the data track's demo is merged.")
        sys.exit(1)
    scenario = generate_scenario(1)
    # file, work, kind, image, metres north, taken, facts in the photo ("photo") or from the phone ("phone")
    shots = [
        ("W-104-before.jpg", "W-104", "before", make_photo("open", 1041), 12, _at(10, 8, 12), "photo"),
        ("W-104-after.jpg", "W-104", "after", make_photo("patched", 1041), 12, _at(15, 17, 40), "photo"),
        ("T-221-before.jpg", "T-221", "before", make_photo("open", 2211), 12, _at(10, 8, 20), "photo"),
        ("T-230-before.jpg", "T-230", "before", make_photo("open", 2301), 9, _at(9, 9, 5), "photo"),
        ("T-230-after.jpg", "T-230", "after", reuse_copy(make_photo("open", 2211)), 9, _at(10, 9, 40), "phone"),
        ("P-125-before.jpg", "P-125", "before", make_photo("open", 1251), 15, _at(8, 9, 0), "photo"),
        ("P-125-after.jpg", "P-125", "after", make_photo("dark", 1251), 15, _at(9, 18, 30), "photo"),
    ]
    OUT.mkdir(parents=True, exist_ok=True)
    listing = []
    for file, work_id, kind, img, north, taken, facts in shots:
        lat, lon = site_point(scenario, work_id, north)
        data = with_facts(img, lat, lon, taken) if facts == "photo" else with_facts(img, None, None, None)
        (OUT / file).write_bytes(data)
        listing.append({"file": file, "work_id": work_id, "kind": kind, "lat": lat, "lon": lon,
                        "taken_at": taken.isoformat(), "facts": facts})
        print(f"wrote data/fixtures/photos/{file}")
    (OUT / "photos.json").write_text(json.dumps(listing, indent=2) + "\n", encoding="utf-8")
    print("wrote data/fixtures/photos/photos.json")


if __name__ == "__main__":
    main()
