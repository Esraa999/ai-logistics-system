from collections import defaultdict
from .normalize import normalize_order_id, parse_deadline, build_zone_maps, canonicalize_zone

def _norm_couriers(couriers, zones_rows):
    norm_raw_map, canon_norms = build_zone_maps(zones_rows)
    res = []
    for c in couriers:
        zones = [canonicalize_zone(z, norm_raw_map, canon_norms) for z in c.get("zonesCovered",[])]
        res.append({
            "courierId": c["courierId"],
            "courierUpper": c["courierId"].upper(),
            "zonesCovered": zones,
            "acceptsCOD": bool(c.get("acceptsCOD")),
            "exclusions": [ (e or "").strip().lower() for e in c.get("exclusions",[]) ],
            "dailyCapacity": float(c.get("dailyCapacity",0)),
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

def parse_log_csv_text(text: str):
    rows = []
    for line in (text or "").strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) != 3:
            continue
        if parts[0].lower() == "orderid":
            continue
        rows.append({"orderId": parts[0], "courierId": parts[1], "deliveredAt": parts[2]})
    return rows

def reconcile(clean_orders_obj, plan_obj, log_rows, couriers, zones_rows):
    orders = clean_orders_obj["orders"]
    orders_by_id = {o["orderId"]: o for o in orders}
    planned = {a["orderId"]: a["courierId"] for a in plan_obj["assignments"]}

    couriers_n = _norm_couriers(couriers, zones_rows)
    courier_by_upper = {c["courierUpper"]: c for c in couriers_n}
    courier_caps = {c["courierUpper"]: c["dailyCapacity"] for c in couriers_n}

    # feasible couriers per order (used for relaxed misassignment logic)
    feasible = {}
    for o in orders:
        feas = []
        for c in couriers_n:
            if _covers(c, o) and _ok_constraints(c, o):
                feas.append(c["courierId"])
        feasible[o["orderId"]] = sorted(feas)

    # normalize logs; keep earliest scan per order for lateness/weight
    logs = []
    for r in log_rows:
        oid = normalize_order_id(r["orderId"])
        cid_upper = (r["courierId"] or "").strip().upper()
        delivered_at = parse_deadline(r["deliveredAt"])
        logs.append({"orderId": oid, "courierUpper": cid_upper, "deliveredAt": delivered_at})

    seen = defaultdict(int)
    actual_by_order = {}
    for l in logs:
        seen[l["orderId"]] += 1
        if l["orderId"] not in actual_by_order or (l["deliveredAt"] and actual_by_order[l["orderId"]]["deliveredAt"] and l["deliveredAt"] < actual_by_order[l["orderId"]]["deliveredAt"]):
            actual_by_order[l["orderId"]] = l

    planned_ids = set(planned)
    log_ids = set(actual_by_order)
    clean_ids = set(orders_by_id)

    missing = sorted([oid for oid in planned_ids if oid not in log_ids])
    unexpected = sorted([oid for oid in log_ids if oid not in clean_ids])
    duplicate = sorted([oid for oid, cnt in seen.items() if cnt > 1])

    late = []
    for oid, l in actual_by_order.items():
        if oid in orders_by_id:
            dl = parse_deadline(orders_by_id[oid]["deadline"])
            if dl and l["deliveredAt"] and l["deliveredAt"] > dl:
                late.append(oid)
    late = sorted(late)

    # relaxed misassignment rule to match spec notes:
    # flag if delivered by an infeasible courier, OR delivered by a different courier when the planned courier was the only feasible option.
    misassigned = []
    for oid, l in actual_by_order.items():
        if oid in orders_by_id and oid in planned:
            feas = feasible.get(oid, [])
            logged_c = courier_by_upper.get(l["courierUpper"])
            logged_ok = bool(logged_c and logged_c["courierId"] in feas)
            if not logged_ok:
                misassigned.append(oid)
            else:
                planned_cid = planned[oid]
                if len(feas) == 1 and planned_cid.upper() != l["courierUpper"]:
                    misassigned.append(oid)
    misassigned = sorted(set(misassigned))

    # overloaded by actual delivered (unique orders)
    delivered_weight_by_upper = defaultdict(float)
    for oid, l in actual_by_order.items():
        if oid in orders_by_id and l["courierUpper"] in courier_by_upper:
            delivered_weight_by_upper[l["courierUpper"]] += float(orders_by_id[oid]["weight"] or 0.0)

    overloaded = []
    for cupper, tot in delivered_weight_by_upper.items():
        cap = courier_caps.get(cupper, float("inf"))
        if tot > cap + 1e-9:
            overloaded.append(courier_by_upper[cupper]["courierId"])
    overloaded = sorted(overloaded)

    return {
        "missing": missing,
        "unexpected": unexpected,
        "duplicate": duplicate,
        "late": late,
        "misassigned": misassigned,
        "overloadedCouriers": overloaded
    }
