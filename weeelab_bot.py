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
import json
from typing import Optional, List

from pytarallo.AuditEntry import AuditEntry, AuditChanges
from pytarallo.Errors import ItemNotFoundError, AuthenticationError
from pytarallo.Tarallo import Tarallo

from Wol import Wol
from LdapWrapper import Users, People, LdapConnection, LdapConnectionError, DuplicateEntryError, AccountLockedError, \
    AccountNotFoundError, AccountNotCompletedError, User, Person
from ToLab import ToLab
from Weeelablib import WeeelabLogs
from variables import *  # internal library with the environment variables
import requests  # send HTTP requests to Telegram server
# noinspection PyUnresolvedReferences
import owncloud
import datetime
import traceback  # Print stack traces in logs
import simpleaudio
from stream_yt_audio import LofiVlcPlayer
from enum import Enum
from time import sleep
from remote_commands import ssh_command
from ssh_util import SSHUtil
from threading import Thread


class BotHandler:
    """
    class with method used by the bot, for more details see https://core.telegram.org/bots/api
    """

    def __init__(self, token):
        """
        init function to set bot token and reference url
        """
        print("Bot handler started")
        self.token = token
        self.api_url = "https://api.telegram.org/bot{}/".format(token)
        self.offset = None

        # These are returned when a user sends an unknown command.
        self.unknown_command_messages_last = -1
        self.unknown_command_messages = [
            "Sorry, I didn't understand that.\nWanna try /history? That one I do understand",
            "Sorry, I didn't understand that.\nWanna try /tolab? That one I do understand",
            "I don't know that command, but do you know /history? It's pretty cool",
            "I don't know that command, but do you know /tolab? It's pretty cool",
            "What? I don't understand :(\nBut I do understand /history",
            "What? I don't understand :(\nBut I do understand /tolab",
            "Unknown command. But do you know /history? It's pretty cool",
            "Unknown command. But do you know /tolab? It's pretty cool",
            "Bad command or file name.\nDo you know what's good? /history",
            "Bad command or file name.\nDo you know what's good? /tolab",
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
            print(f"Polling timed out after f{str(requests_timeout)} seconds")
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
        }
        if reply_markup is not None:
            params['reply_markup'] = {"inline_keyboard": reply_markup}
        self.__do_post('sendMessage', params)

    def edit_message(self, chat_id: int, message_id: int, text: Optional[str] = None, reply_markup=None,
                     parse_mode='HTML', disable_web_page_preview=True):
        params = {
            'chat_id': chat_id,
            'message_id': message_id,
        }
        if text is not None:
            params["text"] = text
            params["parse_mode"] = parse_mode
            params["disable_web_page_preview"] = disable_web_page_preview
        if reply_markup is not None:
            params["reply_markup"] = {"inline_keyboard": reply_markup}
        self.__do_post("editMessageText", params)

    def __do_post(self, endpoint, params):
        result = requests.post(self.api_url + endpoint, json=params)
        if result.status_code >= 400:
            print(f"Telegram server says there's an error: {result.status_code}")
            print(result.content)
            print("Our message:")
            print(json.dumps(params))

    def get_last_update(self):
        """
        method to get last message if there is.
        in case of error return an error code used in the main function
        """
        get_result = self.get_updates(120)  # recall the function to get updates
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


class AcceptableQueriesLoFi(Enum):
    play = 'lofi_play'
    pause = 'lofi_pause'
    close = 'lofi_close'
    volume_plus = 'lofi_vol+'
    volume_down = 'lofi_vol-'


def inline_keyboard_button(label: str, callback_data: str):
    return {"text": label, "callback_data": callback_data}


class CommandHandler:
    """
    Aggregates all the possible commands within one class.
    """

    def __init__(self,
                 bot: BotHandler,
                 tarallo: Tarallo,
                 logs: WeeelabLogs,
                 tolab: ToLab,
                 users: Users,
                 people: People,
                 conn: LdapConnection,
                 wol: dict):
        self.bot = bot
        self.tarallo = tarallo
        self.logs = logs
        self.tolab_db = tolab
        self.users = users
        self.people = people
        self.conn = conn
        self.wol_dict = wol

        self.user: Optional[User] = None
        self.__last_from = None
        self.__last_chat_id = None
        self.__last_user_id = None
        self.__last_user_nickname = None

        self.lofi_player = LofiVlcPlayer()
        self.lofi_player_last_volume = -1
        self.ssh_retry_times = 2

    def read_user_from_callback(self, last_update):
        self.__last_from = last_update['callback_query']['from']
        self.__last_chat_id = last_update['callback_query']['message']['chat']['id']
        self.__last_user_id = last_update['callback_query']['from']['id']
        self.__last_user_nickname = last_update['callback_query']['from']['username'] \
            if 'username' in last_update['callback_query']['from'] else None

        return self.__read_user(None)

    def read_user_from_message(self, last_update):
        self.__last_from = last_update['message']['from']
        self.__last_chat_id = last_update['message']['chat']['id']
        self.__last_user_id = last_update['message']['from']['id']
        self.__last_user_nickname = last_update['message']['from']['username'] \
            if 'username' in last_update['message']['from'] else None

        return self.__read_user(last_update['message']['text'])

    def __read_user(self, text: Optional[str]):
        self.user = None
        try:
            self.user = self.users.get(self.__last_user_id, self.__last_user_nickname, self.conn)
            return True
        except (LdapConnectionError, DuplicateEntryError) as e:
            self.exception(e.__class__.__name__)
        except AccountLockedError:
            self.__send_message("Your account is locked. You cannot use the bot until an administrator unlocks it.\n"
                                "If you're a new team member, that will happen after the test on safety.")
        except AccountNotFoundError:
            if text is not None:
                # Maybe it is the invite link for an account that doesn't exist yet?
                responded = self.respond_to_invite_link(text)
                if responded:
                    return
            self.store_id()
            msg = f"""Sorry, you are not allowed to use this bot.

If you're part of <a href=\"http://weeeopen.polito.it/\">WEEE Open</a> add your user ID in the account management panel. 
Your user ID is: <b>{self.__last_user_id}</b>"""
            self.__send_message(msg)
        except AccountNotCompletedError as e:
            self.__send_message("Oh, hi, long time no see! We switched to a new account management system, "
                                "so you will need to complete your registration here before we can talk again:\n"
                                f"{INVITE_LINK}{e.invite_code}\n"
                                "Once you're done, ask an administrator to enable your account. Have a nice day!")
        return False

    def __send_message(self, message):
        self.bot.send_message(self.__last_chat_id, message)

    def __send_inline_keyboard(self, message, markup):
        self.bot.send_message(self.__last_chat_id, message, reply_markup=markup)

    def __edit_message(self, message_id, message, markup):
        self.bot.edit_message(self.__last_chat_id, message_id, message, reply_markup=markup)

    def respond_to_invite_link(self, message) -> bool:
        message: str
        if not message.startswith(INVITE_LINK):
            return False
        link = message.split(' ', 1)[0]
        code = link[len(INVITE_LINK):]
        try:
            self.users.update_invite(code, self.__last_user_id, self.__last_user_nickname, self.conn)
        except AccountNotFoundError:
            self.__send_message("I couldn't find your invite. Are you sure of that link?")
            return True
        self.__send_message("Hey, I've filled some fields in the registration form for you, no need to say thanks.\n"
                            f"Just go back to {link} and complete the registration.\n"
                            "See you!")
        return True

    def start(self):
        """
        Called with /start
        """

        self.__send_message('\
<b>WEEE Open Telegram bot</b>.\nThe goal of this bot is to obtain information \
about who is currently in the lab, who has done what, compute some stats and, \
in general, simplify the life of our members and to avoid waste of paper \
as well.\nFor a list of the available commands type /help.', )

    def format_user_in_list(self, username: str, other=''):
        person = self.people.get(username, self.conn)
        user_id = None if person is None or person.tgid is None else person.tgid  # This is unreadable. Deal with it.
        display_name = CommandHandler.try_get_display_name(username, person)
        if user_id is None:
            return f'\n- {display_name}{other}'
        else:
            return f'\n- <a href="tg://user?id={user_id}">{display_name}</a>{other}'

    @staticmethod
    def try_get_display_name(username: str, person: Optional[Person]):
        if person is None or person.cn is None:
            return username
        else:
            return person.cn

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

        user_themself_inlab = self.user.uid in people_inlab
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
                if username == self.user.uid:
                    user_themself_tolab = True
            if not user_themself_tolab and not user_themself_inlab:
                msg += '\nAre you going, too? Tell everyone with /tolab.'
        else:
            if right_now.hour > 19:
                msg += '\n\nAre you going to go the lab tomorrow? Tell everyone with /tolab.'
            elif not user_themself_inlab:
                msg += '\n\nAre you going to go the lab later? Tell everyone with /tolab.'

        if len(inlab) > 0 and not user_themself_inlab:
            msg += "\nUse /ring for the bell, if you are at door 3."
        self.__send_message(msg)

    def tolab(self, time: str, day: str = None):
        try:
            time = self._tolab_parse_time(time)
        except ValueError:
            self.__send_message("Use correct time format, e.g. 10:30, or <i>no</i> to cancel")
            return

        if time is not None:
            try:
                day = self._tolab_parse_day(day)
            except ValueError:
                self.__send_message("Use correct day format: +1 for tomorrow, +2 for the day after tomorrow and so on")
                return

        # noinspection PyBroadException
        try:
            if time is None:
                # Delete previous entry via Telegram ID
                self.tolab_db.delete_entry(self.user.tgid)
                # TODO: add random messages (changing constantly like the "unknown command" ones),
                # like "but why?", "I'm sorry to hear that", "hope you have fun elsewhere", etc...
                self.__send_message(f"Ok, you aren't going to the lab, I've taken note.")
            else:
                days = self.tolab_db.set_entry(self.user.uid, self.user.tgid, time, day)
                if days <= 0:
                    self.__send_message(
                        f"I took note that you'll go the lab at {time}. Use <i>/tolab no</i> to cancel. Check if "
                        f"anybody else is coming with /inlab")
                elif days == 1:
                    self.__send_message(f"So you'll go the lab at {time} tomorrow. Use <i>/tolab no</i> to cancel."
                                        f"Check if anyone else is coming with /inlab")
                else:
                    self.__send_message(f"So you'll go the lab at {time} in {days} days. Use <i>/tolab no</i> to "
                                        f"cancel. Check if anyone else is coming with /inlab"
                                        f"\nMark it down on your calendar!")
        except Exception as e:
            self.__send_message(f"An error occurred: {str(e)}")
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

    def ring(self, wave_obj):
        """
        Called with /ring
        """
        inlab = self.logs.get_log().get_entries_inlab()
        if len(inlab) <= 0:
            self.__send_message("Nobody is in lab right now, I cannot ring the bell.")
            return

        lofi_player = self.lofi_player.get_player()
        if lofi_player.is_playing():
            lofi_player.stop()
            sleep(1)
            wave_obj.play()
            sleep(1)
            lofi_player.play()
        else:
            wave_obj.play()

        self.__send_message("You rang the bell 🔔 Wait at door 3 until someone comes. 🔔")

    def user_is_in_lab(self, uid):
        inlab = self.logs.get_log().get_entries_inlab()
        for username in inlab:
            if username == uid:
                return True
        return False

    def log(self, cmd_days_to_filter=None):
        """
        Called with /log
        """

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

            print_name = CommandHandler.try_get_display_name(line.username, self.people.get(line.username, self.conn))

            if line.inlab:
                days[this_day].append(f'<i>{print_name}</i> is in lab\n')
            else:
                days[this_day].append(f'<i>{print_name}</i>: {escape_all(line.text)}\n')

        msg = ''
        for this_day in days:
            msg += '<b>{day}</b>\n{rows}\n'.format(day=this_day, rows=''.join(days[this_day]))

        msg = msg + 'Latest log update: <b>{}</b>'.format(self.logs.log_last_update)
        self.__send_message(msg)

    def stat(self, cmd_target_user=None):
        if cmd_target_user is None:
            # User asking its own /stat
            target_username = self.user.uid
        else:
            # Asking for somebody else
            target_username = str(cmd_target_user)
            if target_username.lower() != self.user.uid.lower():
                # *Really* somebody else
                if self.user.isadmin:
                    # Are you an admin? Then go on!
                    person = self.people.get(target_username, self.conn)
                    if person is None:
                        target_username = None
                        self.__send_message('No statistics for the given user. Have you typed it correctly?')
                    else:
                        target_username = person.uid
                else:
                    target_username = None
                    self.__send_message('Sorry! You are not allowed to see stat of other users!\nOnly admins can!')

        # Do we know what to search?
        if target_username is not None:
            # Downloads them only if needed
            self.logs.get_old_logs()
            self.logs.get_log()

            month_mins, total_mins = self.logs.count_time_user(target_username)
            month_mins_hh, month_mins_mm = self.logs.mm_to_hh_mm(month_mins)
            total_mins_hh, total_mins_mm = self.logs.mm_to_hh_mm(total_mins)

            name = CommandHandler.try_get_display_name(target_username, self.people.get(target_username, self.conn))
            msg = f'Stat for {name}:' \
                  f'\n<b>{month_mins_hh} h {month_mins_mm} m</b> this month.' \
                  f'\n<b>{total_mins_hh} h {total_mins_mm} m</b> in total.' \
                  f'\n\nLast log update: {self.logs.log_last_update}'
            self.__send_message(msg)

    def item_command_error(self, command):
        self.__send_message(f"Add the item the code, e.g. /{command} R100")

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
            history = self.tarallo.get_history(item, limit)
            msg = f'<b>History of item {item}</b>\n\n'
            entries = 0
            for index in range(0, len(history)):
                history: List[AuditEntry]
                change = history[index].change
                h_user = history[index].user
                h_other = history[index].other
                h_time = datetime.datetime.fromtimestamp(int(history[index].time)).strftime('%d-%m-%Y %H:%M')
                if change == AuditChanges.Move:
                    msg += f'➡️ Moved to <b>{h_other}</b>\n'
                elif change == AuditChanges.Update:
                    msg += '🛠️ Updated features\n'
                elif change == AuditChanges.Create:
                    msg += '📋 Created\n'
                elif change == AuditChanges.Rename:
                    msg += f'✏️ Renamed from <b>{h_other}</b>\n'
                elif change == AuditChanges.Delete:
                    msg += '❌ Deleted\n'
                elif change == AuditChanges.Lose:
                    msg += '🔍 Lost\n'
                else:
                    msg += f'Unknown change {change.value}'
                entries += 1
                display_user = CommandHandler.try_get_display_name(h_user, self.people.get(h_user, self.conn))
                msg += f'{h_time} by <i>{display_user}</i>\n\n'
                if entries >= 6:
                    self.__send_message(msg)
                    msg = ''
                    entries = 0
            if entries != 0:
                self.__send_message(msg)
        except ItemNotFoundError:
            self.__send_message(f'Item {item} not found.')
        except AuthenticationError:
            self.__send_message('Sorry, cannot authenticate with T.A.R.A.L.L.O.')
        except RuntimeError:
            fail_msg = f'Sorry, an error has occurred (HTTP status: {str(self.tarallo.response.status_code)}).'
            self.__send_message(fail_msg)

    def item_info(self, item):
        try:
            item = self.tarallo.get_item(item)
            location = ' → '.join(item.path)
            msg = f'Item <b>{item.code}</b>\nLocation: {location}\n\n'
            for feature in item.features:
                msg += f"{feature}: {item.features[feature]}\n"
            self.__send_message(msg)
        except ItemNotFoundError:
            self.__send_message(f'Item {item} not found.')
        except AuthenticationError:
            self.__send_message('Sorry, cannot authenticate with T.A.R.A.L.L.O.')
        except RuntimeError:
            fail_msg = f'Sorry, an error has occurred (HTTP status: {str(self.tarallo.response.status_code)}).'
            self.__send_message(fail_msg)

    def top(self, cmd_filter=None):
        """
        Called with /top <filter>.
        Currently, the only accepted filter is "all", and besides that,
        it returns the monthly filter
        """
        if self.user.isadmin:
            # Downloads them only if needed
            self.logs.get_old_logs()
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
                entry = self.people.get(rival, self.conn)
                if entry is not None:
                    n += 1
                    time_hh, time_mm = self.logs.mm_to_hh_mm(time)
                    display_user = CommandHandler.try_get_display_name(rival, self.people.get(rival, self.conn))
                    if entry.isadmin:
                        msg += f'{n}) [{time_hh}:{time_mm}] <b>{display_user}</b>\n'
                    else:
                        msg += f'{n}) [{time_hh}:{time_mm}] {display_user}\n'

            msg += f'\nLast log update: {self.logs.log_last_update}'
            self.__send_message(msg)
        else:
            self.__send_message('Sorry, only admins can use this function!')

    def delete_cache(self):
        if not self.user.isadmin:
            self.__send_message('Sorry, only admins can use this function!')
            return
        users = self.users.delete_cache()
        people = self.people.delete_cache()
        logs = self.logs.delete_cache()
        self.__send_message("All caches busted! 💥\n"
                            f"Users: deleted {users} entries\n"
                            f"People: deleted {people} entries\n"
                            f"Logs: deleted {logs} lines")

    def exception(self, exception: str):
        msg = f"I tried to do that, but an exception occurred: {exception}"
        self.__send_message(msg)

    def store_id(self):
        first_name = self.__last_from['first_name']

        if 'username' in self.__last_from:
            username = self.__last_from['username']
        else:
            username = ""

        if 'last_name' in self.__last_from['from']:
            last_name = self.__last_from['from']['last_name']
        else:
            last_name = ""

        self.logs.store_new_user(self.__last_user_id, first_name, last_name, username)

    def wol(self):
        if not self.user.isadmin:
            self.__send_message("Sorry, this is a feature reserved to admins.")
            return
        buttons = []
        for machine in self.wol_dict:
            buttons.append([inline_keyboard_button(machine, 'wol_' + machine)])
        self.__send_inline_keyboard("Who do I wake up?", buttons)

    def lofi(self):
        # check if stream is playing to show correct button
        if not self.user_is_in_lab(self.user.uid) and not self.user.isadmin:
            self.__send_message("You are not in lab, no relaxing lo-fi beats for you!")
            return
        lofi_player = self.lofi_player.get_player()
        playing = lofi_player.is_playing()

        message = self.lofi_message(playing)
        reply_markup = self.lofi_keyboard(playing)

        self.__send_inline_keyboard(message, reply_markup)

    @staticmethod
    def lofi_message(playing):
        if playing:
            message = "You're stopping this music only to listen to the Russian anthem, right?"
        else:
            message = "Let's chill bruh"
        return message

    @staticmethod
    def lofi_keyboard(playing: bool):
        if playing:
            first_line_button = [inline_keyboard_button("⏸ Pause", callback_data=AcceptableQueriesLoFi.pause.value)]
        else:
            first_line_button = [inline_keyboard_button("▶️ Play", callback_data=AcceptableQueriesLoFi.play.value)]
        reply_markup = [
            first_line_button,
            [inline_keyboard_button("🔉 Vol-", callback_data=AcceptableQueriesLoFi.volume_down.value),
             inline_keyboard_button("🔊 Vol+", callback_data=AcceptableQueriesLoFi.volume_plus.value)],
            [inline_keyboard_button("❌ Close", callback_data=AcceptableQueriesLoFi.close.value)]
        ]
        return reply_markup

    def lofi_callback(self, query: str, messge_id: int):
        lofi_player = self.lofi_player.get_player()
        playing = lofi_player.is_playing()
        try:
            query = AcceptableQueriesLoFi(query)
        except ValueError:
            self.__send_message("I did not understand that button press")
            return

        if query == AcceptableQueriesLoFi.play:
            if lofi_player.play() == 0:
                volume = lofi_player.audio_get_volume()
                if volume == -1:
                    volume = self.lofi_player_last_volume
                if volume == 0:
                    lofi_player.audio_set_volume(10)  # automatically turn up the volume by one notch
                self.__edit_message(messge_id, "Playing... - current volume: " + str(volume), self.lofi_keyboard(True))
            else:  # == -1
                self.__edit_message(messge_id, "Stream could not be started because of an error.", self.lofi_keyboard(playing))

        elif query == AcceptableQueriesLoFi.pause:
            # there are no checks implemented for stop() in vlc.py
            self.lofi_player_last_volume = lofi_player.audio_get_volume()
            lofi_player.stop()  # .pause() only works on non-live streaming videos
            self.__edit_message(messge_id, "Stopping...", self.lofi_keyboard(False))

        elif query == AcceptableQueriesLoFi.volume_down:
            # os.system("amixer -c 0 set PCM 3dB-")  # system volume
            volume = lofi_player.audio_get_volume()
            if volume == -1:
                volume = self.lofi_player_last_volume
            if lofi_player.audio_set_volume(volume - 10) == 0:
                self.__edit_message(messge_id, "Volume down 10% - current volume: " + str(volume-10), self.lofi_keyboard(playing))
                if volume - 10 == 0:
                    self.lofi_player_last_volume = 0
                    lofi_player.stop()  # otherwise volume == -1
                    self.__edit_message(messge_id, "Stopping...", self.lofi_keyboard(False))
            else:  # == -1
                self.__edit_message(messge_id, "The volume is already muted.", self.lofi_keyboard(playing))

        elif query == AcceptableQueriesLoFi.volume_plus:
            # os.system("amixer -c 0 set PCM 3dB+")  # system volume
            volume = lofi_player.audio_get_volume()
            if volume == -1:
                volume = self.lofi_player_last_volume
            if volume < 100:
                if volume == 0:  # was muted, now resuming
                    if lofi_player.play() == 0:
                        lofi_player.audio_set_volume(10)
                        self.__edit_message(messge_id, "Playing... - current volume: " + str(10), self.lofi_keyboard(True))
                        return
                if lofi_player.audio_set_volume(volume + 10) == 0:
                    self.__edit_message(messge_id, "Volume up 10% - current volume: " + str(volume+10), self.lofi_keyboard(playing))
                else:
                    self.__edit_message(messge_id, "There was an error pumpin' up. Try hitting 'Play'.", self.lofi_keyboard(playing))
            else:  # == -1
                self.__edit_message(messge_id, "The volume is already cranked up to 11.", self.lofi_keyboard(playing))

        elif query == AcceptableQueriesLoFi.close:
            self.__edit_message(messge_id, "Closed. 🐄\nUse /lofi to re-open.", None)

    def wol_callback(self, query: str, message_id: int):
        machine = query.split('_', 1)[1]
        mac = self.wol_dict.get(machine, None)
        if mac is None:
            self.__send_message("That machine does not exist")
            return
        Wol.send(mac)
        self.__edit_message(message_id, f"Waking up {machine} ({mac}) from its slumber...", None)

    def logout(self, words, recursion_counter: int = 0):

        if recursion_counter >= self.ssh_retry_times:
            self.__send_message("I've tried too many times. You'd better just do the logout manually.")
            return

        if not self.user.isadmin:
            self.__send_message("Sorry, this is a feature reserved to admins. You can ask an admin to do your logout.")
            return

        else:
            username = words[0]

            logout_message = ""
            for word in words[1:]:
                logout_message += word + " "
            logout_message.rstrip().replace("  ", " ")

            if '"' in logout_message:
                self.__send_message("What have I told you? The logout message cannot contain double quotes.\n"
                                    "Please try again.")
                self.logout_help()
                return

            if logout_message.__len__() > MAX_WORK_DONE:
                self.__send_message(
                    "Try not to write the story of your life. Re-send a shorter logout message with /logout")
                return

            # send commands
            # TODO: cannot concatenate list only str
            print(ssh_command[0])
            print(ssh_command[1])
            print(username)
            print(logout_message)
            command = ssh_command[0] + username + ssh_command[1] + '"' + logout_message + '"'
            ssh_connection = SSHUtil(username=SSH_USER,
                                     host=SSH_HOST_IP,
                                     private_key_path=SSH_KEY_PATH,
                                     commands=command,
                                     timeout=5)

            # SSH worked, check return code
            if ssh_connection.execute_command(command):
                self.__check_logout_ssh(ssh_connection, username)

            # SSH didn't work
            else:
                # wol always exits with 0, cannot check if it worked
                Wol.send(WOL_LOGOUT)
                self.__send_message("Sent wol command. Waiting a couple minutes until it's completed.\n"
                                    "I'll reach out to you when I've completed the logout process.")
                # boot time is around 115 seconds
                sleep(150)
                # extreme recursion
                recursion_counter += 1
                self.logout(*words, recursion_counter)

            return

    def __check_logout_ssh(self, ssh_connection, username: str):
        # weeelab logout worked
        if ssh_connection.return_code == 0:
            self.__send_message("Logout for " + username + " completed!")
        # weeelab logout didn't work
        elif ssh_connection.return_code == 3:
            self.__send_message("Logout didn't work. Try checking the parameters you've sent me.")
        else:
            self.__send_message("Unexpected weeelab return code. Please check what happened.")
        return

    def unknown(self):
        """
        Called when an unknown command is received
        """
        self.__send_message(self.bot.unknown_command_message + "\n\nType /help for list of commands")

    def tolab_help(self):
        help_message = "Use /tolab and the time to tell the bot when you'll go to the lab.\n\n\
For example type <code>/tolab 10:30</code> if you're going at 10:30.\n\
You can also set the day: <code>/tolab 10:30 +1</code> for tomorrow, <code>+2</code> for the day after tomorrow and so\
on. If you don't set a day, I will consider the time for today or tomorrow, the one which makes more sense.\n\
You can use <code>/tolab no</code> to cancel your plans and /inlab to see who's going when."
        self.__send_message(help_message)

    def logout_help(self):
        help_message = """
Use /logout followed by a username and a description of what they've done to logout that user via weeelab.\n\n\
An example would be: /logout asd.asdoni Riparato PC 69.\n\
No special symbols are needed to separate the different fields, just use spaces.\n\
Note: the username <b>must</b> be a single word with no spaces in between.\n\
Note: the logout message cannot contain double quotes characters such as " """
        self.__send_message(help_message)

    def help(self):
        help_message = """Available commands and options:
/inlab - Show the people in lab
/log - Show log of the day
/log <i>n</i> - Show last <i>n</i> days worth of logs
/stat - Show hours you've spent in lab
/ring - ring the bell at the door
/history <i>item</i> - Show history for an item, straight outta T.A.R.A.L.L.O.
/history <i>item</i> <i>n</i> - Show <i>n</i> history entries
/lofi - Spawns a keyboard with media controls for the lofi YouTube stream"""

        if self.user.isadmin:
            help_message += """
\n<b>only for admin users</b>
/stat <i>username</i> - Show hours spent in lab by this user
/top - Show a list of top users by hours spent this month
/top all - Show a list of top users by hours spent
/deletecache - Delete caches (reload logs and users)
/logout <i>username</i> <i>description of what they've done</i> - Logout a user with weeelab
/wol - Spawns a keyboard with machines an admin can Wake On LAN"""
        self.__send_message(help_message)


def main():
    """main function of the bot"""
    print("Entered main")
    oc = owncloud.Client(OC_URL)
    oc.login(OC_USER, OC_PWD)

    bot = BotHandler(TOKEN_BOT)
    tarallo = Tarallo(TARALLO, TARALLO_TOKEN)
    logs = WeeelabLogs(oc, LOG_PATH, LOG_BASE, USER_BOT_PATH)
    tolab = ToLab(oc, TOLAB_PATH)
    if os.path.isfile("weeedong.wav"):
        wave_obj = simpleaudio.WaveObject.from_wave_file("weeedong.wav")
    else:
        wave_obj = simpleaudio.WaveObject.from_wave_file("weeedong_default.wav")
    users = Users(LDAP_ADMIN_GROUPS, LDAP_TREE_PEOPLE, LDAP_TREE_INVITES)
    people = People(LDAP_ADMIN_GROUPS, LDAP_TREE_PEOPLE)
    conn = LdapConnection(LDAP_SERVER, LDAP_USER, LDAP_PASS)
    wol = WOL_MACHINES

    handler = CommandHandler(bot, tarallo, logs, tolab, users, people, conn, wol)

    while True:
        # call the function to check if there are new messages
        last_update = bot.get_last_update()

        if last_update == -1:
            # When no messages are received...
            # print("last_update = -1")
            continue

        # per Telegram docs, either message or callback_query are None
        # noinspection PyBroadException
        try:
            if "channel_post" in last_update:
                # Leave scam channels where people add our bot randomly
                chat_id = last_update['channel_post']['chat']['id']
                print(bot.leave_chat(chat_id).text)
            elif 'message' in last_update:
                # Handle private messages
                command = last_update['message']['text'].split()
                message_type = last_update['message']['chat']['type']
                # print(last_update['message'])  # Extremely advanced debug techniques

                # Don't respond to messages in group chats
                if message_type != "private":
                    continue

                authorized = handler.read_user_from_message(last_update)
                if not authorized:
                    continue

                if command[0] == "/start" or command[0] == "/start@weeelab_bot":
                    handler.start()

                elif command[0] == "/inlab" or command[0] == "/inlab@weeelab_bot":
                    handler.inlab()

                elif command[0] == "/history" or command[0] == "/history@weeelab_bot":
                    if len(command) < 2:
                        handler.item_command_error('history')
                    elif len(command) < 3:
                        handler.history(command[1])
                    else:
                        handler.history(command[1], command[2])

                elif command[0] == "/item" or command[0] == "/item@weeelab_bot":
                    if len(command) < 2:
                        handler.item_command_error('item')
                    else:
                        handler.item_info(command[1])

                elif command[0] == "/log" or command[0] == "/log@weeelab_bot":
                    if len(command) > 1:
                        handler.log(command[1])
                    else:
                        handler.log()

                elif command[0] == "/tolab" or command[0] == "/tolab@weeelab_bot":
                    if len(command) == 2:
                        handler.tolab(command[1])
                    elif len(command) >= 3:
                        handler.tolab(command[1], command[2])
                    else:
                        handler.tolab_help()

                elif command[0] == "/ring":
                    handler.ring(wave_obj)

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

                elif command[0] == "/deletecache" or command[0] == "/deletecache@weeelab_bot":
                    handler.delete_cache()

                elif command[0] == "/help" or command[0] == "/help@weeelab_bot":
                    handler.help()

                elif command[0] == "/lofi" or command[0] == "/lofi@weeelab_bot":
                    handler.lofi()

                elif command[0] == "/wol" or command[0] == "/wol@weeelab_bot":
                    handler.wol()

                elif command[0] == "/logout" or command[0] == "/logout@weeelab_bot":
                    if len(command) > 1:
                        # handler.logout(command[1:])
                        logout = Thread(target=handler.logout, args=(command[1:],))
                        logout.start()
                    else:
                        handler.logout_help()

                else:
                    handler.unknown()

            elif 'callback_query' in last_update:
                authorized = handler.read_user_from_callback(last_update)
                if not authorized:
                    continue

                # Handle button callbacks
                query = last_update['callback_query']['data']
                message_id = last_update['callback_query']['message']['message_id']

                if query.startswith('wol_'):
                    handler.wol_callback(query, message_id)
                elif query.startswith('lofi_'):
                    handler.lofi_callback(query, message_id)
                else:
                    handler.unknown()
            else:
                print('Unsupported "last_update" type')
                print(last_update)

        except:  # catch any exception if raised
            print("ERROR!")
            print(last_update)
            print(traceback.format_exc())


# call the main() until a keyboard interrupt is called
if __name__ == '__main__':
    # noinspection PyBroadException
    try:
        main()
    except KeyboardInterrupt:
        exit()
    except:
        print("MEGAERROR!")
        print(traceback.format_exc())
        exit(1)
