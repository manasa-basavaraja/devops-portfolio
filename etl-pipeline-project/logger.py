import logging

def get_logger():
    logger = logging.getLogger("etl_pipeline")

    if not logger.handlers:
        logger.setLevel(logging.INFO)

        ch = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s"
        )
        ch.setFormatter(formatter)

        logger.addHandler(ch)

    return logger