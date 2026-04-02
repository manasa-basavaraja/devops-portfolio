def run_quality_checks(df):
    if df.empty:
        raise ValueError("DataFrame is empty")

    if df.isnull().sum().sum() > 0:
        print("Warning: Null values found")

    if df.duplicated().sum() > 0:
        print("Warning: Duplicate records found")