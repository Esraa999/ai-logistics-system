# src/plan.py

from datetime import datetime
from .normalize import build_zone_maps, canonicalize_zone

def _norm_couriers(couriers, zones_rows):
    norm_raw_map, canon_norms = build_zone_maps(zones_rows)
    res = []
    for c in couriers:
        zones = [canonicalize_zone(z, norm_raw_map, canon_norms) for z in c.get("zonesCovered", [])]
        res.append({
            "courierId": c["courierId"],
            "courierUpper": c["courierId"].upper(),
            "zonesCovered": zones,
            "acceptsCOD": bool(c.get("acceptsCOD")),
            "exclusions": [(e or "").strip().lower() for e in c.get("exclusions", [])],
            "dailyCapacity": float(c.get("dailyCapacity", 0)),
            "priority": int(c.get("priority", 999))
        })
    return res

def _covers(c, order):
    return (order["city"] in c["zonesCovered"]) or (order["zoneHint"] in c["zonesCovered"])

def _ok_constraints(c, order):
    if order["paymentType"] == "COD" and not c["acceptsCOD"]:
        return False
    if (order["productType"] or "").lower() in set(c["exclusions"]):
        return False
    return True

def _parse_dl(s):
    return datetime.strptime(s, "%Y-%m-%d %H:%M") if s else datetime.max

def plan_orders(clean_orders_obj, couriers, zones_rows):
    clean_orders = clean_orders_obj["orders"]
    couriers_n = _norm_couriers(couriers, zones_rows)
    loads = {c["courierId"]: 0.0 for c in couriers_n}

    # Deterministic order: earliest deadline, then orderId (this satisfies the "tightest deadline" tie-break)
    orders_sorted = sorted(clean_orders, key=lambda o: (_parse_dl(o["deadline"]), o["orderId"]))

    assignments, unassigned = [], []
    for o in orders_sorted:
        w = float(o["weight"] or 0)
        candidates = []
        for c in couriers_n:
            if _covers(c, o) and _ok_constraints(c, o):
                # ENFORCE CAPACITY HERE
                if loads[c["courierId"]] + w <= c["dailyCapacity"] + 1e-9:
                    candidates.append(c)

        if not candidates:
            # Spec-compliant reason string
            unassigned.append({"orderId": o["orderId"], "reason": "no_supported_courier_or_capacity"})
            continue

        # Tie-breakers: 1) lower priority, 2) lowest current load, 3) lex courierId
        candidates.sort(key=lambda c: (c["priority"], loads[c["courierId"]], c["courierId"]))

        chosen = candidates[0]
        assignments.append({"orderId": o["orderId"], "courierId": chosen["courierId"]})
        loads[chosen["courierId"]] += w

    cap_usage = [{"courierId": k, "totalWeight": (int(v) if abs(v - int(v)) < 1e-9 else v)}
                 for k, v in sorted(loads.items())]

    return {
        "assignments": sorted(assignments, key=lambda x: x["orderId"]),
        "unassigned": sorted(unassigned, key=lambda x: x["orderId"]),
        "capacityUsage": cap_usage
    }
