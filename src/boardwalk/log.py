"""
Logger code
"""
import logging
import sys

logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler(sys.stdout)])

boardwalk_logger = logging.getLogger("boardwalk")
