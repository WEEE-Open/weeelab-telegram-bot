from _datetime import datetime, timedelta
import json
import pytz
import calendar
from datetime import datetime


def inline_keyboard_button(label: str, callback_data: str):
    return {"text": label, "callback_data": callback_data}


class ToLab:
    def __init__(self, oc, tolab_path: str):
        self.oc = oc
        self.local_tz = pytz.timezone("Europe/Rome")
        self.tolab_path = tolab_path
        self.tolab_file = json.loads(oc.get_file_contents(self.tolab_path).decode('utf-8'))
        for entry in self.tolab_file:
            entry["tolab"] = self.string_to_datetime(entry["tolab"])

    def string_to_datetime(self, from_time):
        # A very simple and linear work flow - NOT
        # .replace(self.local_tz) is the ultimate solution that everyone suggests on the Internet, however that sets the
        # time so some weird timezone offsets:
        #
        # >>> datetime.now().replace(tzinfo=pytz.timezone("Europe/Rome"))
        # datetime.datetime(2019, 10, 19, 20, 37, 24, 302038, tzinfo=<DstTzInfo 'Europe/Rome' RMT+0:50:00 STD>)
        #
        # Erm, okay? Let's see what pytz has to say,,,
        #
        # >>> pytz.timezone("Europe/Rome")
        # <DstTzInfo 'Europe/Rome' RMT+0:50:00 STD>
        # >>> pytz.timezone("Europe/Berlin")
        # <DstTzInfo 'Europe/Berlin' LMT+0:53:00 STD>
        # >>> pytz.timezone("Europe/Madrid")
        # <DstTzInfo 'Europe/Madrid' LMT-1 day, 23:45:00 STD>
        # >>> pytz.timezone("Europe/Lisbon")
        # <DstTzInfo 'Europe/Lisbon' LMT-1 day, 23:23:00 STD>
        # >>> pytz.timezone("Europe/Amsterdam")
        # <DstTzInfo 'Europe/Amsterdam' LMT+0:20:00 STD>
        # >>> pytz.timezone("Europe/Brussels")
        # <DstTzInfo 'Europe/Brussels' BMT+0:18:00 STD>
        # >>> pytz.timezone("Europe/Paris")
        # <DstTzInfo 'Europe/Paris' LMT+0:09:00 STD>
        # >>> pytz.timezone("Europe/Vienna")
        # <DstTzInfo 'Europe/Vienna' LMT+1:05:00 STD>
        #
        # These may be the same as the real timezone, just based on the RMT o LMT timezone.
        # However, observe this, observe it very carefully:
        #
        # >>> datetime.now(pytz.timezone("Europe/Rome"))
        # datetime.datetime(2019, 10, 19, 20, 22, 54, 579627, tzinfo=<DstTzInfo 'Europe/Rome' CEST+2:00:00 DST>)
        #
        # Can you spot it? What is that? CEST, the correct timezone. The one that should have been there all along.
        # Smashing self.local_tz into an existing datetime with .replace() should work, but doesn't, it leaves the
        # weird time zone offset thing in there, as we've seen.
        #
        # Aaaaaand every time comparison is now broken in a weird manner.
        # So we have to create a datetime based on NOW, since that's the only reliable way to get the right timezone
        # into a datetime object, and then change the date and time. For this task .combine() is not enough, it still
        # has the weird time zone, so we have to break everything into smaller components...
        correct_date = datetime.now(self.local_tz)
        the_real_date = datetime.strptime(from_time, "%Y-%m-%d %H:%M")
        return correct_date.replace(
            day=the_real_date.day,
            month=the_real_date.month,
            year=the_real_date.year,
            hour=the_real_date.hour,
            minute=the_real_date.minute,
            second=0,
            microsecond=0)

    def __delete_user(self, telegram_id):
        keep = []
        for entry in self.tolab_file:
            if entry["telegramID"] != telegram_id:
                keep.append(entry)
        self.tolab_file = keep

    def __create_entry(self, username: str, telegram_id: int, time: str, day: int):
        entry = dict()
        entry["username"] = username
        entry["telegramID"] = telegram_id
        now = datetime.now(self.local_tz)
        # Assume that the time refers to today
        theday = now + timedelta(days=day)
        theday = theday.strftime('%Y-%m-%d')
        going = self.string_to_datetime(f"{theday} {time}")

        # If it already passed, user probably meant "tomorrow"
        if now > going:
            going += timedelta(days=1)  # I wonder if this does "exactly 24 hours" or it's smarter...

        entry["tolab"] = going
        days = (going.date() - now.date()).days
        return entry, days

    def delete_entry(self, telegram_id: int):
        self.__delete_user(telegram_id)
        self.save(self.tolab_file)

    def set_entry(self, username: str, telegram_id: int, time: str, day: int) -> int:
        self.__delete_user(telegram_id)
        new_entry, days = self.__create_entry(username, telegram_id, time, day)
        keep = []
        appended = False
        for existing_entry in self.tolab_file:
            if not appended and new_entry["tolab"] < existing_entry["tolab"]:
                keep.append(new_entry)
                appended = True
            keep.append(existing_entry)
        if not appended:
            keep.append(new_entry)
        self.tolab_file = keep
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
            elif entry["tolab"] <= now and entry["username"] in people_inlab:
                # Was in /tolab list for some time ago and is in lab right now, remove
                # e.g. /tolab 10:00, student actually goes to lab at 10:00, this method is called at 10:03:
                # entry <= now and student is in lab, so we can remove the entry.
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
        self.oc.put_file_contents(self.tolab_path, json.dumps(serializable, indent=2).encode('utf-8'))


class Tolab_Calendar:
    def __init__(self, month_offset=0):
        time = datetime.now().timetuple()
        self.day = time.tm_mday
        self.month = time.tm_mon
        self.year = time.tm_year

        self.month_offset = int(month_offset)

    def make(self):
        month , days, dates = self.set_calendar()
        keyboard = []
        col_names = []
        keyboard.append([inline_keyboard_button(label=month, callback_data="tolab:None")])
        for d in days:
            col_names.append(inline_keyboard_button(label=d, callback_data="tolab:None"))
        keyboard.append(col_names)
        for row in dates:
            week = []
            for date in row:
                week.append(inline_keyboard_button(date, callback_data=f"tolab:{date}:{month}"))
            keyboard.append(week)
        keyboard.append([
            inline_keyboard_button(label="⬅️", callback_data=f"tolab:backward_month:{self.month_offset-1}:"),
            inline_keyboard_button(label="❌", callback_data="tolab:cancel_tolab"),
            inline_keyboard_button(label="➡️", callback_data=f"tolab:forward_month:{self.month_offset+1}")
        ])
        return keyboard

    def set_calendar(self):
        self.month = (self.month + self.month_offset)
        year_offset = int((self.month - 1)/12)
        self.month = ((self.month - 1) % 12) + 1
        rows = calendar.month(self.year + year_offset, self.month, 2, 1).splitlines()
        month = rows[0].strip()
        days = rows[1].split(" ")
        dates = rows[2:]
        for row, d in enumerate(dates):
            d = d.strip(" ")
            d = d.split()
            if len(d) != 7:
                if d[0] == '1':
                    for i in range(7 - len(d)):
                        d.insert(0, " ")
                else:
                    for i in range(7 - len(d)):
                        d.append(" ")
            dates[row] = d
        return month, days, dates