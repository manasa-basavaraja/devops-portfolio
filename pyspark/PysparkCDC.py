from pyspark.sql import SparkSession
from pyspark.sql.functions import col, current_timestamp, row_number
from pyspark.sql.window import Window

from delta.tables import DeltaTable  # Delta Lake

spark = SparkSession.builder \
    .appName("CDC_Upsert_Pipeline") \
    .getOrCreate()


TARGET_TABLE = "customer_silver"
PRIMARY_KEY = "customer_id"
TIMESTAMP_COL = "updated_at"



raw_df = spark.read.format("json").load("/data/bronze/customers/")


clean_df = (
    raw_df
    .filter(col(PRIMARY_KEY).isNotNull())
    .filter(col(TIMESTAMP_COL).isNotNull())
    .withColumn("ingest_time", current_timestamp())
)

# ---------------------------
# Handles late-arriving + duplicate CDC events
# ---------------------------
window_spec = Window.partitionBy(PRIMARY_KEY).orderBy(col(TIMESTAMP_COL).desc())

dedup_df = (
    clean_df
    .withColumn("rn", row_number().over(window_spec))
    .filter(col("rn") == 1)
    .drop("rn")
)

# ---------------------------
# (Only keep columns that exist in target OR new ones allowed)
# ---------------------------
if spark.catalog.tableExists(TARGET_TABLE):
    target_cols = set(spark.table(TARGET_TABLE).columns)
    incoming_cols = set(dedup_df.columns)

    # Union schema safely
    for col_name in incoming_cols - target_cols:
        dedup_df = dedup_df.withColumn(col_name, col(col_name))

# ---------------------------
# Handles:
# - Inserts
# - Updates
# - Idempotent reruns
# ---------------------------
if not spark.catalog.tableExists(TARGET_TABLE):

    dedup_df.write.format("delta") \
        .mode("overwrite") \
        .saveAsTable(TARGET_TABLE)

else:

    target = DeltaTable.forName(spark, TARGET_TABLE)

    (
        target.alias("t")
        .merge(
            dedup_df.alias("s"),
            f"t.{PRIMARY_KEY} = s.{PRIMARY_KEY}"
        )
        .whenMatchedUpdateAll(condition=f"s.{TIMESTAMP_COL} > t.{TIMESTAMP_COL}")
        .whenNotMatchedInsertAll()
        .execute()
    )

print("Records processed:", dedup_df.count())
print("Pipeline completed successfully")