import logging
import os
from colorama import init

__author__ = """Luca Fabbri"""
__email__ = "l.fabbri@bopen.eu"


LOGGER = logging.getLogger("haunts")

if os.environ.get("DEBUG"):
    LOGGER.setLevel(logging.DEBUG)

init()
