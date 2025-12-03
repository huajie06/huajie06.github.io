---
title: Use duckdb in pipeline
pubDate: "2025-12-02"
description: "Some examples to use duckdb"
tags: ["python", "data", "duckdb"]
---

Frequently I am using `pandas` and `polars` a lot, and memorying the syntax is not that bad. There's actually another package: `duckdb` where the SQL syntax can be used so that I don't need to memorize this `groupby` or `pivot` functions. (Maybe i still do but less often?)

I see myself use `duckdb` in this way

```python
import duckdb

# create an empty connection and then just querying the table
con = duckdb.connect()
con.sql("SELECT * FROM 'taxi_2019_04.parquet' LIMIT 5").show()

# or i can save it to a polars dataframe
df = con.sql("SELECT * FROM 'taxi_2019_04.parquet' LIMIT 5").pl()

# then save it to a csv file
con.sql("SELECT * FROM 'taxi_2019_04.parquet' LIMIT 5").to_csv('test.csv')
```

Some of common actions i do like check columns and their specs

```python
con.sql("DESCRIBE SELECT * FROM 'test.parquet'")

# this is like describe with stats
con.sql("SUMMARIZE SELECT * FROM 'taxi_2019_04.parquet'").show()

# or if it's parquet
con.sql("select * from parquet_schema('test.parquet')")
```

## Some workflow

`duckdb` will be better to deal with different input data files, like a mix of **database, s3, csv, and parquet**.

Then I can do something like

```python
con = duckdb.connect()

query = """
select
    a.*
    ,b.t1
    ,b.t2

    from 'test.csv' as a

    left join 'test1.parquet' as b

    on a.key1 = b.key1
    and a.key2 = b.key2

"""
df = con.sql(query).pl()
```

When there's a lot of testing flow and need to comeback at some intermediate data tables, there can be a persistent table.

```python

con = duckdb.connect('test.db', overwritten=True)

con.sql("create view v1 as select * from 'test.csv' limit 10")

con.sql("create view v2 as select * from 'test.csv' limit 3")

con.close()

# then later i can come back at it
con1 = duckdb.connect("my_analysis.db")
con1.sql("show tables").show()

```
