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

# User email.
# Required for `--execute read`
# USER_EMAIL=<your email here>

# Preferred timezone
# Default is GMT
# TIMEZONE=Europe/Rom

# Calendar services to read events from with `--execute read`, comma separated.
# Allowed values: google, proton. Proton is used only if PROTON_CLI is set.
# Default is google,proton
# READ_FROM_SERVICES=google,proton

# Proton Calendar support for `--execute read` (optional).
# Requires proton-cli 5.4.0 or later (https://proton-cli.lerchster.dev/) installed and logged in
# (`proton account login`). Set to the proton-cli executable name or path to enable it.
# Default is empty: Proton Calendar is not used
# PROTON_CLI=proton

# Your Proton email address(es), comma separated, used to find your answer to invitations.
# Default is USER_EMAIL
# PROTON_EMAIL=<your Proton email here>

# proton-cli profile to use (optional)
# PROTON_PROFILE=

# Columns name
# PROJECT_COLUMN_NAME=Project
# SPENT_COLUMN_NAME=Spent
# ACTIVITY_COLUMN_NAME=Activity
# START_TIME_COLUMN_NAME=Start
# DETAILS_COLUMN_NAME=Details
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
