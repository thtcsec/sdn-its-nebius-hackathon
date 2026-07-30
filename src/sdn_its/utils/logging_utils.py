"""Lightweight logging helpers."""

import logging


def get_logger(name: str = "sdn_its", level: int | None = None) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("[%(asctime)s] %(levelname)s %(name)s: %(message)s", "%H:%M:%S")
        )
        logger.addHandler(handler)
    logger.setLevel(level if level is not None else logging.INFO)
    return logger
