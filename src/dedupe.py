from datetime import datetime
from .normalize import (
    normalize_order_id, normalize_payment_type, normalize_product_type,
    build_zone_maps, canonicalize_zone, parse_deadline, similar_address
)

def clean_and_dedupe_orders(raw_orders, zones_rows):
    norm_raw_map, canon_norms = build_zone_maps(zones_rows)
    grouped = {}
    warnings = []

    for r in raw_orders:
        oid = normalize_order_id(r.get("orderId",""))
        city = canonicalize_zone(r.get("city"), norm_raw_map, canon_norms)
        zone = canonicalize_zone(r.get("zoneHint"), norm_raw_map, canon_norms)
        address = (r.get("address") or "").strip()
        payment = normalize_payment_type(r.get("paymentType"))
        product = normalize_product_type(r.get("productType"))

        weight_raw = r.get("weight", 0)
        try:
            weight = float(weight_raw)
        except Exception:
            weight = 0.0
            warnings.append(f"{oid}: invalid weight; coerced to 0")

        dldt = parse_deadline(r.get("deadline"))
        if not dldt:
            warnings.append(f"{oid}: invalid deadline; dropped")
        dl = dldt.strftime("%Y-%m-%d %H:%M") if dldt else None

        new = {
            "orderId": oid,
            "city": city,
            "zoneHint": zone,
            "address": address,
            "paymentType": payment,
            "productType": product,
            "weight": weight,
            "deadline": dl
        }

        if oid not in grouped:
            grouped[oid] = new
            continue

        cur = grouped[oid]
        # earliest deadline wins
        cur_dl = datetime.strptime(cur["deadline"], "%Y-%m-%d %H:%M") if cur["deadline"] else None
        if dldt and (not cur_dl or dldt < cur_dl):
            cur["deadline"] = dl

        # address heuristic
        if new["address"]:
            if cur["address"] and not similar_address(new["address"], cur["address"]):
                warnings.append(f"{oid}: conflicting addresses -> kept '{cur['address']}'")
            elif not cur["address"]:
                cur["address"] = new["address"]

        # prefer non-empty for other simple fields
        for f in ["city","zoneHint","paymentType","productType"]:
            if not cur.get(f) and new.get(f):
                cur[f] = new[f]

        # weight: if conflict, choose the larger for safety
        if new["weight"] and new["weight"] != cur["weight"]:
            mx = max(new["weight"], cur["weight"])
            if mx != cur["weight"]:
                cur["weight"] = mx
            warnings.append(f"{oid}: conflicting weight -> using {cur['weight']}")

    clean = [grouped[k] for k in sorted(grouped)]
    out = {"orders": clean}
    if warnings:
        out["warnings"] = sorted(set(warnings))
    return out
