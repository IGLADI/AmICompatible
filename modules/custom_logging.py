import functools
import logging
import os
import sys
from datetime import datetime
from logging import Logger


def log(func):
    """
    A decorator that logs the function call details to a logger.

    Args:
        func: The function to be decorated.

    Returns:
        The decorated function.
    """

    @functools.wraps(func)
    def wrapper(*args, logger: Logger, **kwargs):
        logger.debug(f"Calling {func.__name__} with args: {args} and kwargs: {kwargs}")
        return func(*args, logger=logger, **kwargs)

    return wrapper


def setup_logger(
    log_file: str,
    log_level: str,
    logger_name: str | None = None,
    secondary_log_file: str | None = None,
) -> logging.Logger:
    """
    Set up a logger with specified file and log level.

    Args:
        log_file: Path to the log file.
        log_level: Logging level (e.g., 'DEBUG', 'INFO').
        logger_name: Optional name for the logger.
        secondary_log_file: Optional path to a secondary log file.

    Returns:
        Configured logger instance.
    """
    logger = logging.getLogger(logger_name)
    # remove default logger
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    logger.setLevel(logging.DEBUG)

    # cli output
    stream_handler = logging.StreamHandler(sys.stdout)
    log_level = getattr(logging, log_level.upper())
    stream_handler.setLevel(log_level)

    # file output
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    if secondary_log_file:
        secondary_file_handler = logging.FileHandler(secondary_log_file)
        secondary_file_handler.setLevel(logging.DEBUG)

    formatter = logging.Formatter("%(levelname)s: %(message)s")
    stream_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)
    if secondary_log_file:
        secondary_file_handler.setFormatter(formatter)

    logger.addHandler(stream_handler)
    logger.addHandler(file_handler)
    if secondary_log_file:
        logger.addHandler(secondary_file_handler)
    return logger


def create_log_folder(base_dir: str) -> str:
    """
    Create a log folder with the current timestamp.

    Args:
        base_dir: Base directory for the log folder.

    Returns:
        Path to the created log folder.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_folder = os.path.join(base_dir, timestamp)
    # expand ~ in path
    log_folder = os.path.expanduser(log_folder)
    os.makedirs(log_folder, exist_ok=True)
    print(f"Created log folder: {log_folder}")
    return log_folder
