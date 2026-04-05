from pyspark.sql import functions as F

def validate_data(df):
    # Check for Nulls in critical columns
    null_counts = df.select([F.count(F.when(F.col(c).isNull(), c)).alias(c) for c in df.columns])
    
    # Check for Uniqueness (Primary Key check)
    is_unique = df.count() == df.select("id").distinct().count()
    
    # Check for Negative Values in Sales/Amount
    invalid_sales = df.filter(F.col("sales_amount") < 0).count()
    
    return {"is_unique": is_unique, "invalid_rows": invalid_sales}

# Usage in a pipeline
report = validate_data(df)
if report["invalid_rows"] > 0:
    print("Alert: Data quality issue detected!")