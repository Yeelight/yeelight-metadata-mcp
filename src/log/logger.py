import logging
import os
from logging.handlers import TimedRotatingFileHandler

from config.config import settings


logger_name = settings.LOGGER_CONFIG.get("logger-name")
file_name = settings.LOGGER_CONFIG.get("file-name")
file_dir = settings.LOGGER_CONFIG.get("file-path")

try:
    os.makedirs(file_dir, exist_ok=True)
except PermissionError:
    file_dir = os.path.join(os.getcwd(), "logs", settings.SERVICE_NAME)
    os.makedirs(file_dir, exist_ok=True)

file_path = os.path.join(file_dir, file_name)

formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
file_handler = TimedRotatingFileHandler(file_path, when="D", interval=1, backupCount=30)
file_handler.setFormatter(formatter)
file_handler.setLevel(logging.INFO)

httpx_logger = logging.getLogger("httpx")
httpx_logger.setLevel(logging.INFO)
httpx_logger.addHandler(file_handler)


def __get_common_logger() -> logging.Logger:
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        logger.addHandler(file_handler)
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(logging.INFO)
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)
    return logger


logger = __get_common_logger()
