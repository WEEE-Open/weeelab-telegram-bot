# noinspection PyUnresolvedReferences
import owncloud
from _datetime import datetime, time
import pytz
import json


class Quotes:
    def __init__(self, oc: owncloud, quotes_path: str):
        self.oc = oc
        self.local_tz = pytz.timezone("Europe/Rome")
        self.quotes_path = quotes_path
        self.quotes_last_download = None
        self.quotes = []

    def get_quotes(self):
        if self.quotes_last_download is not None and time() - self.quotes_last_download < 60*60*48:
            return self

        self.quotes = json.loads(self.oc.get_file_contents(self.quotes_path).decode('utf-8'))

        self.quotes_last_download = time()

        return self

    def delete_cache(self) -> int:
        lines = len(self.quotes)

        self.quotes = []
        self.quotes_last_download = None

        return lines
