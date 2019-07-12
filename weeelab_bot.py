#!/usr/bin/env python
# coding:utf-8

"""
WEEELAB_BOT - Telegram bot.
Author: WEEE Open Team
    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.
    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.
    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

# Modules
from TaralloSession import TaralloSession
from ToLab import ToLab
from Weeelablib import WeeelabLogs
from variables import *  # internal library with the environment variables
import requests  # send HTTP requests to Telegram server
# noinspection PyUnresolvedReferences
import owncloud
import datetime
import traceback  # Print stack traces in logs


class BotHandler:
    """
    class with method used by the bot, for more details see https://core.telegram.org/bots/api
    """

    def __init__(self, token):
        """
        init function to set bot token and reference url
        """
        self.token = token
        self.api_url = "https://api.telegram.org/bot{}/".format(token)
        self.offset = None

        # These are returned when a user sends an unknown command.
        self.unknown_command_messages_last = -1
        self.unknown_command_messages = [
            "Sorry, I didn't understand that",
            "I don't know that command, but do you know /history? It's pretty cool",
            "I don't know that command, but do you know /tolab? It's pretty cool",
            "What? I don't understand :(",
            "Unknown command. But do you know /history? It's pretty cool",
            "Bad command or file name"
        ]

    def get_updates(self, timeout=120):
        """
        method to receive incoming updates using long polling
        [Telegram API -> getUpdates ]
        """
        params = {'offset': self.offset, 'timeout': timeout}
        requests_timeout = timeout + 5
        # noinspection PyBroadException
        try:
            result = requests.get(self.api_url + 'getUpdates', params, timeout=requests_timeout).json()['result']
            if len(result) > 0:
                self.offset = result[-1]['update_id'] + 1
            return result
        except requests.exceptions.Timeout:
            print(f"Polling timed out after f{requests_timeout} seconds")
            return None
        except Exception as e:
            print("Failed to get updates: " + str(e))
            return None

    def send_message(self, chat_id, text, parse_mode='HTML', disable_web_page_preview=True, reply_markup=None):
        """
        method to send text messages [ Telegram API -> sendMessage ]
        On success, the sent Message is returned.
        """
        params = {
            'chat_id': chat_id,
            'text': text,
            'parse_mode': parse_mode,
            'disable_web_page_preview': disable_web_page_preview,
            'reply_markup': reply_markup
        }
        return requests.post(self.api_url + 'sendMessage', params)

    def get_last_update(self):
        """
        method to get last message if there is.
        in case of error return an error code used in the main function
        """
        get_result = self.get_updates()  # recall the function to get updates
        if not get_result:
            return -1
        elif len(get_result) > 0:  # check if there are new messages
            return get_result[-1]  # return the last message in json format
        else:
            return -1

    def leave_chat(self, chat_id):
        """
        method to send text messages [ Telegram API -> leaveChat ]
        On success, the leave Chat returns True.
        """
        params = {
            'chat_id': chat_id,
        }
        return requests.post(self.api_url + 'leaveChat', params)

    @property
    def unknown_command_message(self):
        self.unknown_command_messages_last += 1
        self.unknown_command_messages_last %= len(self.unknown_command_messages)
        return self.unknown_command_messages[self.unknown_command_messages_last]


def escape_all(string):
    return string.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


class CommandHandler:
    """
    Aggregates all the possible commands within one class.
    """

    def __init__(self, user, bot, tarallo: TaralloSession, logs: WeeelabLogs, last_update, tolab: ToLab):
        self.user = user
        self.bot = bot
        self.tarallo = tarallo
        self.logs = logs
        self.last_chat_id = last_update['message']['chat']['id']
        self.last_user_id = last_update['message']['from']['id']
        self.last_update = last_update
        self.tolab_db = tolab

    def _send_message(self, message):
        self.bot.send_message(self.last_chat_id, message)

    def start(self):
        """
        Called with /start
        """

        self._send_message('\
<b>WEEE Open Telegram bot</b>.\nThe goal of this bot is to obtain information \
about who is currently in the lab, who has done what, compute some stats and, \
in general, simplify the life of our members and to avoid waste of paper \
as well. \nAll data is read from a weeelab log file, which is fetched from \
an OwnCloud shared folder.\nFor a list of the commands allowed send /help.', )

    def format_user_in_list(self, username: str, other=''):
        user_id = self.logs.try_get_id(username)
        display_name = self.logs.try_get_name_and_surname(username)
        if user_id is None:
            return f'\n- {display_name}{other}'
        else:
            return f'\n- <a href="tg://user?id={user_id}">{display_name}</a>{other}'

    def inlab(self):
        """
        Called with /inlab
        """

        inlab = self.logs.get_log().get_entries_inlab()
        people_inlab = set()

        if len(inlab) == 0:
            msg = 'Nobody is in lab right now.'
        elif len(inlab) == 1:
            msg = 'There is one student in lab right now:'
        else:
            msg = f'There are {str(len(inlab))} students in lab right now:'

        for username in inlab:
            msg += self.format_user_in_list(username)
            people_inlab.add(username)

        user_themself_inlab = self.user['username'] in people_inlab
        number_of_people_going = self.tolab_db.check_tolab(people_inlab)
        right_now = datetime.datetime.now(self.tolab_db.local_tz)

        if number_of_people_going > 0:
            today = right_now.date()
            if number_of_people_going == 1:
                msg += '\n\nThere is one student that is going to lab:'
            else:
                msg += f'\n\nThere are {str(number_of_people_going)} students that are going to lab:'

            user_themself_tolab = False
            for user in self.tolab_db.tolab_file:
                username = user["username"]
                going_day = user["tolab"].date()
                hh = str(user["tolab"].hour).zfill(2)
                mm = str(user["tolab"].minute).zfill(2)
                if today == going_day:
                    msg += self.format_user_in_list(username, f" today at {hh}:{mm}")
                elif today + datetime.timedelta(days=1) == going_day:
                    msg += self.format_user_in_list(username, f" tomorrow at {hh}:{mm}")
                else:
                    msg += self.format_user_in_list(username, f" on {str(going_day)} at {hh}:{mm}")
                if username == self.user['username']:
                    user_themself_tolab = True
            if not user_themself_tolab and not user_themself_inlab:
                msg += '\nAre you going, too? Tell everyone with /tolab.'
        else:
            if right_now.hour > 19:
                msg += '\n\nAre you going to go the lab tomorrow? Tell everyone with /tolab.'
            elif not user_themself_inlab:
                msg += '\n\nAre you going to go the lab later? Tell everyone with /tolab.'

        self._send_message(msg)

    def tolab(self, telegram_id, time: str, day: str = None):
        try:
            time = self._tolab_parse_time(time)
        except ValueError:
            self._send_message("Use correct time format, e.g. 10:30, or <i>no</i> to cancel")
            return

        if time is not None:
            try:
                day = self._tolab_parse_day(day)
            except ValueError:
                self._send_message("Use correct day format: +1 for tomorrow, +2 for the day after tomorrow and so on")
                return

        # noinspection PyBroadException
        try:
            if time is None:
                self.tolab_db.delete_entry(telegram_id)
                # TODO: add random messages (changing constantly like the "unknown command" ones),
                # like "but why?", "I'm sorry to hear that", "hope you have fun elsewhere", etc...
                self._send_message(f"Ok, you aren't going to the lab, I've taken note.")
            else:
                user = self.logs.get_entry_from_tid(telegram_id)
                days = self.tolab_db.set_entry(user["username"], telegram_id, time, day)
                if days <= 0:
                    self._send_message(f"I took note that you'll go the lab at {time}. Use <i>/tolab no</i> to cancel.")
                elif days == 1:
                    self._send_message(f"So you'll go the lab at {time} tomorrow. Use <i>/tolab no</i> to cancel.")
                else:
                    self._send_message(f"So you'll go the lab at {time} in {days} days. Use <i>/tolab no</i> to cancel.\
\nMark it down on your calendar!")
        except Exception as e:
            self._send_message(f"An error occurred: {str(e)}")
            print(traceback.format_exc())

    @staticmethod
    def _tolab_parse_time(time: str):
        """
        Parse time and coerce it into a standard format

        :param time: Time string, provided by the user
        :return: Time in HH:mm format, or None if "no"
        """
        if time == "no":
            return None
        elif len(time) == 1 and time.isdigit():
            return f"0{time}:00"
        elif len(time) == 2 and time.isdigit() and 0 <= int(time) <= 23:
            return f"{time}:00"
        elif len(time) == 4 and time[0].isdigit() and time[2:4].isdigit() and 0 <= int(time[2:4]) <= 59:
            if time[1] == '.':
                return ':'.join(time.split('.'))
            elif time[1] == ':':
                return time
        elif len(time) == 5 and time[0:2].isdigit() and time[3:4].isdigit():
            if time[2] == '.':
                time = ':'.join(time.split('.'))
            if time[2] == ':':
                if 0 <= int(time[0:2]) <= 23 and 0 <= int(time[3:5]) <= 59:
                    return time

        raise ValueError

    @staticmethod
    def _tolab_parse_day(day: str):
        """
        Convert day offset to an integer

        :param day: Day as specified by the user
        :return: Days, 0 if None
        """
        if day is None:
            return 0
        else:
            if day.startswith('+') and day[1:].isdigit():
                day = int(day[1:])
                if not day == 0:
                    return day
        raise ValueError

    def citofona(self):
        """
        Called with /citofona
        """
        # TODO: merge the other bot HERE
        pass

    def log(self, cmd_days_to_filter=None):
        """
        Called with /log
        """

        # TODO: this also downloads the file for each request. Maybe don't do it every time.
        self.logs.get_log()

        if cmd_days_to_filter is not None and cmd_days_to_filter.isdigit():
            # Command is "/log [number]"
            days_to_print = int(cmd_days_to_filter)
        elif cmd_days_to_filter == "all":
            # This won't work. Will never work. There's a length limit on messages.
            # Whatever, this variant had been missing for months and nobody even noticed...
            days_to_print = 31
        else:
            days_to_print = 1

        days = {}
        # reversed() doesn't create a copy
        for line in reversed(self.logs.log):
            this_day = line.day()
            if this_day not in days:
                if len(days) >= days_to_print:
                    break
                days[this_day] = []

            print_name = self.logs.try_get_name_and_surname(line.username)

            if line.inlab:
                days[this_day].append(f'<i>{print_name}</i> is in lab\n')
            else:
                days[this_day].append(f'<i>{print_name}</i>: {escape_all(line.text)}\n')

        msg = ''
        for this_day in days:
            msg += '<b>{day}</b>\n{rows}\n'.format(day=this_day, rows=''.join(days[this_day]))

        msg = msg + 'Latest log update: <b>{}</b>'.format(self.logs.log_last_update)
        self._send_message(msg)

    def stat(self, cmd_target_user=None):
        if cmd_target_user is None:
            # User asking its own /stat
            target_username = self.user['username']
        elif self.user['level'] == 1:
            # User asking somebody else's stats
            # TODO: allow normal users to do /stat by specifying their own username. Pointless but more consistent.
            target_username = str(cmd_target_user)
            if self.logs.get_entry_from_username(target_username) is None:
                target_username = None
                self._send_message('No statistics for the given user. Have you typed it correctly?')
        else:
            # Asked for somebody else's stats but not an admin
            target_username = None
            self._send_message('Sorry! You are not allowed to see stat of other users!\nOnly admins can!')

        # Do we know what to search?
        if target_username is not None:
            # Downloads them only if needed
            self.logs.get_old_logs()
            # TODO: usual optimizations are possible
            self.logs.get_log()

            month_mins, total_mins = self.logs.count_time_user(target_username)
            month_mins_hh, month_mins_mm = self.logs.mm_to_hh_mm(month_mins)
            total_mins_hh, total_mins_mm = self.logs.mm_to_hh_mm(total_mins)

            msg = f'Stat for {self.logs.try_get_name_and_surname(target_username)}:' \
                  f'\n<b>{month_mins_hh} h {month_mins_mm} m</b> this month.' \
                  f'\n<b>{total_mins_hh} h {total_mins_mm} m</b> in total.' \
                  f'\n\nLast log update: {self.logs.log_last_update}'
            self._send_message(msg)

    def history(self, item, cmd_limit=None):
        if cmd_limit is None:
            limit = 6
        else:
            limit = int(cmd_limit)
            if limit < 1:
                limit = 1
            elif limit > 50:
                limit = 50
        try:
            if self.tarallo.login(BOT_USER, BOT_PSW):
                history = self.tarallo.get_history(item, limit)
                if history is None:
                    self._send_message(f'Item {item} not found.')
                else:
                    msg = f'<b>History of item {item}</b>\n\n'
                    entries = 0
                    for index in range(0, len(history)):
                        change = history[index]['change']
                        h_user = history[index]['user']
                        h_location = history[index]['other']
                        h_time = datetime.datetime.fromtimestamp(
                            int(float(history[index]['time']))).strftime('%d-%m-%Y %H:%M')
                        if change == 'M':
                            msg += f'➡️ Moved to <b>{h_location}</b>\n'
                        elif change == 'U':
                            msg += '🛠️ Updated features\n'
                        elif change == 'C':
                            msg += '📋 Created\n'
                        elif change == 'R':
                            msg += f'✏️ Renamed from <b>{h_location}</b>\n'
                        elif change == 'D':
                            msg += '❌ Deleted\n'
                        elif change == 'L':
                            msg += '🔍 Lost\n'
                        else:
                            msg += f'Unknown change {change}'
                        entries += 1
                        msg += f'{h_time} by <i>{self.logs.try_get_name_and_surname(h_user)}</i>\n\n'
                        if entries >= 6:
                            self._send_message(msg)
                            msg = ''
                            entries = 0
                    if entries != 0:
                        self._send_message(msg)
            else:
                self._send_message('Sorry, cannot authenticate with T.A.R.A.L.L.O.')
        except RuntimeError:
            fail_msg = f'Sorry, an error has occurred (HTTP status: {str(self.tarallo.last_status)}).'
            self._send_message(fail_msg)

    def top(self, cmd_filter=None):
        """
        Called with /top <filter>.
        Currently, the only accepted filter is "all", and besides that,
        it returns the monthly filter
        """
        if self.user['level'] == 1:
            # Downloads them only if needed
            self.logs.get_old_logs()
            # TODO: usual optimizations are possible
            self.logs.get_log()

            # TODO: add something like "/top 04 2018" that returns top list for April 2018
            if cmd_filter == "all":
                msg = 'Top User List!\n'
                rank = self.logs.count_time_all()
            else:
                msg = 'Top Monthly User List!\n'
                rank = self.logs.count_time_month()
            # sort the dict by value in descending order (and convert dict to list of tuples)
            rank = sorted(rank.items(), key=lambda x: x[1], reverse=True)

            n = 0
            for (rival, time) in rank:
                entry = self.logs.get_entry_from_username(rival)
                if entry is not None:
                    n += 1
                    time_hh, time_mm = self.logs.mm_to_hh_mm(time)
                    if entry["level"] == 1 or entry["level"] == 2:
                        msg += f'{n}) [{time_hh}:{time_mm}] <b>{self.logs.try_get_name_and_surname(rival)}</b>\n'
                    else:
                        msg += f'{n}) [{time_hh}:{time_mm}] {self.logs.try_get_name_and_surname(rival)}\n'

            msg += f'\nLast log update: {self.logs.log_last_update}'
            self._send_message(msg)
        else:
            self._send_message('Sorry! You are not allowed to use this function! \nOnly admins can')

    def not_allowed(self, user_json_error):
        """
        Called when user is not allowed to use the bot (banned, no telegram ID in user.json, etc...)
        """

        msg = f'Sorry, you are not allowed to use this bot.\n\
If you\'re a member of <a href="http://weeeopen.polito.it/">WEEE Open</a>, \
ask the administrators to authorize your account and /start the bot again.\n\n\
Your user ID is: <b>{self.last_user_id}</b>'

        if user_json_error is not None:
            msg += f"\n\nWarning: error in users file, {user_json_error}.\nMaybe you\'re authorized but the file is " \
                   f"broken? "

        self._send_message(msg)

    def store_id(self):
        first_name = self.last_update['message']['from']['first_name']

        if 'username' in self.last_update['message']['from']:
            username = self.last_update['message']['from']['username']
        else:
            username = ""

        if 'last_name' in self.last_update['message']['from']:
            last_name = self.last_update['message']['from']['last_name']
        else:
            last_name = ""

        self.logs.store_new_user(self.last_user_id, first_name, last_name, username)

    def unknown(self):
        """
        Called when an unknown command is received
        """
        self._send_message(self.bot.unknown_command_message + "\n\nType /help for list of commands")

    def tolab_help(self):
        help_message = "Use /tolab and the time to tell the bot when you'll go to the lab.\n\n\
For example type <code>/tolab 10:30</code> if you're going at 10:30.\n\
You can also set the day: <code>/tolab 10:30 +1</code> for tomorrow, <code>+2</code> for the day after tomorrow and so\
on. If you don't set a day, I will consider the time for today or tomorrow, the one which makes more sense.\n\
You can use <code>/tolab no</code> to cancel your plans and /inlab to see who's going when."
        self._send_message(help_message)

    def status(self):
        if self.user['level'] != 1:
            self.unknown()
            return
        if self.logs.error is None:
            message = "Everything is working correctly, or everything is broken and I don't even know."
        else:
            message = f"There's an error in users file, go and fix it: {self.logs.error}"
        self._send_message(message)

    def help(self):
        help_message = "Available commands and options:\n\n\
/inlab - Show the people in lab\n\
/log - Show log of the day\n\
/log <i>n</i> - Show last <i>n</i> days worth of logs\n\
/stat - Show hours you've spent in lab\n\
/history <i>item</i> - Show history for an item, straight outta T.A.R.A.L.L.O.\n\
/history <i>item</i> <i>n</i> - Show <i>n</i> history entries\n"

        if self.user['level'] == 1:
            help_message += "\n<b>only for admin users</b>\n\
/stat <i>name.surname</i> - Show hours spent in lab by this user\n\
/top - Show a list of top users by hours spent this month\n\
/top all - Show a list of top users by hours spent\n"
        self._send_message(help_message)


def main():
    """main function of the bot"""
    oc = owncloud.Client(OC_URL)
    oc.login(OC_USER, OC_PWD)

    bot = BotHandler(TOKEN_BOT)
    tarallo = TaralloSession(TARALLO)
    logs = WeeelabLogs(oc, LOG_PATH, LOG_BASE, USER_PATH, USER_BOT_PATH)
    tolab = ToLab(oc, TOLAB_PATH)

    while True:
        # call the function to check if there are new messages
        last_update = bot.get_last_update()

        if last_update != -1:
            # noinspection PyBroadException
            try:
                command = last_update['message']['text'].split()

                last_user_id = last_update['message']['from']['id']
                message_type = last_update['message']['chat']['type']
                print(last_update['message'])  # Extremely advanced debug techniques

                # Don't respond to messages in group chats
                if message_type == "private":
                    # TODO: get_users downloads users.json from the cloud. For performance this could be done only
                    # once in a while
                    logs.get_users()
                    user = logs.get_entry_from_tid(last_user_id)

                    # Instantiate a command handler with the current user information
                    handler = CommandHandler(user, bot, tarallo, logs, last_update, tolab)

                    if user is None or user["level"] == 0:
                        handler.not_allowed(logs.error)
                        if user is None:
                            handler.store_id()
                    else:
                        if command[0] == "/start" or command[0] == "/start@weeelab_bot":
                            handler.start()

                        elif command[0] == "/inlab" or command[0] == "/inlab@weeelab_bot":
                            handler.inlab()

                        elif command[0] == "/history" or command[0] == "/history@weeelab_bot":
                            if len(command) < 2:
                                bot.send_message(handler.last_chat_id, 'Sorry insert the item to search')
                            elif len(command) < 3:
                                handler.history(command[1])
                            else:
                                handler.history(command[1], command[2])

                        elif command[0] == "/log" or command[0] == "/log@weeelab_bot":

                            if len(command) > 1:
                                handler.log(command[1])
                            else:
                                handler.log()

                        elif command[0] == "/stat" or command[0] == "/stat@weeelab_bot":

                            if len(command) > 1:
                                handler.stat(command[1])
                            else:
                                handler.stat()

                        elif command[0] == "/top" or command[0] == "/top@weeelab_bot":
                            if len(command) > 1:
                                handler.top(command[1])
                            else:
                                handler.top()

                        elif command[0] == "/tolab" or command[0] == "/tolab@weeelab_bot":
                            if len(command) == 2:
                                handler.tolab(last_user_id, command[1])
                            elif len(command) >= 3:
                                handler.tolab(last_user_id, command[1], command[2])
                            else:
                                handler.tolab_help()

                        elif command[0] == "/help" or command[0] == "/help@weeelab_bot":
                            handler.help()

                        elif command[0] == "/status" or command[0] == "/status@weeelab_bot":
                            handler.status()

                        else:
                            handler.unknown()

            except:  # catch the exception if raised
                if "channel_post" in last_update:
                    chat_id = last_update['channel_post']['chat']['id']
                    print(bot.leave_chat(chat_id).text)
                print("ERROR!")
                print(last_update)
                print(traceback.format_exc())


# call the main() until a keyboard interrupt is called
if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        exit()
