import logging
import os
from datetime import datetime


LOG_DIR = "logs"


def get_logger(name: str):

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    if not logger.handlers:

        handler = logging.StreamHandler()

        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
        )

        handler.setFormatter(formatter)

        logger.addHandler(handler)

    return logger

def setup_logger(name: str):

    os.makedirs(LOG_DIR, exist_ok=True)

    log_file = os.path.join(
        LOG_DIR,
        f"{name}_{datetime.now().strftime('%Y%m%d')}.log"
    )

    logger = logging.getLogger(name)

    logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger