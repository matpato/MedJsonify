import logging
import sys


def setup_logging(name='medjsonify', level=logging.INFO):
    """
    Setup logging configuration.

    Safe to call several times: the handler is added only once, and messages
    are not passed on to the root logger, so each line is printed once (also
    when the root logger has its own handler, as in Airflow or standalone mode).
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    if not logger.handlers:
        # Console handler
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)
        # Formatter
        handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        logger.addHandler(handler)

    logger.propagate = False
    return logger