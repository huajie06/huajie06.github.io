---
title: "Create equal-weight bins in Python using Numpy"
pubDate: "2025-11-18"
description: "Some recap after trying to create bins with weights in Polars"
tags: ["python", "engineering"]
---

The problem is basically trying to create bins when you have two series (or two columns), and one of them is your weight.

My problem is that one column is predicted **frequency**, and the other one is **exposure**.

```python
import polars as pl
import numpy as np

np.random.seed(42)
n_rows = 10000

df = pl.DataFrame({
    "pred": np.random.rand(n_rows),
    "exp": np.random.rand(n_rows)
}).lazy()


df_sorted = lf.select(['pred','exp']).collect().sort('pred')

cum_exp = df_sorted['exp'].cum_sum().to_numpy()
total_exp = cum_exp[-1]

# this will give 10%, 20% and ..., at that x% what is the weight
target_cum_weight = np.linspace(0, total_exp, 10 + 1)

# now we just need to find the index of that weight value
indices = np.searchsorted(cum_exp, target_cum_weight)

# well, but we actually need the pred-value, not the weight
break_points = df_sorted.select(['pred'])[indices].to_list()

(
    df.with_columns(
        pl.col('pred')
        .cut(breaks=break_points[1:-1]
        ,labels=[f'decile_{i:02d}' for i in range(10 + 1)])
        .alias('decile')
    ).groupby('decile')
    .agg(
        pl.len().alias('count'),
        pl.col('pred').sum().alias('total_pred'),
        pl.col('exp').sum().alias('total_exp'),
    ).collect()
    .sort('decile')
)
```

This should give a equal weighted bins. Similarly, this can be done by use `numpy.interp`. The idea is to solve the **equation**.

```python

# similar code before

cum_weight = np.cumsum(sorted_exp)
start_weight = cum_weight[0]
end_weight = cum_weight[-1]

# define the target weights, the y-axis values
target_weights = np.linspace(start_weight, end_weight, 11)[1:-1]

# you need to solve for this
pred_breaks = np.interp(target_weights, cum_weight, sorted_pred)

```

First option normally is optimal, but really all the time would spend on the sort, the others are not probably small. So it's like `elephant in the room` thing.

## Another option with Polars native method

A bit update on 11/20.

Below is an example assume that trying to create a decile lift chart, with equal expsoure weight. This is a very specific use case when i'm analyzing Umbrella loss using some Auto data. So there's a loss threshold option.

```python
from typing import Union


def calculate_lift(
    lf: pl.LazyFrame,
    filter_expr: pl.Expr,
    score_col: str,
    target_col: str,
    target_col_threshold: int,
    n_bins: int = 10,
    weight_col: Union[str, None] = None,
) -> pl.DataFrame:
    """
    Calculates lift analysis metrics by binning data based on equal cumulative weight.
    """

    if weight_col is None:
        raise ValueError("weight_col must be provided for equal weight binning.")

    filtered_lf = lf.filter((filter_expr) & (pl.col(score_col).is_not_null())).with_columns(
        pl.when(pl.col(target_col) > target_col_threshold).then(1).otherwise(0).alias("cc_target")
    )

    df = (
        filtered_lf.select([score_col, target_col, weight_col, "cc_target"])
        .sort(score_col, descending=True)
        .collect()
    )

    #  assign bins based on equal weight (not equal count)
    df = df.with_columns(pl.col(weight_col).cum_sum().alias("cum_weight"))
    total_weight = df.select(pl.col(weight_col).sum()).item()

    df = df.with_columns(
        ((pl.col("cum_weight") / total_weight) * n_bins).ceil().cast(pl.Int32).alias("decile")
    )

    lift_data = df.group_by("decile").agg(
        [
            pl.col(weight_col).sum().alias("exposure"),
            (pl.col("cc_target")).sum().alias("actual"),
        ]
    )

    overall_rate = (df.select(pl.col("cc_target")).sum().item()) / total_weight

    lift_data = lift_data.with_columns(
        [
            (pl.col("actual") / pl.col("exposure")).alias("rate"),
            (pl.col("actual") / pl.col("exposure") / overall_rate).alias("lift"),
        ]
    ).sort("decile")

    lift_data = lift_data.with_columns(
        [
            pl.col("exposure").cum_sum().alias("cum_exposure"),
            pl.col("actual").cum_sum().alias("cum_actual"),
        ]
    )

    total_actual = lift_data.select(pl.col("actual").sum()).item()
    lift_data = lift_data.with_columns(
        [
            (pl.col("cum_actual") / total_actual * 100).alias("pct_captured"),
            (pl.col("cum_exposure") / pl.col("cum_exposure").max() * 100).alias("pct_population"),
        ]
    )

    return lift_data

```
