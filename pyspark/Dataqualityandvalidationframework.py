from pyspark.sql import functions as F

def validate_data(df, key_col="id", amount_col="sales_amount"):
    # 1. Null counts per column (fixed logic)
    null_counts = df.select([
        F.sum(F.col(c).isNull().cast("int")).alias(c)
        for c in df.columns
    ]).collect()[0].asDict()

    # 2. Uniqueness check for primary key
    total_rows = df.count()
    distinct_keys = df.select(key_col).distinct().count()
    is_unique = (total_rows == distinct_keys)

    # 3. Negative values check
    invalid_sales = df.filter(F.col(amount_col) < 0).count()

    # 4. Optional: flag rows with ANY nulls (useful in pipelines)
    rows_with_nulls = df.filter(
        F.reduce(lambda a, b: a | b, [F.col(c).isNull() for c in df.columns])
    ).count()

    return {
        "null_counts": null_counts,
        "rows_with_nulls": rows_with_nulls,
        "is_unique": is_unique,
        "invalid_sales_rows": invalid_sales,
        "total_rows": total_rows
    }

# Usage in pipeline
report = validate_data(df)

if report["invalid_sales_rows"] > 0:
    print("Alert: Negative sales values detected!")

if not report["is_unique"]:
    print("Alert: Duplicate IDs found!")

if report["rows_with_nulls"] > 0:
    print("Warning: Rows with missing values detected!")