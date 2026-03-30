import pandas as pd 

def extract():
    print("Extracting data")
    data = {
        "name":["John","Alice","Rob"],
        "age":[15,25,30],
        "group":["Junior","senior","senior"]
    }
    return pd.DataFrame(data)

def transform():
    print("Transforming data")
    df("age_plus_5") = df("age") + 5
    return df 

def load(df):
    print("Loading data")
    df.to_csv("Export.csv",index=False)
    # return()
    Print("output saved to csv")

if __name__ == "__main__":
    df = extract()
    df = transform(df)
    load(df)
