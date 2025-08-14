import argparse
from pathlib import Path
from .io_utils import read_json, write_json, read_zones, read_csv_text
from .dedupe import clean_and_dedupe_orders
from .plan import plan_orders
from .reconcile import reconcile, parse_log_csv_text

def run(inputs_dir: Path, outputs_dir: Path):
    orders = read_json(inputs_dir / "orders.json")
    couriers = read_json(inputs_dir / "couriers.json")
    zones_rows = read_zones(inputs_dir / "zones.csv")
    log_text = read_csv_text(inputs_dir / "log.csv")

    # A) clean + dedupe
    clean_obj = clean_and_dedupe_orders(orders, zones_rows)
    write_json(outputs_dir / "clean_orders.json", clean_obj)

    # B) plan
    plan_obj = plan_orders(clean_obj, couriers, zones_rows)
    write_json(outputs_dir / "plan.json", plan_obj)

    # C) reconcile
    log_rows = parse_log_csv_text(log_text)
    recon_obj = reconcile(clean_obj, plan_obj, log_rows, couriers, zones_rows)
    # Sort lists explicitly (determinism)
    for k in ["missing","unexpected","duplicate","late","misassigned","overloadedCouriers"]:
        recon_obj[k] = sorted(recon_obj[k])
    write_json(outputs_dir / "reconciliation.json", recon_obj)

def main():
    p = argparse.ArgumentParser(description="AI-Assisted Logistics Cleanup & Reconciliation")
    p.add_argument("--inputs", default="inputs", help="input folder containing orders.json, couriers.json, zones.csv, log.csv")
    p.add_argument("--outputs", default="outputs", help="output folder for clean_orders.json, plan.json, reconciliation.json")
    args = p.parse_args()
    run(Path(args.inputs), Path(args.outputs))

if __name__ == "__main__":
    main()

