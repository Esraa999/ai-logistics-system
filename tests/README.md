# AI-Assisted Logistics Cleanup & Reconciliation

A command-line tool written in Python that processes logistics data to:
1. Clean and normalize messy order data with deduplication
2. Plan optimal courier assignments under real-world constraints
3. Reconcile planned assignments against actual delivery logs

## Project Structure

```
ai_task/
├─ README.md
├─ ASSUMPTIONS.md
├─ AI_NOTES.md
├─ requirements.txt
├─ src/
│  ├─ __init__.py
│  ├─ main.py
│  ├─ io_utils.py
│  ├─ normalize.py
│  ├─ dedupe.py
│  ├─ plan.py
│  └─ reconcile.py
├─ inputs/            # put your real inputs here (not overwritten by tests)
│  ├─ orders.json
│  ├─ couriers.json
│  ├─ zones.csv
│  └─ log.csv
├─ outputs/           # program writes clean_orders.json, plan.json, reconciliation.json
├─ scripts/
│  └─ run_tests.py
└─ tests/
   ├─ test1/  # Dedupe + Late + Unexpected + Misassigned
   ├─ test2/  # Capacity & Exclusions (planning)
   ├─ test3/  # Duplicate scans (reconciliation)
   └─ test4/  # Zone normalization ("6 Oct", "6th of Oct.", "6 October" → "6th of October")
```

## Requirements

- **Python 3.9+**
- **No external dependencies** (uses Python standard library only)
- **Windows, macOS, and Linux compatible**

## Quick Start

### 1. Setup (Windows)

```bat
REM Clone or extract the project
cd ai_task

REM Optional: Create virtual environment
py -3 -m venv .venv
call .venv\Scripts\activate

REM Install dependencies (none required, but for consistency)
pip install -r requirements.txt
```

### 2. Setup (macOS/Linux)

```bash
# Clone or extract the project
cd ai_task

# Optional: Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies (none required, but for consistency)
pip install -r requirements.txt
```

### 3. Prepare Input Files

Place your input files in the `inputs/` directory:
- `orders.json` - Array of orders with potential duplicates and messy data
- `couriers.json` - Array of courier configurations with zones, constraints, and capacities
- `zones.csv` - Canonical mapping for city/zone normalization
- `log.csv` - Actual delivery scan records

### 4. Run the Program

**Windows:**
```bat
python -m src.main --inputs inputs --outputs outputs
```

**macOS/Linux:**
```bash
python -m src.main --inputs inputs --outputs outputs
```

### 5. View Results

The program generates three output files in the `outputs/` directory:
- `clean_orders.json` - Normalized and deduplicated orders
- `plan.json` - Courier assignments with capacity usage
- `reconciliation.json` - Comparison between plan and actual delivery log

## Input File Schemas

### orders.json
```json
[
  {
    "orderId": " Ord-001 ",
    "city": "6th of October",
    "zoneHint": "6 October- El Montazah",
    "address": "6 Oct - El Montazh,, st. 12",
    "paymentType": "COD",
    "productType": "fragile",
    "weight": 2,
    "deadline": "2025-08-12 16:30"
  }
]
```

### couriers.json
```json
[
  {
    "courierId": "Bosta",
    "zonesCovered": ["6th of October", "Giza"],
    "acceptsCOD": true,
    "exclusions": ["fragile"],
    "dailyCapacity": 3,
    "priority": 2
  }
]
```

### zones.csv
```csv
raw,canonical
"6 October","6th of October"
"6th of Oct.","6th of October"
"El Montazah","El Montazah"
"Dokki","Dokki"
"Giza","Giza"
```

### log.csv
```csv
Ord-001,BOSTA,2025-08-12 16:31
ORD-002,Weevo,2025-08-12 17:10
```

## Output File Schemas

### clean_orders.json
```json
{
  "orders": [
    {
      "orderId": "ORD-001",
      "city": "6th of October",
      "zoneHint": "El Montazah",
      "address": "6 Oct - El Montazah, st. 12",
      "paymentType": "COD",
      "productType": "fragile",
      "weight": 2,
      "deadline": "2025-08-12 16:30"
    }
  ],
  "warnings": [
    "ORD-001: conflicting addresses -> kept '6 Oct - El Montazah, st. 12'"
  ]
}
```

### plan.json
```json
{
  "assignments": [
    {"orderId": "ORD-001", "courierId": "Weevo"},
    {"orderId": "ORD-002", "courierId": "Weevo"}
  ],
  "unassigned": [
    {"orderId": "ORD-003", "reason": "no_supported_courier_or_capacity"}
  ],
  "capacityUsage": [
    {"courierId": "Bosta", "totalWeight": 0},
    {"courierId": "SafeShip", "totalWeight": 0},
    {"courierId": "Weevo", "totalWeight": 5}
  ]
}
```

### reconciliation.json
```json
{
  "missing": [],
  "unexpected": ["ORD-999"],
  "duplicate": [],
  "late": ["ORD-001"],
  "misassigned": ["ORD-001"],
  "overloadedCouriers": []
}
```

## Running Tests

The project includes automated tests for the public mini-test cases:

**Windows:**
```bat
python scripts\run_tests.py
```

**macOS/Linux:**
```bash
python scripts/run_tests.py
```

### Test Cases

- **test1**: Deduplication + Late delivery + Unexpected order + Misassignment detection
- **test2**: Capacity constraints + Product exclusions in planning
- **test3**: Duplicate scan detection in reconciliation
- **test4**: Zone normalization (various "6 October" variants → "6th of October")

## Command Line Options

```bash
python -m src.main [OPTIONS]

Options:
  --inputs DIR    Input directory containing the 4 required files (default: inputs)
  --outputs DIR   Output directory for results (default: outputs)
  -h, --help      Show help message
```

## Key Features

### Data Normalization
- **Order IDs**: Trimmed, uppercased, normalized to `LETTERS-DIGITS` format
- **Cities/Zones**: Canonicalized using `zones.csv` with fuzzy matching tolerance
- **Payment Types**: Standardized to `COD` or `Prepaid`
- **Product Types**: Normalized to `fragile` or `standard`
- **Weights**: Coerced to numeric values
- **Deadlines**: Supports both `YYYY-MM-DD HH:MM` and `YYYY/MM/DD HH:MM` formats

### Intelligent Deduplication
- Groups orders by normalized order ID
- Resolves conflicts by preferring non-empty fields
- Uses earliest deadline when multiple deadlines exist
- Detects similar addresses using edit distance algorithms
- Generates warnings for data conflicts

### Constraint-Aware Planning
- Validates courier zone coverage (city OR zoneHint)
- Enforces payment type compatibility (COD acceptance)
- Respects product exclusions (fragile handling)
- Tracks daily capacity by weight sum
- Applies deterministic tie-breakers: priority → current load → courier ID

### Comprehensive Reconciliation
- **Missing**: Planned orders not delivered
- **Unexpected**: Delivered orders not in clean data
- **Duplicates**: Orders scanned multiple times
- **Late**: Deliveries after deadline
- **Misassigned**: Wrong courier or infeasible courier used
- **Overloaded**: Couriers exceeding their daily capacity

## Determinism Guarantees

- All output arrays are alphabetically sorted
- Fixed tie-breaking rules for consistent planning
- No randomness or external API calls
- Reproducible results across runs

## Error Handling

- Graceful handling of malformed data
- Detailed warnings for data quality issues
- Fallback values for missing or invalid fields
- Comprehensive validation of input schemas

## Performance

- Optimized for typical logistics datasets (thousands of orders)
- Memory-efficient processing
- Fast fuzzy matching with early termination
- Linear time complexity for most operations

## Troubleshooting

### Common Issues

1. **File not found errors**: Ensure all 4 input files exist in the specified directory
2. **JSON parsing errors**: Validate JSON syntax in input files
3. **CSV format issues**: Ensure zones.csv has proper headers and quotes
4. **Permission errors**: Check write permissions for output directory

### Debugging

Enable verbose logging by modifying the main function or check:
- `clean_orders.json` for data normalization results
- Warnings array for data quality issues
- Console output for processing status

## Dependencies

This project uses only Python standard library modules:
- `json` - JSON file processing
- `csv` - CSV file parsing
- `datetime` - Date/time parsing and comparison
- `pathlib` - Cross-platform file path handling
- `re` - Regular expression pattern matching
- `difflib` - Fuzzy string matching
- `argparse` - Command-line argument parsing
- `collections` - Data structures (defaultdict)

No external packages or internet connectivity required.