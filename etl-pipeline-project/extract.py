import pandas as pd

def extract_data(config):
    source_type = config["source"]["type"]

    if source_type == "csv":
        return pd.read_csv(config["source"]["path"])

    elif source_type == "api":
        import requests
        response = requests.get(config["source"]["url"])
        return pd.DataFrame(response.json())

    else:
        raise ValueError("Unsupported source type")