import json
import filecmp
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable

def run_case(name):
    case_dir = ROOT / "tests" / name
    inp = case_dir / "inputs"
    out = case_dir / "outputs"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)

    cmd = [PY, "-m", "src.main", "--inputs", str(inp), "--outputs", str(out)]
    r = subprocess.run(cmd, cwd=ROOT)
    if r.returncode != 0:
        print(f"[{name}] FAILED: non-zero exit code")
        return False

    ok = True
    exp_dir = case_dir / "expected"
    if exp_dir.exists():
        for exp_file in exp_dir.glob("*.json"):
            got_file = out / exp_file.name
            if not got_file.exists():
                print(f"[{name}] MISSING output: {exp_file.name}")
                ok = False
                continue
            # Compare JSON structurally (ignoring whitespace/order of keys)
            ej = json.loads(exp_file.read_text(encoding="utf-8"))
            gj = json.loads(got_file.read_text(encoding="utf-8"))
            if ej != gj:
                print(f"[{name}] DIFF in {exp_file.name}")
                print("Expected:", json.dumps(ej, indent=2, ensure_ascii=False))
                print("Got     :", json.dumps(gj, indent=2, ensure_ascii=False))
                ok = False
    print(f"[{name}] {'Success' if ok else 'FAIL'}")
    return ok

def main():
    all_ok = True
    for name in ["test1","test2","test3","test4"]:
        all_ok &= run_case(name)
    sys.exit(0 if all_ok else 1)

if __name__ == "__main__":
    main()