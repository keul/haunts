import logging
import os

__author__ = """Luca Fabbri"""
__email__ = "l.fabbri@bopen.eu"
__version__ = "0.1.0"


LOGGER = logging.getLogger("haunts")

if os.environ.get("DEBUG"):
    LOGGER.setLevel(logging.DEBUG)
