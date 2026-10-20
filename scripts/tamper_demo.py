"""Change one record entry behind the app's back, then put it back. Run: python -m scripts.tamper_demo [--seq N | --restore]"""
import argparse
import json
from pathlib import Path

from sqlalchemy import select

from backend.app.db import session
from backend.app.tables import LedgerRow

BACKUP = Path(".cache") / "tamper_backup.json"
EXTRA = " and paid ₹5,00,000 extra"


def _target(seq: int | None) -> LedgerRow | str:
    """The entry to change, or the sentence saying why there is none."""
    with session() as s:
        if seq is not None:
            row = s.get(LedgerRow, seq)
            return row if row else f"No record entry #{seq}."
        row = s.scalars(select(LedgerRow).where(LedgerRow.action == "plan.approved")
                        .order_by(LedgerRow.seq.desc()).limit(1)).first()
        return row if row else "There is no approved plan in the record yet. Use --seq N."


def _set_summary(seq: int, summary: str) -> None:
    with session() as s:
        s.get(LedgerRow, seq).summary = summary


def _restore() -> int:
    if not BACKUP.is_file():
        print("Nothing to restore.")
        return 0
    saved = json.loads(BACKUP.read_text(encoding="utf-8"))
    _set_summary(saved["seq"], saved["summary"])
    BACKUP.unlink()
    print(f"Restored record entry #{saved['seq']}. The record check passes again.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Change one record entry for the demo, then put it back.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--seq", type=int, help="the entry to change (default: the newest approved plan)")
    group.add_argument("--restore", action="store_true", help="put the changed entry back")
    args = parser.parse_args(argv)
    if args.restore:
        return _restore()
    if BACKUP.is_file():
        print(f"Entry #{json.loads(BACKUP.read_text(encoding='utf-8'))['seq']} is already changed. "
              "Run with --restore first.")
        return 1
    row = _target(args.seq)
    if isinstance(row, str):
        print(row)
        return 1
    BACKUP.parent.mkdir(parents=True, exist_ok=True)
    BACKUP.write_text(json.dumps({"seq": row.seq, "summary": row.summary}, ensure_ascii=False), encoding="utf-8")
    _set_summary(row.seq, row.summary + EXTRA)
    print(f"Changed record entry #{row.seq}: {row.summary + EXTRA}")
    print(f"Check the record now: it fails at #{row.seq}. Undo with: python -m scripts.tamper_demo --restore")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
