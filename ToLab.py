from _datetime import datetime, timedelta
import json

import pytz


class ToLab:
    def __init__(self, oc, tolab_path: str):
        self.oc = oc
        self.local_tz = pytz.timezone("Europe/Rome")
        self.tolab_path = tolab_path
        self.tolab_file = json.loads(oc.get_file_contents(self.tolab_path).decode('utf-8'))
        for entry in self.tolab_file:
            entry["tolab"] = datetime.strptime(entry["tolab"], "%Y-%m-%d %H:%M").replace(tzinfo=self.local_tz)

    def _delete_user(self, telegram_id):
        keep = []
        for entry in self.tolab_file:
            if entry["telegramID"] != telegram_id:
                keep.append(entry)
        self.tolab_file = keep

    def _create_entry(self, username: str, telegram_id: int, time: str, day: int):
        entry = dict()
        entry["username"] = username
        entry["telegramID"] = telegram_id
        now = datetime.now(self.local_tz)
        # Assume that the time refers to today
        theday = now + timedelta(days=day)
        theday = theday.strftime('%Y-%m-%d')
        going = datetime.strptime(f"{theday} {time}", "%Y-%m-%d %H:%M").replace(tzinfo=self.local_tz)

        # If it already passed, user probably meant "tomorrow"
        if now > going:
            going += timedelta(days=1)  # I wonder if this does "exactly 24 hours" or it's smarter...

        entry["tolab"] = going
        days = (going.date() - now.date()).days
        return entry, days

    def delete_entry(self, telegram_id: int):
        self._delete_user(telegram_id)
        self.save(self.tolab_file)

    def set_entry(self, username: str, telegram_id: int, time: str, day: int) -> int:
        self._delete_user(telegram_id)
        entry, days = self._create_entry(username, telegram_id, time, day)
        self.tolab_file.append(entry)
        self.save(self.tolab_file)
        return days

    def check_tolab(self, people_inlab: set):
        """
        Check who's going to lab.
        Also, remove /tolab entries older than 30 minutes or for people that are in lab.

        :param people_inlab: set of usernames of people /inlab
        :return:
        """
        now = datetime.now(self.local_tz)
        expires = now - timedelta(minutes=30)

        changed = False
        keep = []
        for entry in self.tolab_file:
            if entry["tolab"] < expires:
                # Older than 30 minutes, remove
                changed = True
            elif entry["tolab"] < now and entry["username"] in people_inlab:
                # Was in /tolab list for some time ago and is in lab right now, remove
                # e.g. /tolab 10:00, student actually goes to lab at 10:00, this method is called at 10:03:
                # entry < now and student is in lab, so we can remove the entry.
                # e.g. /tolab 16.00, student is in lab, this method is called at 10:00: entry is not removed, they may
                # leave and come back later.
                changed = True
            else:
                keep.append(entry)

        if changed:
            self.tolab_file = keep
            self.save(keep)

        return len(keep)

    def save(self, entries: list):
        serializable = []
        for entry in entries:
            serializable.append(entry.copy())
        for entry in serializable:
            # Save it in local timezone format, because who cares
            entry["tolab"] = datetime.strftime(entry["tolab"], "%Y-%m-%d %H:%M")
        self.oc.put_file_contents(self.tolab_path, json.dumps(serializable, indent=4).encode('utf-8'))
