---
title: "Create equal-weight bins in Python using Numpy"
pubDate: "2025-11-18"
description: "Some recap after trying to create bins with weights in Polars"
tags: ["Python", "Engineering"]
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
