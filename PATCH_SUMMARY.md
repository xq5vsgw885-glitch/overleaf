# Patch Summary: Robust CSV Delimiter Detection

## Problem Identified
The naive delimiter-test broke on semicolon-delimited files with decimal commas:
```
time;angle
0;0,0
1;2,0
2;4,0
```
With comma tried first, it parsed formally non-empty but wrong:
- Expected: 2 columns (time, angle)  
- Got: 1 column (the entire row as a single string)

## Solution: Plausibility Scoring

### New Function: `_score_delimiter(df: pd.DataFrame) -> float`
Evaluates each delimiter candidate on three criteria:
1. **Numeric columns detected** (after decimal-comma conversion): weighted +10.0 per column
2. **Completely empty columns**: penalized -5.0 per column  
3. **Non-numeric columns**: penalized -2.0 per column

Score formula:
```
score = numeric_cols * 10.0 - empty_cols * 5.0 - (num_cols - numeric_cols) * 2.0
```

### Updated `_read_table()` Logic
1. Try each delimiter (`,`, `;`, `\t`) and collect (score, delimiter, df) tuples
2. Sort by score descending; accept best if score ≥ 0
3. If no explicit delimiter works, try auto-detection
4. If all fail, raise clear 400 error: "Keine plausible Spaltenstruktur gefunden"

### Why It Works
- **Semicolon + decimal commas case**: Semicolon properly splits into 2 columns with high numeric content → high score
- **Comma case on same data**: Would split incorrectly, low numeric columns → low score, rejected
- **Robust fallback**: Auto-detection as last resort with same scoring validation
- **Clear errors**: Non-plausible data returns actionable 400 message

## Test Coverage

### New Test: `test_semicolon_delimiter_with_decimal_commas()`
```python
csv = "time;angle\n0;0,0\n1;2,0\n2;4,0\n"
```
Validates:
- ✅ `used_all_rows == True`
- ✅ `row_count == 3`
- ✅ `detected_numeric_columns` includes time and angle
- ✅ `mean(angle) ≈ 2.0`
- ✅ `regression.slope ≈ 2.0`

### Existing Tests Remain Passing
- `test_analyze_processes_all_rows_stats_and_regression` (comma-delimited)
- `test_not_computable_latitude_has_no_correction_factor`
- `test_xy_tracking_without_angle_transformation_does_not_invent_angle`
- `test_malformed_or_empty_csv_returns_clear_error`

## Constraints Preserved
✅ All 4 original tests passing  
✅ Public response schema unchanged  
✅ No raw CSV sent to generation  
✅ `used_all_rows=true` only when all rows processed  
✅ `ddof=1` in sample standard deviation  
✅ Clear 400 errors for malformed CSV  
✅ Works without `ANTHROPIC_API_KEY`  
✅ No angle invention from x/y tracking  
✅ `correction_factor_used: False` on latitude  
✅ Foucault latitude `not_computable` behavior unchanged  

## Files Changed
- **server.py**: +30 lines (new `_score_delimiter()` function, enhanced `_read_table()`)
- **tests/test_analyze.py**: +25 lines (new test case)

## Commits
1. `52ba0bb9` – "Improve CSV delimiter detection with plausibility scoring"
2. `ac2f3f95` – "Add test for semicolon delimiter with decimal commas"
