"""Write docs/openapi.json from the app. Run: python -m scripts.export_openapi (no database needed)."""
import json
from pathlib import Path

from backend.app.main import app

OUT = Path(__file__).resolve().parents[1] / "docs" / "openapi.json"


def main() -> None:
    spec = app.openapi()
    OUT.write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote docs/openapi.json ({len(spec['paths'])} paths)")


if __name__ == "__main__":
    main()
