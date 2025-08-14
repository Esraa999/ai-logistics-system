import json
import csv
from pathlib import Path

def read_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

def write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, sort_keys=False)

def read_csv_text(path: Path) -> str:
    with path.open("r", encoding="utf-8") as f:
        return f.read()

def read_zones(path: Path):
    rows = []
    with path.open("r", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        for r in rdr:
            rows.append({"raw": r["raw"].strip().strip('"'),
                         "canonical": r["canonical"].strip().strip('"')})
    return rows
