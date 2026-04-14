import pandas as pd
import boto3
from datetime import datetime

def run_etl():
    # Sample data (replace with API later if needed)
    data = {
        "name": ["Manasa", "DevOps"],
        "role": ["Engineer", "Pipeline"]
    }

    df = pd.DataFrame(data)

    file_name = f"output_{datetime.now().strftime('%Y%m%d%H%M%S')}.csv"

    s3 = boto3.client('s3')
    s3.put_object(
        Bucket="devops-etl-demo-bucket",
        Key=f"data/{file_name}",
        Body=df.to_csv(index=False)
    )

    print("ETL job completed and uploaded to S3")

if __name__ == "__main__":
    run_etl()
    