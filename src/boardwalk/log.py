"""
Logger code
"""
import logging
import sys

logging.basicConfig(
    format="%(levelname)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
    level=logging.INFO,
)

boardwalk_logger = logging.getLogger("boardwalk")
