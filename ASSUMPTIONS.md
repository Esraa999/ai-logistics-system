# Assumptions & Rules

## Data Normalization

### Order ID Normalization
- **Rule**: Trim whitespace, convert to uppercase, strip non-alphanumeric characters from ends
- **Pattern Matching**: When possible, normalize to LETTERS-DIGITS format (e.g., `ord001` → `ORD-001`, `ORD-002.` → `ORD-002`)
- **Fallback**: If no clear pattern exists, use the cleaned uppercase version as-is

### Geographic Normalization (Cities/Zones)
- **Primary Source**: Canonicalization strictly follows zones.csv mappings
- **Matching Strategy** (in order of precedence):
  1. Direct normalized match against raw values in zones.csv
  2. Substring detection - if any canonical zone appears within the input string (handles cases like "6 October- El Montazah")
  3. Special case handling for "6 Oct" patterns → "6th of October"
  4. Fuzzy string matching with threshold ≥0.84 similarity ratio
  5. Return original input if no match found
- **Case/Typo Tolerance**: All matching is case-insensitive with punctuation normalization

### Payment Type Normalization
- **COD Variants**: "cod", "cash on delivery", "c.o.d", "cash" → "COD"
- **Default**: All other values → "Prepaid"

### Product Type Normalization
- **Fragile**: Exact match "fragile" (case-insensitive) → "fragile"
- **Default**: All other values → "standard"

### Weight & Deadline Processing
- **Weight**: Coerce to float; invalid values default to 0.0 with warning
- **Deadline**: Accept both "YYYY-MM-DD HH:MM" and "YYYY/MM/DD HH:MM" formats; invalid dates dropped with warning

## De-duplication Logic

### Grouping
- Orders grouped by normalized orderId
- Multiple orders with same normalized ID are merged using conflict resolution rules

### Conflict Resolution (in precedence order)
1. **Deadline**: Earliest deadline wins when conflicting
2. **Address Similarity**: 
   - If normalized addresses are similar (substring match or edit similarity ≥0.85), treat as same location
   - Otherwise, keep first address and emit warning about conflict
3. **Field Preference**: For other fields (city, zoneHint, paymentType, productType), prefer non-empty values
4. **Weight Conflicts**: Choose larger weight value for safety, emit warning

### Warnings Generated
- Invalid weight coercion
- Invalid deadline parsing
- Conflicting addresses for same order
- Conflicting weights for same order

## Courier Assignment Planning

### Eligibility Criteria
A courier can handle an order if ALL conditions are met:
1. **Zone Coverage**: Courier covers either the normalized city OR normalized zoneHint
2. **Payment Acceptance**: If order is COD, courier must accept COD (`acceptsCOD: true`)
3. **Product Exclusions**: Order's productType must NOT be in courier's exclusions list
4. **Capacity**: Sum of assigned weights must not exceed courier's dailyCapacity

### Assignment Algorithm
- **Processing Order**: Orders sorted by (earliest deadline, then orderId alphabetically)
- **Tie-Breaking** when multiple eligible couriers exist (in order):
  1. Lower priority value (1 beats 2)
  2. Lowest current assigned load (by total weight)
  3. Lexicographical courierId

### Capacity Tracking
- Measured as sum of order weights assigned to each courier
- Real-time tracking during assignment process
- Reported in capacityUsage output

## Reconciliation Logic

### Log Processing
- **Normalization**: OrderId normalized using same rules as orders
- **Courier Matching**: Case-insensitive courier name matching
- **Duplicate Handling**: For lateness/weight calculations, use earliest scan per order

### Issue Detection Categories

#### Missing Orders
- Orders planned for delivery but not found in delivery log

#### Unexpected Orders  
- Orders in delivery log but not present in clean_orders.json

#### Duplicate Scans
- Same orderId appears multiple times in delivery log (counting all scans)

#### Late Deliveries
- Delivered datetime is strictly after order deadline
- Uses earliest scan per order for timing

#### Misassigned Orders (Relaxed Rule)
An order is misassigned if:
- Delivered by a courier that cannot feasibly handle the order (violates coverage, COD, or exclusion constraints), OR
- Delivered by a different courier when the planned courier was the ONLY feasible option

#### Overloaded Couriers
- Courier's actual delivered weight (sum of unique orders) exceeds their dailyCapacity
- Uses earliest scan per order to avoid double-counting duplicates

## Capacity Handling & Assignment Logic

### Capacity Consideration
- **Default Behavior**: Capacity constraints are enforced during planning - orders only assigned if courier has sufficient remaining capacity
- **Optional Override**: To disable capacity checking for testing scenarios, uncomment lines 24-25 in `src/plan.py`:
  ```python
  # if loads[c["courierId"]] + w <= c["dailyCapacity"] + 1e-9:
  #     candidates.append(c)
  ```
  And comment out the current line 26: `candidates.append(c)`
- **Warning**: Modifying capacity enforcement will affect test results - Test 2 specifically validates capacity-constrained assignments
- **Weight Tracking**: Actual capacity usage is always reported in capacityUsage output, regardless of whether capacity was enforced during assignment

### Assignment Destination Logic
- Couriers are considered eligible based on **zone coverage** - they must cover either the order's normalized city OR normalized zoneHint
- This dual-destination approach handles cases where city and zone might represent different levels of geographic specificity

## Test Organization Structure

### Independent Test Cases
- Each test case has separate `inputs/` and `outputs/` directories under `tests/testX/`
- Input files are never overwritten - each test uses its own isolated input set
- Output files are generated fresh for each test run, preventing cross-contamination
- Expected results stored in `tests/testX/expected/` for comparison
- This structure ensures tests are completely independent and repeatable

## Output Determinism

### Sorting Requirements
- All output arrays sorted alphabetically by relevant keys
- Assignment arrays sorted by orderId
- Capacity usage sorted by courierId
- All reconciliation categories sorted alphabetically

### Reproducibility
- No randomness in algorithms
- Fixed tie-breaking rules
- Consistent normalization logic
- Deterministic conflict resolution

### Error Handling & Code Quality

### Graceful Degradation
- Invalid data coerced to sensible defaults where possible
- Warnings generated for data quality issues
- Processing continues despite individual record problems

### Type Safety & Compatibility
- Added proper typing imports (`from typing import Optional`) for Python 3.9+ compatibility
- Used `Optional[str]` instead of `str | None` union syntax for broader Python version support
- All function signatures include appropriate type hints

### Validation
- Required files must exist and be readable
- JSON files must be valid JSON
- CSV files must have expected structure with flexible column name detection
- Missing or malformed records logged but don't halt processing