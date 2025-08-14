import json
import csv
import re
from datetime import datetime
from typing import Dict, List, Any, Optional
import difflib

class DataCleaner:
    def __init__(self):
        self.zone_mapping = {}
        self.warnings = []
    
    def load_zone_mapping(self, zones_csv_path: str):
        """Load canonical zone mapping from CSV"""
        self.zone_mapping = {}
        with open(zones_csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Handle different possible column names
                raw_key = None
                canonical_key = None
                
                # Check for different column name variations
                for key in row.keys():
                    if key.lower().strip() in ['raw', 'raw_zone', 'original']:
                        raw_key = key
                    elif key.lower().strip() in ['canonical', 'canonical_zone', 'normalized']:
                        canonical_key = key
                
                if raw_key and canonical_key:
                    raw_value = row[raw_key].strip()
                    canonical_value = row[canonical_key].strip()
                    self.zone_mapping[raw_value] = canonical_value
    
    def normalize_order_id(self, order_id: str) -> str:
        """Normalize order ID: trim, uppercase, strip non-alphanumerics at ends"""
        # Trim whitespace
        normalized = order_id.strip()
        
        # Remove non-alphanumeric characters from start and end
        normalized = re.sub(r'^[^a-zA-Z0-9]+', '', normalized)
        normalized = re.sub(r'[^a-zA-Z0-9]+$', '', normalized)
        
        # Convert to uppercase
        normalized = normalized.upper()
        
        # Handle special case: "ord001" should become "ORD-001" 
        # Add hyphen after letters if followed by numbers and no hyphen exists
        if re.match(r'^[A-Z]+[0-9]+$', normalized):
            # Find where letters end and numbers begin
            match = re.match(r'^([A-Z]+)([0-9]+)$', normalized)
            if match:
                normalized = f"{match.group(1)}-{match.group(2)}"
        
        return normalized
    
    def normalize_zone(self, zone: str) -> str:
        """Normalize zone using canonical mapping"""
        if not zone:
            return ""
        
        zone = zone.strip()
        
        # Direct match
        if zone in self.zone_mapping:
            return self.zone_mapping[zone]
        
        # Case-insensitive match
        for raw, canonical in self.zone_mapping.items():
            if zone.lower() == raw.lower():
                return canonical
        
        # Fuzzy match for typos
        best_match = difflib.get_close_matches(zone, self.zone_mapping.keys(), n=1, cutoff=0.8)
        if best_match:
            return self.zone_mapping[best_match[0]]
        
        return zone
    
    def normalize_payment_type(self, payment_type: str) -> str:
        """Normalize payment type to COD or Prepaid"""
        if not payment_type:
            return "COD"
        
        payment_type = payment_type.strip().lower()
        if payment_type in ['cod', 'cash', 'cash on delivery']:
            return "COD"
        elif payment_type in ['prepaid', 'paid', 'credit', 'debit']:
            return "Prepaid"
        
        return "COD"  # Default
    
    def normalize_product_type(self, product_type: str) -> str:
        """Normalize product type to lowercase canonical"""
        if not product_type:
            return "standard"
        
        return product_type.strip().lower()
    
    def parse_deadline(self, deadline_str: str) -> Optional[datetime]:
        """Parse deadline string to datetime object"""
        if not deadline_str:
            return None
        
        deadline_str = deadline_str.strip()
        
        # Try YYYY-MM-DD HH:MM format
        try:
            return datetime.strptime(deadline_str, '%Y-%m-%d %H:%M')
        except ValueError:
            pass
        
        # Try YYYY/MM/DD HH:MM format
        try:
            return datetime.strptime(deadline_str, '%Y/%m/%d %H:%M')
        except ValueError:
            pass
        
        self.warnings.append(f"Could not parse deadline: {deadline_str}")
        return None
    
    def normalize_weight(self, weight) -> float:
        """Normalize weight to float"""
        if isinstance(weight, (int, float)):
            return float(weight)
        
        try:
            return float(str(weight).strip())
        except (ValueError, TypeError):
            return 0.0
    
    def addresses_similar(self, addr1: str, addr2: str) -> bool:
        """Simple heuristic to check if addresses describe the same location"""
        if not addr1 or not addr2:
            return False
        
        # Normalize addresses for comparison
        norm1 = re.sub(r'[^a-zA-Z0-9\s]', '', addr1.lower().strip())
        norm2 = re.sub(r'[^a-zA-Z0-9\s]', '', addr2.lower().strip())
        
        # Check similarity using difflib
        similarity = difflib.SequenceMatcher(None, norm1, norm2).ratio()
        return similarity >= 0.8
    
    def merge_orders(self, orders: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Merge duplicate orders, preferring non-empty fields and earliest deadline"""
        if len(orders) == 1:
            return orders[0]
        
        merged = {}
        deadlines = []
        addresses = []
        
        # Collect all non-empty values for each field
        for order in orders:
            for key, value in order.items():
                if key == 'deadline' and value:
                    deadlines.append(value)
                elif key == 'address' and value:
                    addresses.append(value)
                elif value and (key not in merged or not merged[key]):
                    merged[key] = value
        
        # Handle deadline - keep earliest
        if deadlines:
            earliest_deadline = min(deadlines)
            merged['deadline'] = earliest_deadline
        
        # Handle address conflicts
        if len(addresses) > 1:
            unique_addresses = []
            for addr in addresses:
                is_similar_to_existing = any(self.addresses_similar(addr, existing) 
                                           for existing in unique_addresses)
                if not is_similar_to_existing:
                    unique_addresses.append(addr)
            
            if len(unique_addresses) > 1:
                self.warnings.append(f"Address conflict for order {merged.get('orderId', 'unknown')}: {unique_addresses}")
            
            merged['address'] = unique_addresses[0]  # Keep first unique address
        elif len(addresses) == 1:
            merged['address'] = addresses[0]
        
        return merged
    
    def clean_orders(self, orders_json_path: str, zones_csv_path: str) -> Dict[str, Any]:
        """Main function to clean and normalize orders"""
        self.warnings = []
        
        # Load zone mapping
        self.load_zone_mapping(zones_csv_path)
        
        # Load orders
        with open(orders_json_path, 'r', encoding='utf-8') as f:
            raw_orders = json.load(f)
        
        # Group orders by normalized ID for deduplication
        order_groups = {}
        
        for order in raw_orders:
            # Normalize order ID
            normalized_id = self.normalize_order_id(order.get('orderId', ''))
            
            # Normalize other fields
            normalized_order = {
                'orderId': normalized_id,
                'city': self.normalize_zone(order.get('city', '')),
                'zoneHint': self.normalize_zone(order.get('zoneHint', '')),
                'address': order.get('address', '').strip(),
                'paymentType': self.normalize_payment_type(order.get('paymentType', '')),
                'productType': self.normalize_product_type(order.get('productType', '')),
                'weight': self.normalize_weight(order.get('weight', 0)),
                'deadline': self.parse_deadline(order.get('deadline', ''))
            }
            
            if normalized_id not in order_groups:
                order_groups[normalized_id] = []
            order_groups[normalized_id].append(normalized_order)
        
        # Merge duplicates
        clean_orders_list = []
        for order_id, orders in order_groups.items():
            if len(orders) > 1:
                self.warnings.append(f"Duplicate orders found for ID {order_id}: {len(orders)} instances")
            
            merged_order = self.merge_orders(orders)
            clean_orders_list.append(merged_order)
        
        # Sort by order ID for determinism
        clean_orders_list.sort(key=lambda x: x['orderId'])
        
        result = {'orders': clean_orders_list}
        if self.warnings:
            result['warnings'] = sorted(self.warnings)
        
        return result
    
    def save_clean_orders(self, clean_orders: Dict[str, Any], output_path: str):
        """Save cleaned orders to JSON file"""
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(clean_orders, f, indent=2, default=str, sort_keys=True)