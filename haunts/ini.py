import configparser


DEFAULT_INI = """[haunts]
# The Google Sheet Document id where you register events
# Required
CONTROLLER_SHEET_DOCUMENT_ID=<Google Sheet Document Id here>

# The sheet where to assign events category names to Google Calendar ids
# Default is "config"
# CONTROLLER_SHEET_NAME=config

# Events in the day start time in HH:MM format
# Default is 09:00
# START_TIME=09:00

# Nominal working hours per day
# Default is 8
# WORKING_HOURS=8

# Overtime start date in HH:MM format
# Default is empty: no overtime
# OVERTIME_FROM=20:00
"""

parser = configparser.RawConfigParser(allow_no_value=True)


def create_default(config):
    print("Creating default configuration")
    with open(config.resolve(), "w") as f:
        f.write(DEFAULT_INI)
    print("Created")


def init(config_file):
    global configuration
    with open(config_file.resolve(), "r") as config:
        parser.read_file(config)


def get(name, default=None):
    value = parser["haunts"].get(name, default)
    if value is None and default is None:
        raise KeyError(f"Not found: {name}")
    return default if value is None else value
