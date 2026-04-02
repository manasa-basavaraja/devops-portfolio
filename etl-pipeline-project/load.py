import pandas as pd
from sqlalchemy import create_engine

def load_data(df, config):
    target = config["target"]

    if target["type"] == "csv":
        df.to_csv(target["path"], index=False)

    elif target["type"] == "postgres":
        engine = create_engine(target["connection_string"])
        df.to_sql(target["table"], engine, if_exists="append", index=False)

    else:
        raise ValueError("Unsupported target type")