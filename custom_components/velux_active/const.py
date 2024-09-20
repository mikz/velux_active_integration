"""Constants for the velux_active integration."""

import logging

LOGGER = logging.getLogger(__package__)

DOMAIN = "velux_active"

API_URL = "https://app.velux-active.com"
OAUTH2_TOKEN = f"{API_URL}/oauth2/token"

OAUTH2_CLIENT_ID = "5931426da127d981e76bdd3f"
OAUTH2_CLIENT_SECRET = "6ae2d89d15e767ae5c56b456b452d319"