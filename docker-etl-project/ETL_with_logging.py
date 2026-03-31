import pandas as pd
import logging
import os
from datetime import datetime

LOG_FILE = f"etl_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger()

def extract(file_path):
    try:
        logger.info(f"Starting extraction from {file_path}")
        df = pd.read_csv(file_path)
        logger.info(f"Extracted {len(df)} records")
        return df
    except Exception as e:
        logger.error(f"Error during extraction: {e}")
        raise


def transform(df):
    try:
        logger.info("Starting transformation")

        # Example transformations
        df.dropna(inplace=True)
        df.columns = [col.lower() for col in df.columns]

        if 'salary' in df.columns:
            df['salary'] = df['salary'] * 1.1  # 10% increment

        logger.info("Transformation completed")
        return df

    except Exception as e:
        logger.error(f"Error during transformation: {e}")
        raise


def load(df, output_path):
    try:
        logger.info(f"Starting load to {output_path}")

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        df.to_csv(output_path, index=False)

        logger.info(f"Loaded {len(df)} records to {output_path}")

    except Exception as e:
        logger.error(f"Error during load: {e}")
        raise

# -------------------------------
# Main ETL Pipeline
# -------------------------------
def run_etl(input_path, output_path):
    try:
        logger.info("ETL job started")

        df = extract(input_path)
        df_transformed = transform(df)
        load(df_transformed, output_path)

        logger.info("ETL job completed successfully")

    except Exception as e:
        logger.critical(f"ETL job failed: {e}")


if __name__ == "__main__":
    INPUT_FILE = "data/input.csv"
    OUTPUT_FILE = "data/output/output.csv"

    run_etl(INPUT_FILE, OUTPUT_FILE)