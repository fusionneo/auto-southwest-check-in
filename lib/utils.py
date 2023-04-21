import logging
import time
from enum import IntEnum
from typing import Any, Dict

import requests
import os
import json

BASE_URL = "https://mobile.southwest.com/api/"
logger = logging.getLogger(__name__)

def get_airport_code(city: str):
    pass

AIRPORTS_FILE_PATH = "utils/airport_stations.json"

def make_request(
    method: str, site: str, headers: Dict[str, Any], info: Dict[str, str], max_attempts=20
) -> Dict[str, Any]:
    url = BASE_URL + site

    # In the case that your server and the Southwest server aren't in sync,
    # this requests multiple times for a better chance at success when checking in
    attempts = 1
    while attempts <= max_attempts:
        if method == "POST":
            response = requests.post(url, headers=headers, json=info)
        else:
            response = requests.get(url, headers=headers, params=info)

        if response.status_code == 200:
            logger.debug("Successfully made request after %d attempts", attempts)
            return response.json()

        attempts += 1
        time.sleep(0.5)

    error = response.reason + " " + str(response.status_code)
    logger.debug("Failed to make request: %s", error)
    raise RequestError(error)

def get_airport_code(city: str):
    project_dir = os.path.dirname(os.path.dirname(__file__))
    file_directory = project_dir + "/" + AIRPORTS_FILE_PATH
    with open(file_directory, encoding="utf-8") as aps:
        airports = json.load(aps)
    
    for airport in airports["airStations"]:
        if airport["stationName"] == city:
            airport_code = airport["id"]
            return airport_code


# Make a custom exception when a request fails
class RequestError(Exception):
    pass


# Make a custom exception when a login fails
class LoginError(Exception):
    pass


class NotificationLevel(IntEnum):
    INFO = 1
    ERROR = 2
