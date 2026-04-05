from pyspark.sql import functions as F

# Adding a 'salt' column to distribute the skewed key
df_skewed = df_large.withColumn("salt", (F.rand() * 10).cast("int"))

# Exploding the lookup table to match the salted keys
df_lookup_salted = df_lookup.withColumn("salt", F.explode(F.array([F.lit(i) for i in range(10)])))

# Join on both the actual key and the salt
result = df_skewed.join(df_lookup_salted, ["id", "salt"], "inner").drop("salt")