---
title: "Part 1. Building a Lightweight Data Validation Pipeline with UV and Polars"
pubDate: "2025-12-20"
description: "How to ensure data quality in legacy systems using YAML-driven validation."
tags: ["python", "data", "pipeline", "uv", "polars"]
---

## Background

Recently, I migrated a Boat Rating engine from static files (.csv/.parquet) to dynamic database connections. The primary challenge was ensuring that the data from the new sources remained consistent with the legacy expectations.

The engine uses ~100 variables and lacks modern engineering "safety nets." I didn't want to rewrite the entire architecture, so I focused on a "minimum viable update": creating a validation layer that flags issues before they hit the engine.

---

## Streamlining with UV

I used `uv` to manage the project. It removes the hassle of managing virtual environments across different servers.

Typical workflow:

```bash
uv init
uv add pandas polars
uv add --dev pytest ruff
uv run main.py

```

---

## YAML-Driven Validation

I decided to use a `.yaml` file to define the schema for our 100+ variables. This keeps the logic separate from the code and makes it easy for others to update rules.

**Key checks included:**

1. **Existence:** Is the column there?
2. **Type Match:** (e.g., Integer vs String)
3. **Range:** For numerical values.
4. **Allowed/Forbidden Values:** Using lists or regex.

### The Schema (`data_schema.yaml`)

```yaml
# example setup, uses dataset from kaggle
schema:
  id:
    type: integer
    range: [1, 200]

  mssubclass:
    type: integer
    allowed_value: [60, 20, 70, 80]

  mszoning:
    type: string
    regex: "^[A-Z]+$"

  lotfrontage:
    type: float

  lotarea:
    type: float
    range: [1, 220000]

  street:
    type: string
    optional: true

  lotshape:
    type: string
    not_allowed_value: ["IR3"]
```

### The Implementation (`validate.py`)

I built a `DataValidator` class using **Polars**. Polars is ideal here because its expression API makes range and regex checks incredibly fast.

```python

import yaml
import polars as pl

class DataValidator:
    def __init__(self, schema_path: str):
        self.schema = self._load_schema(schema_path).get("schema", {})
        self.polars_dtypes = {
            "string": [pl.String, pl.Categorical, pl.Enum],
            "float": [pl.Float32, pl.Float64, pl.Decimal],
            "integer": [
                pl.Int8, pl.Int16, pl.Int32, pl.Int64,
                pl.UInt8, pl.UInt16, pl.UInt32, pl.UInt64,
            ],
            "date": [pl.Date, pl.Datetime, pl.Duration, pl.Time],
            "boolean": [pl.Boolean],
        }

    def _load_schema(self, schema_path):
        try:
            with open(schema_path, "r") as f:
                return yaml.safe_load(f)
        except Exception as e:
            raise ValueError(f"Failed to load schema: {e}")

    def _get_example_msg(self, invalid_df: pl.DataFrame, col_name: str) -> str:
        """get up to 3 unique examples."""
        invalid_vals = invalid_df[col_name].unique().to_list()
        invalid_vals = [v for v in invalid_vals if v is not None]

        count = len(invalid_vals)
        examples = invalid_vals[:3]
        example_str = ", ".join(map(str, examples))

        if count > 3:
            return f"{example_str}, ... (+{count - 3} more)"
        return example_str

    def validate(self, df: pl.DataFrame) -> pl.DataFrame:
        errors = []

        for col_name, col_def in self.schema.items():
            if col_name not in df.columns:
                if not col_def.get("optional", False):
                    errors.append(
                        {
                            "variable": col_name,
                            "check": "Existence",
                            "description": "Column not found",
                            "examples": "N/A",
                        }
                    )
                continue

            col_expr = pl.col(col_name)

            # --- type check ---
            expected_key = col_def.get("type")
            actual_dtype = df[col_name].dtype
            if expected_key in self.polars_dtypes:
                if actual_dtype not in self.polars_dtypes[expected_key]:
                    errors.append(
                        {
                            "variable": col_name,
                            "check": "Type",
                            "description": f"Expected {expected_key}, got {actual_dtype}",
                            "examples": "N/A",
                        }
                    )

            # --- range check ---
            if "range" in col_def:
                low, high = col_def["range"]
                invalid = df.filter((col_expr < low) | (col_expr > high))
                if not invalid.is_empty():
                    errors.append(
                        {
                            "variable": col_name,
                            "check": "Range",
                            "description": f"{len(invalid)} rows outside [{low}, {high}]",
                            "examples": self._get_example_msg(invalid, col_name),
                        }
                    )

            # --- allowed values (whitelist) ---
            if "allowed_value" in col_def:
                allowed = col_def["allowed_value"]
                # :Gemini: handle string vs numeric mismatch safely
                # supposedly your yaml file should not have conflicting values...
                if (
                    any(isinstance(x, str) for x in allowed)
                    and actual_dtype != pl.String
                ):
                    check_expr = col_expr.cast(pl.String)
                else:
                    check_expr = col_expr

                invalid = df.filter(~check_expr.is_in(allowed))
                if not invalid.is_empty():
                    errors.append(
                        {
                            "variable": col_name,
                            "check": "Allowed Values",
                            "description": f"{len(invalid)} rows have invalid values",
                            "examples": self._get_example_msg(invalid, col_name),
                        }
                    )

            # --- not allowed values (blacklist) ---
            if "not_allowed_value" in col_def:
                forbidden = col_def["not_allowed_value"]
                # :Gemini: Handle String vs Numeric mismatch safely
                if (
                    any(isinstance(x, str) for x in forbidden)
                    and actual_dtype != pl.String
                ):
                    check_expr = col_expr.cast(pl.String)
                else:
                    check_expr = col_expr

                invalid = df.filter(check_expr.is_in(forbidden))
                if not invalid.is_empty():
                    errors.append(
                        {
                            "variable": col_name,
                            "check": "Forbidden Values",
                            "description": f"{len(invalid)} rows found in blacklist",
                            "examples": self._get_example_msg(invalid, col_name),
                        }
                    )

            # --- regex check ---
            if "regex" in col_def:
                pattern = col_def["regex"]
                invalid = df.filter(~col_expr.cast(pl.String).str.contains(pattern))
                if not invalid.is_empty():
                    errors.append(
                        {
                            "variable": col_name,
                            "check": "Regex",
                            "description": f"{len(invalid)} rows mismatch pattern '{pattern}'",
                            "examples": self._get_example_msg(invalid, col_name),
                        }
                    )

        schema = {
            "variable": pl.String,
            "check": pl.String,
            "description": pl.String,
            "examples": pl.String,
        }
        return pl.DataFrame(errors, schema=schema)

    def report_result(self, error_df: pl.DataFrame):
        width = 50
        title_text = "VALIDATION REPORT"
        print("\n" + "=" * width)
        print(f"{title_text:^50}")
        print("=" * width + "\n")

        if error_df.is_empty():
            print("✅ All checks passed! No errors found.")
        else:
            # :Gemini: config didn't know before - Polars to show full width, text won't cut off
            with pl.Config(
                tbl_formatting="ASCII_MARKDOWN",  # Makes it look like a nice grid
                tbl_hide_column_data_types=True,
                tbl_rows=-1,  # Show all rows
                fmt_str_lengths=100,  # Allow long strings
            ):
                print(error_df)
        print("\n")


def main():
    data_path = "./data/train.parquet"
    validator = DataValidator("data_schema.yaml")

    print(f"Loading {data_path}...")
    df = pl.read_parquet(data_path)

    df.columns = [col.lower() for col in df.columns]

    error_df = validator.validate(df)
    validator.report_result(error_df)

if __name__ == "__main__":
    main()
```

---

## Next Steps

- Would like to refactor the Python script to use Pydantic for the YAML parsing
- Mechanices to remap data columns to match the rate engine
