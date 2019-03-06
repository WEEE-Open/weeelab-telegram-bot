import datetime
import json
import re
# noinspection PyUnresolvedReferences
import owncloud
from datetime import timedelta


class WeeelabLogs:
    def __init__(self, oc: owncloud, log_path: str, log_base: str, user_path: str, user_bot_path: str):
        self.log = []
        self.log_last_update = None
        self.users = None
        self.error = None
        self.oc = oc

        self.log_path = log_path
        self.log_base = log_base
        self.user_path = user_path
        self.user_bot_path = user_bot_path

        # Logs from past months (no lines from current month)
        self.old_log = []
        # Logs start from april 2017, these variables represent which log file has been fetched last, so it will start
        # from the first one that actually exists (april 2017)
        self.old_logs_month = 3
        self.old_logs_year = 2017

    def get_log(self):
        self.log = []
        log_file = self.oc.get_file_contents(self.log_path).decode('utf-8')
        log_lines = log_file.splitlines()

        for line in log_lines:
            self.log.append(WeeelabLine(line))

        # store the data of the last update of the log file,
        # the data is in UTC so we add 2 for eu/it local time
        # TODO: this is sometimes +1 because ora legale, use a timezone library and compute correct time
        self.log_last_update = self.oc.file_info(self.log_path).get_last_modified() + timedelta(hours=2)

        return self

    def get_old_logs(self):
        today = datetime.date.today()
        prev_month = today.month - 1
        if prev_month == 12:
            prev_year = today.year - 1
        else:
            prev_year = today.year

        if self.old_logs_year < prev_year or self.old_logs_month < prev_month:
            self.update_old_logs(prev_month, prev_year)

    def update_old_logs(self, max_month, max_year):
        """
        Download old logs up to a date. Don't call directly, use get_old_logs.

        :param max_month:
        :param max_year:
        :return:
        """
        year = self.old_logs_year
        month = self.old_logs_month

        while True:
            month += 1
            if month >= 13:
                month = 1
                year += 1
            if year >= max_year and month > max_month:
                break

            filename = self.log_base + "log" + str(year) + str(month).zfill(2) + ".txt"
            print(f"Downloading {filename}")
            try:
                log_file = self.oc.get_file_contents(filename).decode('utf-8')
                log_lines = log_file.splitlines()

                for line in log_lines:
                    self.old_log.append(WeeelabLine(line))
            except owncloud.owncloud.HTTPResponseError:
                print(f"Failed downloading {filename}, will try again next time")
                # Roll back to the previous month, since that's the last we have
                month -= 1
                if month == 0:
                    month = 12
                    year -= 1
                break

        self.old_logs_month = month
        self.old_logs_year = year

    def get_users(self):
        try:
            self.users = json.loads(self.oc.get_file_contents(self.user_path).decode('utf-8'))["users"]
        except json.decoder.JSONDecodeError as e:
            self.error = str(e)
            if self.users is None:
                raise RuntimeError("Error getting/parsing users file and no previous version available")
            return self
        self.error = None

        return self

    def count_time_user(self, username):
        """
        Count time spent in lab for this user

        :param username:
        :return: Minutes this month and in total
        """
        minutes_thismonth = 0

        # noinspection PyUnusedLocal
        line: WeeelabLine
        for line in self.log:
            if line.username == username:
                minutes_thismonth += line.duration_minutes()

        minutes_total = minutes_thismonth

        # noinspection PyUnusedLocal
        line: WeeelabLine
        for line in self.old_log:
            if line.username == username:
                minutes_total += line.duration_minutes()

        return minutes_thismonth, minutes_total

    def count_time_month(self):
        """
        Count time spent in lab for all users this month

        :return: Dict with username as key, minutes as value
        """
        minutes = {}

        # noinspection PyUnusedLocal
        line: WeeelabLine
        for line in self.log:
            if line.username not in minutes:
                minutes[line.username] = 0
            minutes[line.username] += line.duration_minutes()

        return minutes

    def count_time_all(self):
        """
        Count time spent in lab for all users, all times

        :return: Dict with username as key, minutes as value
        """
        # Start from that
        minutes = self.count_time_month()

        # noinspection PyUnusedLocal
        line: WeeelabLine
        for line in self.old_log:
            if line.username not in minutes:
                minutes[line.username] = 0
            minutes[line.username] += line.duration_minutes()

        return minutes

    def get_entries_inlab(self):
        # PyCharm, you suggested that, why are you making me remove it?
        # noinspection PyUnusedLocal
        line: WeeelabLine
        inlab = []

        for line in self.log:
            if line.inlab:
                inlab.append(line.username)

        return inlab

    def get_entry_from_tid(self, user_id: str):
        """
        Search user data from a Telegram ID

        :param user_id: Telegram user ID
        :return: The entry from users.json or None
        """
        for user in self.users:
            if user["telegramID"] == str(user_id):
                return user
        return None

    def get_entry_from_username(self, username: str):
        """
        Search user data from a username

        :param username: Normalized, unique, official username
        :return: The entry from users.json or None
        """
        for user in self.users:
            if username == user["username"]:
                return user
        return None

    def store_new_user(self, tid, name: str, surname: str, username: str):
        new_users_file = self.oc.get_file_contents(self.user_bot_path)
        new_users = new_users_file.decode('utf-8')

        if str(tid) in new_users:
            return
        else:
            # Store a new user name and id in a file on owncloud server,
            # encoding in utf.8
            try:
                if surname != '':
                    surname = f" {surname}"
                if username == '':
                    username = " (no username)"
                else:
                    username = f" (@{username})"
                new_users = new_users + "{}{}{}: {}\n".format(name, surname, username, tid)
                self.oc.put_file_contents(self.user_bot_path, new_users.encode('utf-8'))
            except (AttributeError, UnicodeEncodeError):
                print("ERROR writing user.txt")
                pass

    def try_get_name_and_surname(self, username: str):
        """
        Get full name and surname from username, or return provided username if not found

        :param username: Normalized, unique, official username
        :return: Name and surname, or name only, or username only, or something usable
        """
        entry = self.get_entry_from_username(username)
        if entry:
            return self.get_name_and_surname(entry)
        else:
            return username

    def try_get_id(self, username: str):

        entry = self.get_entry_from_username(username)
        if entry:
            return entry["telegramID"]
        else:
            return None

    @staticmethod
    def get_name_and_surname(user_entry: dict):
        """
        Get user name and surname in correct format, given an entry.
        This doesn't crash and burn if some data is missing.

        :param user_entry: user entry (e.g. from search_user)
        :return: Name and surname, or name only, or username only, or something usable
        """
        if "name" in user_entry and "surname" in user_entry:
            return "{} {}".format(user_entry["name"], user_entry["surname"])

        if "name" in user_entry:
            return user_entry["name"]

        return user_entry["username"]

    @staticmethod
    def mm_to_hh_mm(minutes):
        hh = minutes // 60
        hh = str(hh).zfill(2)

        mm = minutes % 60
        mm = str(mm).zfill(2)

        return hh, mm


class WeeelabLine:
    regex = re.compile('\[([^\]]+)\]\s*\[([^\]]+)\]\s*\[([^\]]+)\]\s*<([^>]+)>\s*[:{2}]*\s*(.*)')

    def __init__(self, line: str):
        res = self.regex.match(line)
        self.time_in = res.group(1)
        self.time_out = res.group(2)
        self.duration = res.group(3)
        self.username = res.group(4)
        self.text = res.group(5)

        if self.duration == "INLAB":
            self.time_out = None
            self.inlab = True
        else:
            self.inlab = False

    def day(self):
        return self.time_in.split(" ")[0]

    def duration_minutes(self):
        # TODO: calculate partials (time right now - time in)
        if self.inlab:
            return 0

        parts = self.duration.split(':')
        return int(parts[0]) * 60 + int(parts[1])
