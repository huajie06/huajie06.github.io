# pyright: reportMissingImports=false
import yaml
import polars as pl


# class for normalization (renaming and casting)
class DataHarmonizer:
    def __init__(self, schema_path: str):
        self.schema = self._load_schema(schema_path).get("schema", {})
        # map string types to actual polars types for casting
        # TODO: be more precise if desired type to be: `int8` in the schema file
        self.type_map = {
            "string": pl.String,
            "float": pl.Float64,
            "integer": pl.Int64,
            "date": pl.Date,
            "boolean": pl.Boolean,
        }

    def _load_schema(self, schema_path):
        try:
            with open(schema_path, "r") as f:
                return yaml.safe_load(f)
        except Exception as e:
            raise ValueError(f"Failed to load schema: {e}")

    def harmonize(self, df: pl.DataFrame):
        report_logs = []

        # 1. column renaming based on aliases
        rename_map = {}
        df_cols = set(df.columns)

        for col, props in self.schema.items():
            if col not in df_cols:
                # check if any alias exists in the dataframe
                aliases = props.get("aliases", [])
                for alias in aliases:
                    if alias in df_cols:
                        rename_map[alias] = col
                        report_logs.append(
                            {
                                "action": "Rename",
                                "column": col,
                                "details": f"Renamed from '{alias}'",
                            }
                        )
                        break  # stop after finding first match

        if rename_map:
            df = df.rename(rename_map)

        # 2. type casting, performs on already renamed df
        for col, props in self.schema.items():
            if col in df.columns:
                target_type_str = props.get("type")
                target_pl_type = self.type_map.get(target_type_str)

                if target_pl_type:
                    current_type = df[col].dtype

                    if current_type != target_pl_type:
                        # keep track of the null count; failure pattern on casting goes wrong
                        nulls_before = df[col].null_count()

                        # use strict=False forces bad values to null instead of crashing
                        df = df.with_columns(
                            pl.col(col).cast(target_pl_type, strict=False)
                        )

                        nulls_after = df[col].null_count()
                        failed_rows = nulls_after - nulls_before

                        if failed_rows > 0:
                            report_logs.append(
                                {
                                    "action": "Cast Fail",
                                    "column": col,
                                    "details": f"Failed to cast {failed_rows} rows to {target_type_str}",
                                }
                            )
                        else:
                            report_logs.append(
                                {
                                    "action": "Cast Success",
                                    "column": col,
                                    "details": f"Cast from {current_type} to {target_type_str}",
                                }
                            )

        # return the transformed df and the report
        return df, pl.DataFrame(
            report_logs,
            schema={"action": pl.String, "column": pl.String, "details": pl.String},
        )


class DataValidator:
    def __init__(self, schema_path: str):
        self.schema = self._load_schema(schema_path).get("schema", {})
        self.polars_dtypes = {
            "string": [pl.String, pl.Categorical, pl.Enum],
            "float": [pl.Float32, pl.Float64, pl.Decimal],
            "integer": [
                pl.Int8,
                pl.Int16,
                pl.Int32,
                pl.Int64,
                pl.UInt8,
                pl.UInt16,
                pl.UInt32,
                pl.UInt64,
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
        """helper to get up to 3 unique examples."""
        try:
            invalid_vals = invalid_df[col_name].unique().to_list()
            invalid_vals = [v for v in invalid_vals if v is not None]

            count = len(invalid_vals)
            examples = invalid_vals[:3]
            example_str = ", ".join(map(str, examples))

            if count > 3:
                return f"{example_str}, ... (+{count - 3} more)"
            return example_str
        except Exception as e:
            print(f"no example found: {e}")
            return "N/A"

    def validate(self, df: pl.DataFrame) -> pl.DataFrame:
        errors = []

        for col, props in self.schema.items():
            if col not in df.columns:
                if not props.get("optional", False):
                    errors.append(
                        {
                            "variable": col,
                            "check": "Existence",
                            "description": "Column not found",
                            "examples": "N/A",
                        }
                    )
                continue

            col_expr = pl.col(col)

            # type check
            expected_key = props.get("type")
            actual_dtype = df[col].dtype

            if expected_key in self.polars_dtypes:
                valid_types = self.polars_dtypes[expected_key]
                # check if actual type is in the allowed list for that key
                if actual_dtype not in valid_types:
                    errors.append(
                        {
                            "variable": col,
                            "check": "Type",
                            "description": f"Expected {expected_key}, got {actual_dtype}",
                            "examples": "N/A",
                        }
                    )

            # range check
            if "range" in props:
                low, high = props["range"]
                invalid = df.filter((col_expr < low) | (col_expr > high))
                if not invalid.is_empty():
                    errors.append(
                        {
                            "variable": col,
                            "check": "Range",
                            "description": f"{len(invalid)} rows outside [{low}, {high}]",
                            "examples": self._get_example_msg(invalid, col),
                        }
                    )

            # allowed values (whitelist)
            if "allowed_value" in props:
                allowed = props["allowed_value"]
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
                            "variable": col,
                            "check": "Allowed Values",
                            "description": f"{len(invalid)} rows have invalid values",
                            "examples": self._get_example_msg(invalid, col),
                        }
                    )

            # not allowed values (blacklist)
            if "not_allowed_value" in props:
                forbidden = props["not_allowed_value"]
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
                            "variable": col,
                            "check": "Forbidden Values",
                            "description": f"{len(invalid)} rows found in blacklist",
                            "examples": self._get_example_msg(invalid, col),
                        }
                    )

            #regex check
            if "regex" in props:
                pattern = props["regex"]
                # [ensure we only regex on strings
                if actual_dtype == pl.String:
                    invalid = df.filter(~col_expr.str.contains(pattern))
                    if not invalid.is_empty():
                        errors.append(
                            {
                                "variable": col,
                                "check": "Regex",
                                "description": f"{len(invalid)} rows mismatch pattern '{pattern}'",
                                "examples": self._get_example_msg(invalid, col),
                            }
                        )

        # return a dataframe
        schema = {
            "variable": pl.String,
            "check": pl.String,
            "description": pl.String,
            "examples": pl.String,
        }
        return pl.DataFrame(errors, schema=schema)


def print_report(title, df_report):
    width = 60
    print("\n" + "=" * width)
    print(f"{title:^60}")
    print("=" * width + "\n")

    if df_report.is_empty():
        print("No issues found.")
    else:
        with pl.Config(
            tbl_formatting="ASCII_MARKDOWN",
            tbl_hide_column_data_types=True,
            tbl_rows=-1,
            fmt_str_lengths=100,
        ):
            print(df_report)
    print("\n")


def main():
    # 1. path to data
    data_path = "../data/train.parquet"
    schema_path = "data_schema.yaml"

    # 2. initialize
    harmonizer = DataHarmonizer(schema_path)
    validator = DataValidator(schema_path)

    # 3. load Data
    print(f"Loading {data_path}...")
    df = pl.read_parquet(data_path)

    df.columns = [col.lower() for col in df.columns]

    # 4. step 1: rename & cast
    # run harmonization
    df_clean, harm_report = harmonizer.harmonize(df)
    print_report("HARMONIZATION REPORT (Renaming & Casting)", harm_report)

    # 5. step 2: validate (ranges & logic)
    error_df = validator.validate(df_clean)
    print_report("VALIDATION REPORT (Logic & Quality)", error_df)

    # 6. step 3: output sample
    # default 10% sampling
    sample_fraction = 0.1

    # handle small datasets gracefully (take at least 5 rows or all if small)
    n_rows = len(df_clean)
    if n_rows < 50:
        df_sample = df_clean
    else:
        df_sample = df_clean.sample(fraction=sample_fraction, seed=42)

    print(f"Original Row Count: {n_rows}")
    print(f"Sampled Row Count:  {len(df_sample)} (approx {sample_fraction * 100}%)")

    # df_sample.write_parquet("clean_sample.parquet")
    print("Sample dataset ready.")


if __name__ == "__main__":
    main()
