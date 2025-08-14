from typing import Optional
import re
import difflib

def _norm_token(s: str) -> str:
    return re.sub(r'[^a-z0-9]+', '', (s or '').lower())

def normalize_order_id(s: str) -> str:
    s = (s or "").strip().upper()
    s = re.sub(r'^[^A-Z0-9]+', '', s)
    s = re.sub(r'[^A-Z0-9]+$', '', s)
    m = re.match(r'^([A-Z]+)[\s\-\._]*([0-9]+)$', s)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    return s

def normalize_payment_type(s: str) -> str:
    s = (s or "").strip().lower()
    return "COD" if s in {"cod","cash on delivery","c.o.d","cash"} else "Prepaid"

def normalize_product_type(s: str) -> str:
    s = (s or "").strip().lower()
    return "fragile" if s == "fragile" else "standard"

def build_zone_maps(zones_rows):
    raw_to_canon = {}
    canon_norm_to_canon = {}
    for r in zones_rows:
        raw_to_canon[r["raw"]] = r["canonical"]
        canon_norm_to_canon[_norm_token(r["canonical"])] = r["canonical"]
    for v in list(raw_to_canon.values()):
        raw_to_canon.setdefault(v, v)
    norm_raw_map = { _norm_token(k): v for k, v in raw_to_canon.items() }
    return norm_raw_map, canon_norm_to_canon

def canonicalize_zone(term: str, norm_raw_map, canon_norms) -> Optional[str]:
    if not term:
        return None
    norm = _norm_token(term)
    # if any canonical appears inside the input, use it (handles "6 October- El Montazah")
    for cnorm, can in canon_norms.items():
        if cnorm in norm:
            return can
    # direct map
    if norm in norm_raw_map:
        return norm_raw_map[norm]
    # special tolerance for "6 Oct"
    if re.search(r'\b6\s*oct\b', (term or '').lower()):
        return "6th of October"
    # fuzzy fallback
    best, best_ratio = None, 0.0
    for nk, v in norm_raw_map.items():
        r = difflib.SequenceMatcher(a=norm, b=nk).ratio()
        if r > best_ratio:
            best_ratio, best = r, v
    return best if best_ratio >= 0.84 else term.strip()

def parse_deadline(s: str):
    from datetime import datetime
    if s is None:
        return None
    for fmt in ("%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M"):
        try:
            return datetime.strptime(s.strip(), fmt)
        except Exception:
            pass
    return None

def address_key(s: str) -> str:
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9]+', ' ', (s or '').lower())).strip()

def similar_address(a: str, b: str) -> bool:
    if not a or not b:
        return False
    ak, bk = address_key(a), address_key(b)
    if not ak or not bk:
        return False
    if ak in bk or bk in ak:
        return True
    import difflib
    return difflib.SequenceMatcher(a=ak, b=bk).ratio() >= 0.85
