def transform_data(df):
    df = df.copy()

    # Example transformations
    df.columns = [col.lower().strip() for col in df.columns]

    if "salary" in df.columns:
        df["salary"] = df["salary"].fillna(0)

    # Derived column
    if "first_name" in df.columns and "last_name" in df.columns:
        df["full_name"] = df["first_name"] + " " + df["last_name"]

    return df