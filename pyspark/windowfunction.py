from pyspark.sql import SparkSession
from pyspark.sql.window import Window
from pyspark.sql.functions import row_number, col

spark = SparkSession.builder.appName("DedupLatestRecord").getOrCreate()

# Sample Data
data = [
    (101, "Alice", "2024-01-01"),
    (101, "Alice", "2024-03-01"),
    (102, "Bob", "2024-02-15"),
    (102, "Bob", "2024-01-10")
]

df = spark.createDataFrame(data, ["customer_id", "name", "updated_at"])

# Window Spec
window_spec = Window.partitionBy("customer_id").orderBy(col("updated_at").desc())

# Deduplicate
latest_df = (
    df.withColumn("rn", row_number().over(window_spec))
      .filter(col("rn") == 1)
      .drop("rn")
)

latest_df.show()