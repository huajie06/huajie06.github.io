# pyright: reportMissingImports=false
import pytest
import polars as pl
import yaml


@pytest.fixture(scope="session", autouse=True)
def set_polars_display_settings():
    pl.Config.set_ascii_tables(True)  # Turns ┌── into +--
    pl.Config.set_tbl_rows(20)


with open("schema.yaml") as f:
    SCHEMA = yaml.safe_load(f)


@pytest.fixture(scope="session")
def df():
    try:
        return pl.read_parquet("sample_data.parquet")
    except Exception as e:
        pytest.fail(f"test fail due to {e}")


def get_pl_dtype(type_str):
    pl_dtype_map = {
        "int": [pl.Int8, pl.Int16, pl.Int32, pl.Int64, pl.Int128],
        "string": [pl.Categorical, pl.Utf8],
        "float": [pl.Float16, pl.Float32, pl.Float64],
        "bool": [pl.Boolean],
    }

    return pl_dtype_map.get(type_str, None)


dtype_cases = [(col, props) for col, props in SCHEMA["columns"].items()]


@pytest.mark.parametrize("col, props", dtype_cases)
def test_column_presence_type(col, props, df):
    assert col in df.columns, f"column missing: {col}"

    expected_dtype = get_pl_dtype(props["dtype"])
    actual_dtype = df[col].dtype

    if expected_dtype is None:
        raise ValueError(f"column {col} type in schema file is not found in mapping")

    assert (
        actual_dtype in expected_dtype
    ), f"column type mismatch: {col}, should be {expected_dtype}, got {actual_dtype}"


def get_rules(rule_name):
    return [
        (col, props[rule_name])
        for col, props in SCHEMA["columns"].items()
        if rule_name in props
    ]


@pytest.mark.parametrize("col, min_val", get_rules("min"))
def test_min_val(df, col, min_val):
    actual = df[col].min()
    assert (
        actual >= min_val
    ), f"Column '{col}' failed min check. Found {actual}, expected >= {min_val}"


@pytest.mark.parametrize("col, max_val", get_rules("max"))
def test_max_val(df, col, max_val):
    actual = df[col].max()
    assert (
        actual <= max_val
    ), f"Column '{col}' failed max check. Found {actual}, expected <= {max_val}"


nullable_cases = [
    (col, props["nullable"])
    for col, props in SCHEMA["columns"].items()
    if "nullable" in props and props["nullable"] is False
]


@pytest.mark.parametrize("col, is_nullable", nullable_cases)
def test_no_nulls_allowed(df, col, is_nullable):
    null_count = df[col].null_count()
    assert (
        null_count == 0
    ), f"Column '{col}' must not contain nulls (nullable:{is_nullable}). Found {null_count} nulls."


unique_cases = [
    col for col, props in SCHEMA["columns"].items() if props.get("unique") is True
]


@pytest.mark.parametrize("col", unique_cases)
def test_uniqueness(df, col):
    assert (
        df[col].is_unique().all()
    ), f"Column '{col}' contains duplicates, but spec requires unique values."


@pytest.mark.parametrize("col, range", get_rules("range"))
def test_range(df, col, range):
    expected_min = range[0]
    expected_max = range[1]
    actual_min = df[col].min()
    actual_max = df[col].max()
    assert (
        actual_min >= expected_min and actual_max <= expected_max
    ), f"column: {col} out of range. expected range: [{expected_min},{expected_max}], got: [{actual_min},{actual_max}]"


@pytest.mark.parametrize("col, allowed_values", get_rules("allowed_values"))
def test_allowed_values(df, col, allowed_values):
    expected_values = set(allowed_values)
    actual_values = set(df[col].unique())
    missings = actual_values - expected_values

    assert (
        len(missings) == 0
    ), f"column: {col}, has not allowed values. expected: {expected_values}, got: {actual_values}"
