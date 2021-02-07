# noinspection PyUnresolvedReferences
from datetime import datetime
from typing import Optional

import owncloud
from random import choice
import json
class Quotes:
    def __init__(self, oc: owncloud, quotes_path: str):
        self.oc = oc
        self.quotes_path = quotes_path
        self.quotes_last_download = None
        self.quotes = []
        self.authors = {}

    def _download(self):
        if self.quotes_last_download is not None and self._timestamp_now() - self.quotes_last_download < 60*60*48:
            return self

        self.quotes = json.loads(self.oc.get_file_contents(self.quotes_path).decode('utf-8'))

        self.quotes_last_download = self._timestamp_now()

        print("Downloaded quotes")

        for quote in self.quotes:
            if "author" in quote:
                for author in quote["author"].split('/'):
                    author: str
                    author = self._normalize_author(author)
                    if author not in self.authors:
                        self.authors[author] = {}
                    self.authors[author] += quote

        return self

    @staticmethod
    def _timestamp_now() -> float:
        return datetime.now().timestamp()

    def get_random_quote(self, author: Optional[str]=None):
        self._download()

        if author is None:
            q = self.quotes
        else:
            q = self.authors.get(self._normalize_author(author), {})
            if len(q) <= 0:
                return None, None, None

        return self._format_quote(choice(q))

    @staticmethod
    def _normalize_author(author):
        author = ''.join(filter(str.isalnum, author.strip().lower()))
        return author

    @staticmethod
    def _format_quote(json_quote):
        quote = json_quote["quote"] if "quote" in json_quote else None
        author = json_quote["author"] if "author" in json_quote else None
        context = json_quote["context"] if "context" in json_quote else None

        if author and quote:
            return quote, author, context
        return None, None, None

    def _get_quote_at(self, pos: int):
        if pos < 0 or pos >= len(self.quotes):
            return None
        return self._format_quote(self.quotes[pos])

    def delete_cache(self) -> int:
        lines = len(self.quotes)

        self.quotes = []
        self.authors = {}
        self.quotes_last_download = None

        return lines
