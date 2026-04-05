from pyspark.sql.functions import broadcast

# Standard join triggers a Shuffle; broadcast sends the small table to all executors
# Use this when the small table is < 10MB (default) or up to a few hundred MBs
final_df = large_df.join(broadcast(small_df), "country_code", "left")