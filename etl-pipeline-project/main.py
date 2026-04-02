import yaml
from extract import extract_data
from transform import transform_data
from load import load_data
from quality_checks import run_quality_checks
from logger import get_logger

logger = get_logger()

def run_pipeline(config_path="config.yaml"):
    try:
        logger.info("Starting ETL Pipeline")

        # Load config
        with open(config_path, "r") as file:
            config = yaml.safe_load(file)

        # Extract
        df = extract_data(config)
        logger.info(f"Extracted {len(df)} records")

        # Transform
        df_transformed = transform_data(df)
        logger.info("Transformation complete")

        # Data Quality Checks
        run_quality_checks(df_transformed)

        # Load
        load_data(df_transformed, config)

        logger.info("ETL Pipeline completed successfully")

    except Exception as e:
        logger.error(f"Pipeline failed: {str(e)}")
        raise

if __name__ == "__main__":
    run_pipeline()