import re
import time
from pathlib import Path

from data.demo import demo_scenario
from risk.windows import compute_risk_windows

RISK = Path(__file__).resolve().parents[2] / "risk"


def test_only_one_network_call():
    hits = []
    for path in RISK.glob("*.py"):
        text = path.read_text(encoding="utf-8-sig")
        if re.search(r"urlopen|requests\.|httpx|socket", text):
            hits.append(path.name)
    assert hits == ["weather.py"]
    assert len(re.findall(r"urlopen", (RISK / "weather.py").read_text(encoding="utf-8-sig"))) == 1


def test_deterministic(need_snapshot):
    demo = demo_scenario()
    first = compute_risk_windows(demo, "fixture")
    assert all(compute_risk_windows(demo, "fixture") == first for _ in range(5))


def test_fast(need_snapshot):
    demo = demo_scenario()
    compute_risk_windows(demo, "fixture")
    start = time.perf_counter()
    compute_risk_windows(demo, "fixture")
    assert (time.perf_counter() - start) * 1000 < 50
