from pyspark.sql.window import Window
from pyspark.sql import functions as F

# Define window: Partition by user, order by date, look at last 6 rows + current row
window_spec = Window.partitionBy("user_id").orderBy("login_date")
rolling_window = window_spec.rowsBetween(-6, 0)

df_analysis = df.withColumn("prev_login", F.lag("login_date").over(window_spec)) \
                .withColumn("days_since_last", F.datediff("login_date", "prev_login")) \
                .withColumn("7d_rolling_avg", F.avg("sales").over(rolling_window))