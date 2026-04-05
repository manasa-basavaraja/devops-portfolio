from pyspark.sql import functions as F

# Flattening a list/array into multiple rows
df_flat = df.withColumn("product", F.explode(F.col("purchased_items")))

# Aggregating the flattened data
df_counts = df_flat.groupBy("product").count().orderBy(F.desc("count"))

# PIVOT: Rows to Columns
pivot_df = df.groupBy("date").pivot("metric_name").sum("value")

# UNPIVOT (Stack): Columns to Rows (Commonly asked as "How to reverse a pivot")
unpivot_df = pivot_df.select(
    "date", 
    F.expr("stack(2, 'MetricA', MetricA, 'MetricB', MetricB) as (metric_name, value)")
)