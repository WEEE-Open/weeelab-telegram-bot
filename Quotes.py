# noinspection PyUnresolvedReferences
import owncloud
from _datetime import time
from random import choice
import json

def format_quote(json_quote):
    quote = json_quote["quote"] if "quote" in json_quote else None
    author = json_quote["author"] if "author" in json_quote else None
    context = json_quote["context"] if "context" in json_quote else None

    if author and quote:
        return quote, author, context
    return None, None, None

class Quotes:
    def __init__(self, oc: owncloud, quotes_path: str):
        self.oc = oc
        self.quotes_path = quotes_path
        self.quotes_last_download = None
        self.quotes = []

    def _download(self):
        if self.quotes_last_download is not None and time() - self.quotes_last_download < 60*60*48:
            return self

        self.quotes = json.loads(self.oc.get_file_contents(self.quotes_path).decode('utf-8'))

        self.quotes_last_download = time()

        print("Downloaded quotes")

        return self

    def get_random_quote(self):
        self._download()

        return format_quote(choice(self.quotes))

    def _get_quote_at(self, pos: int):
        if pos < 0 or pos >= len(self.quotes):
            return None
        return format_quote(self.quotes[pos])

    def delete_cache(self) -> int:
        lines = len(self.quotes)

        self.quotes = []
        self.quotes_last_download = None

        return lines
