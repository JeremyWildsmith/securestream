import time
from typing import Dict

import requests
import urllib.parse
import sys


class ControllerModel:
    RETRY_DELAY = 30
    CACHE_LIFE = 1

    def __init__(self, endpoint):
        self.endpoint = endpoint
        self.retry = 0
        self.next_req = 0
        self.cache = dict()

    def post_delta(self, key: str):
        try:
            r = requests.post(urllib.parse.urljoin(self.endpoint, "/statistics"), json={key: 1})

            if r.status_code != 200:
                print(sys.stderr, "Error posting statistics to controller.")
        except Exception as e:
            print(sys.stderr, f"Error posting statistics to controller: {e}")

    def get_config(self, key: str, default: any) -> any:
        if self.next_req > time.time():
            return self.cache.get(key, default)

        if time.time() > self.retry:
            try:
                r = requests.get(urllib.parse.urljoin(self.endpoint, "/config"))

                if r.status_code != 200:
                    print(sys.stderr, f"Error communicating with controller. Will retry in 30 seconds. ({r.content})")
                    self.retry = time.time() + ControllerModel.RETRY_DELAY
                    return default

                self.cache = r.json()
                self.next_req = time.time() + ControllerModel.CACHE_LIFE
                return self.cache.get(key, default)
            except Exception as e:
                print(sys.stderr, f"Error reaching controller. Will retry in 30 seconds. ({e})")
                self.retry = time.time() + ControllerModel.RETRY_DELAY

        return default
