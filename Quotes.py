# noinspection PyUnresolvedReferences
from datetime import datetime
from typing import Optional

import owncloud
import random
import json
class Quotes:
    def __init__(self, oc: owncloud, quotes_path: str, demotivational_path: str, games_path: str):
        self.oc = oc
        self.quotes_path = quotes_path
        self.game_path = games_path
        self.demotivational_path = demotivational_path

        self.quotes = []
        self.game = {}
        self.authors = {}
        self.authors_for_game = {}
        self.authors_weights_for_game = {}
        self.demotivational = []

        self.quotes_last_download = None
        self.demotivational_last_download = None

    def _download(self):
        if self.quotes_last_download is not None and self._timestamp_now() - self.quotes_last_download < 60*60*48:
            return self

        self.quotes = json.loads(self.oc.get_file_contents(self.quotes_path).decode('utf-8'))
        self.quotes_last_download = self._timestamp_now()

        authors_count_for_game = {}
        for quote in self.quotes:
            if "author" in quote:
                parts = quote["author"].split('/')
                for author in parts:
                    author: str
                    author_not_normalized = author.strip()
                    author = self._normalize_author(author)
                    if author not in self.authors:
                        self.authors[author] = []
                        # dicts also keep insertion order from Python 3.7, which is important later
                        self.authors_for_game[author] = author_not_normalized
                        self.authors_weights_for_game[author] = 0
                    self.authors[author].append(quote)
                    if len(parts) == 1 and ("game" not in quote or quote["game"] != False):
                        self.authors_weights_for_game[author] += 1

        loop_on_this = list(self.authors_weights_for_game.keys())
        for author in loop_on_this:
            if self.authors_weights_for_game[author] <= 5:
                del self.authors_for_game[author]
                del self.authors_weights_for_game[author]

        print(f"There are {len(self.authors_for_game)} authors for THE GAME: {self.authors_for_game.values()}")

        return self

    def _download_demotivational(self):
        if self.demotivational_last_download is not None and self._timestamp_now() - self.demotivational_last_download < 60*60*48:
            return self

        self.demotivational = self.oc.get_file_contents(self.demotivational_path).decode('utf-8').split("\n")
        self.demotivational_last_download = self._timestamp_now()

        return self

    def _download_game(self):
        if len(self.game) <= 0:
            try:
                self.game = json.loads(self.oc.get_file_contents(self.game_path).decode('utf-8'))
            except owncloud.owncloud.HTTPResponseError as e:
                if e.status_code == 404:
                    self.oc.put_file_contents(self.game_path, json.dumps(self.game, indent=1).encode('utf-8'))
                else:
                    raise e

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
                return None, None, None, None

        return self._format_quote(random.choice(q))

    def get_game_stats(self, uid: str):
        self._init_game(uid)

        return self.game[uid]["right"], self.game[uid]["wrong"]

    def get_quote_for_game(self, uid: str):
        self._download()

        # Random quote from an allowed author
        quote, author_printable, context, game = self.get_random_quote()
        author_normalized = self._normalize_author(author_printable)
        while author_normalized not in self.authors_for_game.keys() or not game:
            quote, author_printable, context, game = self.get_random_quote()
            author_normalized = self._normalize_author(author_printable)

        # 3 other possibilites
        answers = random.sample(
            list(filter(lambda x : x != author_normalized, self.authors_for_game.keys())),
            3,
            counts=list(filter(lambda x : x != author_normalized, self.authors_weights_for_game.keys()))
        )
        # plus the right one
        answers.append(author_normalized)

        # Make them all printable
        for i in range(0, 4):
            answers[i] = self.authors_for_game[answers[i]]
        # Shuffle
        random.shuffle(answers)

        self._init_game(uid)

        self.game[uid]["current_author"] = author_printable
        #self._save_game()

        # since author_printable = '/', they're bound
        # noinspection PyUnboundLocalVariable
        return quote, context, answers

    def _init_game(self, uid: str):
        self._download_game()
        if uid not in self.game:
            self.game[uid] = {"current_author": None, "right": 0, "wrong": 0}

    def answer_game(self, uid: str, answer: str):
        self._init_game(uid)

        if self.game[uid]["current_author"] is None:
            return None
        elif self._normalize_author(self.game[uid]["current_author"]).strip(" ") == answer:
            self.game[uid]["current_author"] = None
            self.game[uid]["right"] += 1
            self._save_game()
            return True
        else:
            right_author = self.game[uid]["current_author"]
            self.game[uid]["current_author"] = None
            self.game[uid]["wrong"] += 1
            self._save_game()
            return right_author

    def get_demotivational_quote(self):
        self._download_demotivational()

        if len(self.demotivational) <= 0:
            return None

        return random.choice(self.demotivational)

    @staticmethod
    def _normalize_author(author):
        author = ''.join(filter(str.isalnum, author.strip().lower()))
        return author

    @staticmethod
    def normalize_author_for_game(author):
        return Quotes._normalize_author(author).strip(" ")

    @staticmethod
    def _format_quote(json_quote):
        quote = json_quote["quote"] if "quote" in json_quote else None
        author = json_quote["author"] if "author" in json_quote else None
        context = json_quote["context"] if "context" in json_quote else None
        game = True if "game" in json_quote and json_quote["game"] != False else False

        if author and quote:
            return quote, author, context, game
        return None, None, None, None

    def _get_quote_at(self, pos: int):
        if pos < 0 or pos >= len(self.quotes):
            return None
        return self._format_quote(self.quotes[pos])

    def delete_cache(self) -> int:
        lines = len(self.quotes) + len(self.game)

        self.quotes = []
        self.authors = {}
        self.game = {}
        self.authors_for_game = []
        self.demotivational = []
        self.quotes_last_download = None
        self.demotivational_last_download = None

        return lines

    def _save_game(self):
        if len(self.game) > 0:
            # indent=0 to at least have some lines, instead of no newline at all
            self.oc.put_file_contents(self.game_path, json.dumps(self.game, indent=0, separators=(',', ':')).encode('utf-8'))
