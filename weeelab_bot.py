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
from json import JSONDecodeError
from typing import Optional, List

from pytarallo.AuditEntry import AuditEntry, AuditChanges
from pytarallo.Errors import ItemNotFoundError, AuthenticationError
from pytarallo.Tarallo import Tarallo

from Wol import Wol
from LdapWrapper import Users, People, LdapConnection, LdapConnectionError, DuplicateEntryError, AccountLockedError, \
    AccountNotFoundError, User, Person
from ToLab import ToLab, Tolab_Calendar
from Quotes import Quotes
from Weeelablib import WeeelabLogs
from variables import *  # internal library with the environment variables
import requests  # send HTTP requests to Telegram server
# from requests_html import HTMLSession
# noinspection PyUnresolvedReferences
import owncloud
import datetime
import random
import time
from datetime import timedelta
import traceback  # Print stack traces in logs
import simpleaudio
from stream_yt_audio import LofiVlcPlayer
from enum import Enum
from time import sleep
from remote_commands import ssh_weeelab_command, shutdown_command, ssh_i_am_door_command
from ssh_util import SSHUtil
from threading import Thread
from subprocess import run, PIPE


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
        self.game_questions_last = -1
        self.game_questions = [
            "Who said this?",
            "Guess the author",
            "Guess the author!",
            "Who wants to be a millionaire?",
            "Who's the author?",
            "Who said this magnificent quote?",
            "Who said this memorable quote?",
            "Who said this famous quote?",
            "Who said this one?",
            "Who said this?",
            "Who said it?",
            "Who said it first?",
            "Who said this first?",
            "Who's the author of this memorable quote?",
            "Guess the disagio",
            "Ah, this famous quote - who said it?",
            "Do you know this one?",
            "Do you know who said this one?",
        ]
        self.active_sessions = []

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

    def send_message(self, chat_id, text, parse_mode='HTML', disable_notification: bool = False,
                     disable_web_page_preview: bool = True, reply_markup=None):
        """
        method to send text messages [ Telegram API -> sendMessage ]
        On success, the sent Message is returned.
        """
        params = {
            'chat_id': chat_id,
            'text': text,
            'parse_mode': parse_mode,
            'disable_web_page_preview': disable_web_page_preview,
            'disable_notification': disable_notification
        }
        if reply_markup is not None:
            params['reply_markup'] = {"inline_keyboard": reply_markup}
        self.__do_post('sendMessage', params)

    def send_photo(self, chat_id, photo, caption: str = None, parse_mode: str = 'HTML',
                   disable_notification: bool = False, reply_markup=None):
        """
        method to send photos [ Telegram API -> sendPhoto ]
        On success, the sent Message is returned.
        """
        params = {
            'chat_id': chat_id,
            'photo': photo,
            'caption': caption,
            'parse_mode': parse_mode,
            'disable_notification': disable_notification,
            'reply_markup': reply_markup
        }
        if reply_markup is not None:
            params['reply_markup'] = {"inline_keyboard": reply_markup}
        self.__do_post('sendPhoto', params)

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

    @property
    def game_question(self):
        self.game_questions_last += 1
        self.game_questions_last %= len(self.game_questions)
        return self.game_questions[self.game_questions_last]


def escape_all(string):
    return string.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


class AcceptableQueriesLoFi(Enum):
    play = 'lofi_play'
    pause = 'lofi_pause'
    close = 'lofi_close'
    volume_plus = 'lofi_vol+'
    volume_down = 'lofi_vol-'


class AcceptableQueriesShutdown(Enum):
    weeelab_yes = 'weeelab_yes'
    weeelab_no = 'weeelab_no'
    i_am_door_yes = "i_am_door_yes"
    i_am_door_no = "i_am_door_no"


class Machines(Enum):
    scma = 'scma'
    piall = 'piall'


def inline_keyboard_button(label: str, callback_data: str):
    return {"text": label, "callback_data": callback_data}


def calculate_time_to_sleep(hour: int, minute: int = 0) -> int:
    """
    Calculate time to sleep to perform an action at a given hour and minute
    by e-caste
    """
    # hour is before given hour -> wait until today at given hour and minute
    if int(datetime.datetime.now().time().strftime('%k')) < hour:
        time_to_sleep = int(
            (datetime.datetime.today().replace(hour=hour, minute=minute, second=0)
             - datetime.datetime.now()).total_seconds())
    # hour is equal to given hour
    elif int(datetime.datetime.now().time().strftime('%k')) == hour:
        # minute is before given minute -> wait until today at given time
        if int(datetime.datetime.now().time().strftime('%M')) < minute:
            time_to_sleep = int(
                (datetime.datetime.today().replace(hour=hour, minute=minute, second=0)
                 - datetime.datetime.now()).total_seconds())
        # minute is after given minute -> wait until tomorrow at given time
        else:
            time_to_sleep = int(
                (datetime.datetime.today().replace(hour=hour, minute=minute, second=0) + timedelta(days=1)
                 - datetime.datetime.now()).total_seconds())
    # hour is after given hour -> wait until tomorrow at given time
    else:
        time_to_sleep = int(
            (datetime.datetime.today().replace(hour=hour, minute=minute, second=0) + timedelta(days=1)
             - datetime.datetime.now()).total_seconds())
    return time_to_sleep


def human_readable_number(num: int) -> str:
    """
    e.g. human_readable_number(14832675) is 14,832,675
    :param num: a big number
    :return: a comma separated number string
    """
    return "{:,}".format(num)


def fah_ranker(bot: BotHandler, hour: int, minute: int):
    while True:
        try:
            # first sleep until 5am
            sleep(calculate_time_to_sleep(hour=5, minute=0))
            # then sleep until the given hour which is now computed correctly even in case of hour change
            sleep(calculate_time_to_sleep(hour, minute))

            team_number = 249208
            url = f"https://api.foldingathome.org/team/{team_number}/members"
            url_team_info = f"https://api.foldingathome.org/team/{team_number}"
            url_total_team_count = "https://api.foldingathome.org/team/count"
            for _ in range(10):
                res = requests.get(url)
                json_res = res.json()
                res_info = requests.get(url_team_info)
                json_res_info = res_info.json()
                res_count = requests.get(url_total_team_count)
                json_res_count = res_count.json()
                if any(str(sc).startswith('4') for sc in (res.status_code, res_info.status_code, res_count.status_code)) \
                        or any('error' in j for j in (json_res, json_res_info)):
                    sleep(1)
                    continue
                else:
                    break
            else:
                continue

            json_fields = dict(zip(json_res[0], range(0, len(json_res))))
            del json_res[0]

            def _fah_get(json_list, name: str):
                pos = json_fields.get(name, -1)
                if pos < 0:
                    return None
                if pos >= len(json_list):
                    return None
                return json_list[pos]

            last = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())

            # save data to JSON
            json_history = "fah_history.json"
            json_history_content = {}
            new_file = False
            daily = False
            try:
                try:
                    with open(json_history, 'r') as inf:
                        daily = True
                        json_history_content = json.load(inf)
                        previous_snapshot_key = max(k for k, v in json_history_content.items())

                        donors_previous_score = {_fah_get(donor, 'name'): _fah_get(donor, 'score')
                                                 for donor in json_res}
                        # associate daily increase to each name
                        donors_daily_score = {name: donors_previous_score[name] - score
                                              for name, score in json_history_content[previous_snapshot_key].items()}
                        # sort by top score first
                        top_3_donors_by_daily_score = {k: v
                                                       for k, v in sorted(donors_daily_score.items(),
                                                                          key=lambda item: item[1],
                                                                          reverse=True)[:3]}
                        top_3 = "\n".join([f"<code>#{i+1}</code> <b>{name}</b> with "
                                           f"<i>{human_readable_number(score)}</i> points"
                                           for i, (name, score) in
                                           enumerate(top_3_donors_by_daily_score.items())
                                           if score > 0])

                except FileNotFoundError:
                    # create file if it doesn't exist
                    new_file = True

                # insert new snapshot in JSON
                json_history_content[last] = {_fah_get(donor, 'name'): _fah_get(donor, 'score') for donor in json_res}
                with open(json_history, 'w') as outf:
                    json.dump(json_history_content, outf)

            except TypeError as te:
                print(te)
            except JSONDecodeError as jde:
                print(jde)

            top_10 = []
            for i, member in enumerate(json_res[:10]):
                this_top_10 = f"<code>#{i+1}</code> <b>{_fah_get(member, 'name')}</b> with "
                this_top_10 += f"<i>{human_readable_number(_fah_get(member, 'score'))}</i> points"
                this_top_10 += f", <i>{_fah_get(member, 'wus')}</i> WUs"
                if _fah_get(member, 'rank') is not None:
                    this_top_10 += f", rank <i>{human_readable_number(_fah_get(member, 'rank'))}</i>"
                top_10.append(this_top_10)
            top_10 = "\n".join(top_10)

            total_credit = 0
            total_wus = 0
            for member in json_res:
                total_credit += _fah_get(member, 'score')
                total_wus += _fah_get(member, 'wus')

            delta = ""
            if daily:
                delta = f"Daily increase: <b>{human_readable_number(sum(donors_daily_score.values()))}</b>\n" \
                        if not new_file else ""

            top_3_daily = ""
            if not new_file:
                top_3_daily = f"Daily MVPs:\n{top_3}\n\n" if top_3\
                    else "No MVPs today since the score has not increased."

            text = f"Total Team Score: <b>{human_readable_number(total_credit)}</b>\n" \
                   f"Total Team Work Units: <b>{human_readable_number(total_wus)}</b>\n" \
                   f"Team Rank: {human_readable_number(json_res_info['rank'])} " \
                   f"/ {human_readable_number(json_res_count)} " \
                   f"-> top <b>{round(json_res_info['rank']/json_res_count*100, 2)}%</b>\n" \
                   f"Last update: {last}\n\n" \
                   f"{delta}" \
                   f"{top_3_daily}" \
                   f"Top members:\n{top_10}\n\n" \
                   f'See all the stats <a href="https://stats.foldingathome.org/team/{team_number}">here</a>'

            bot.send_message(chat_id=WEEE_FOLD_ID,
                             text=text,
                             disable_notification=True)

        except Exception as e:  # TODO: specify any expected Exception class
            print(e)


# def fah_grapher(bot: BotHandler, hour: int, minute: int):
#     while True:
#         try:
#             sleep(calculate_time_to_sleep(hour, minute))
#
#             team_number = 249208
#             s = HTMLSession()
#             url = f"https://folding.extremeoverclocking.com/graphs/production_day_total.php?s=&t={team_number}"
#
#             img_enc_png = s.get(url).content
#             bot.send_photo(chat_id=WEEE_FOLD_ID,
#                            photo=img_enc_png)
#
#         except Exception as e:
#             print(e)


def run_shell_cmd(cmd: str) -> str:
    cmd = cmd.strip().replace('  ', ' ').split(' ')  # is now a list of strings
    return run(cmd, stdout=PIPE).stdout.decode('utf-8')


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
                 wol: dict,
                 quotes: Quotes):
        self.bot = bot
        self.tarallo = tarallo
        self.logs = logs
        self.quotes = quotes
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

If you're part of <a href=\"http://weeeopen.polito.it/\">WEEE Open</a> add your user ID in the account management panel
or ask an administrator to unlock your account.
Your user ID is: <b>{self.__last_user_id}</b>"""
            self.__send_message(msg)
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

        haskey = chr(128273) if person.haskey else ""

        sir = ""
        if self.user.isadmin and person.dateofsafetytest is not None and not person.signedsir:
            sir = f" (Remember to sign the SIR! {chr(128221)})"

        if user_id is None:
            return f'\n- {display_name}{haskey}{other}{sir}'
        else:
            return f'\n- <a href="tg://user?id={user_id}">{display_name}</a>{haskey}{other}{sir}'

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
                msg += '\n\nAre you going to the lab tomorrow? Tell everyone with /tolab.'
            elif not user_themself_inlab:
                msg += '\n\nAre you going to the lab later? Tell everyone with /tolab.'

        if len(inlab) > 0 and not user_themself_inlab:
            msg += "\n\nUse /ring for the bell, if you are at door 3."
        self.__send_message(msg)

    def tolab(self, the_time: str, day: str = None, is_gui: bool = False):
        try:
            the_time = self._tolab_parse_time(the_time)
        except ValueError:
            self.__send_message("Use correct time format, e.g. 10:30, or <i>no</i> to cancel")
            return

        if the_time is not None:
            try:
                day = self._tolab_parse_day(day)
            except ValueError:
                self.__send_message("Use correct day format: +1 for tomorrow, +2 for the day after tomorrow and so on")
                return

        # noinspection PyBroadException
        try:
            if the_time is None:
                # Delete previous entry via Telegram ID
                self.tolab_db.delete_entry(self.user.tgid)
                self.__send_message(f"Ok, you aren't going to the lab, I've taken note.")
            else:
                sir_message = ""
                if not self.user.signedsir and self.user.dateofsafetytest is not None:
                    sir_message = "\nRemember to sign the SIR when you get there!"

                days = self.tolab_db.set_entry(self.user.uid, self.user.tgid, the_time, day)
                if not is_gui:
                    if days <= 0:
                        self.__send_message(
                            f"I took note that you'll go to the lab at {the_time}. "
                            f"Use /tolab_no to cancel. Check if "
                            f"anybody else is coming with /inlab.{sir_message}")
                    elif days == 1:
                        self.__send_message(f"So you'll go the lab at {the_time} tomorrow. Use /tolab_no to cancel. "
                                            f"Check if anyone else is coming with /inlab{sir_message}")
                    else:
                        last_message = sir_message if sir_message != "" else "\nMark it down on your calendar!"
                        self.__send_message(f"So you'll go the lab at {the_time} in {days} days. Use /tolab_no to "
                                        f"cancel. Check if anyone else is coming with /inlab"
                                        f"{last_message}")
        except Exception as e:
            self.__send_message(f"An error occurred: {str(e)}")
            print(traceback.format_exc())

    def tolabGui(self):
        calendar = Tolab_Calendar().make()
        idx = 0
        self.__send_inline_keyboard(message=f"Select a date",
                                    markup=calendar)

    def get_tolab_active_sessions(self):
        return self.bot.active_sessions

    @staticmethod
    def _tolab_parse_time(the_time: str):
        """
        Parse time and coerce it into a standard format

        :param the_time: Time string, provided by the user
        :return: Time in HH:mm format, or None if "no"
        """
        if the_time == "no":
            return None
        elif len(the_time) == 1 and the_time.isdigit():
            return f"0{the_time}:00"
        elif len(the_time) == 2 and the_time.isdigit() and 0 <= int(the_time) <= 23:
            return f"{the_time}:00"
        elif len(the_time) == 4 and the_time[0].isdigit() and the_time[2:4].isdigit() and 0 <= int(the_time[2:4]) <= 59:
            if the_time[1] == '.':
                return ':'.join(the_time.split('.'))
            elif the_time[1] == ':':
                return the_time
        elif len(the_time) == 5 and the_time[0:2].isdigit() and the_time[3:4].isdigit():
            if the_time[2] == '.':
                the_time = ':'.join(the_time.split('.'))
            if the_time[2] == ':':
                if 0 <= int(the_time[0:2]) <= 23 and 0 <= int(the_time[3:5]) <= 59:
                    return the_time

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

    def _get_tolab_gui_days(self, idx: int, date: str):
        self.bot.active_sessions[idx][2]
        day = date.split()
        day[1] = datetime.datetime.strptime(day[1], "%B").month
        day = f'{day[0]} {day[1]} {day[2]}'
        day = datetime.datetime.strptime(day, "%d %m %Y")
        today = datetime.datetime.now().timetuple()
        today = f"{today.tm_mday} {today.tm_mon} {today.tm_year}"
        today = datetime.datetime.strptime(today, "%d %m %Y")
        diff = day - today
        return diff.days

    def ring(self, wave_obj):
        """
        Called with /ring
        """
        inlab = self.logs.get_log().get_entries_inlab()
        if len(inlab) <= 0:
            self.__send_message("Nobody is in lab right now, I cannot ring the bell.")
            return

        if self.lofi_player.player_exist():
            lofi_player = self.lofi_player.get_player()
            if lofi_player.is_playing():
                lofi_player.stop()
                sleep(1)
                wave_obj.play()
                sleep(1)
                lofi_player.play()
            else:
                wave_obj.play()
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
                        # Downloads them only if needed
                        self.logs.get_old_logs()
                        self.logs.get_log()
                        if not self.logs.user_exists_in_logs(target_username):
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
            location = ' → '.join(item.location)
            msg = f'Item <b>{item.code}</b>\nLocation: {location}\n\n'
            for feature in item.features:
                msg += f"{feature}: {item.features[feature]}\n"
            if item.product is not None:
                msg += f"----------------------------\n"
                for feature in item.product.features:
                    msg += f"{feature}: {item.product.features[feature]}\n"
            msg += f'\n<a href="{self.tarallo.url}/item/{item.code}">View on Tarallo</a>'

            self.__send_message(msg)
        except ItemNotFoundError:
            self.__send_message(f'Item {item} not found.')
        except (RuntimeError, AuthenticationError):
            fail_msg = f'Sorry, an error has occurred (HTTP status: {str(self.tarallo.response.status_code)}).'
            self.__send_message(fail_msg)

    def item_location(self, item):
        try:
            item = self.tarallo.get_item(item, 0)
            location = ' → '.join(item.location)
            msg = f'Item <b>{item.code}</b>\nLocation: {location}\n'
            msg += f'\n<a href="{self.tarallo.url}/item/{item.code}">View on Tarallo</a>'

            self.__send_message(msg)
        except ItemNotFoundError:
            self.__send_message(f'Item {item} not found.')
        except (RuntimeError, AuthenticationError):
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
            for (rival, the_time) in rank:
                entry = self.people.get(rival, self.conn)
                if entry is not None:
                    n += 1
                    time_hh, time_mm = self.logs.mm_to_hh_mm(the_time)
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
        quotes = self.quotes.delete_cache()
        self.__send_message("All caches busted! 💥\n"
                            f"Users: deleted {users} entries\n"
                            f"People: deleted {people} entries\n"
                            f"Logs: deleted {logs} lines\n"
                            f"Quotes: deleted {quotes} lines")

    def exception(self, exception: str):
        msg = f"I tried to do that, but an exception occurred: {exception}"
        self.__send_message(msg)

    def store_id(self):
        first_name = self.__last_from['first_name']

        if 'username' in self.__last_from:
            username = self.__last_from['username']
        else:
            username = ""

        if 'last_name' in self.__last_from:
            last_name = self.__last_from['last_name']
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

    def game(self, param=None):
        if param is not None:
            if param == "stat" or param == "stats" or param == "statistics":
                right, wrong = self.quotes.get_game_stats(self.user.uid)
                total = right + wrong
                if total == 0:
                    self.__send_message(f"You never played the game.")
                    return
                right_percent = right * 100 / total
                wrong_percent = wrong * 100 / total
                self.__send_message(f"You answered {total} questions.\n"
                                    f"Right: {right} ({right_percent:2.1f}%)\nWrong: {wrong} ({wrong_percent:2.1f}%)")
            else:
                self.unknown()
        else:
            quote, context, answers = self.quotes.get_quote_for_game(self.user.uid)
            buttons = [
                [
                   inline_keyboard_button(answers[0], 'game_' + Quotes.normalize_author_for_game(answers[0])),
                   inline_keyboard_button(answers[1], 'game_' + Quotes.normalize_author_for_game(answers[1])),
                ],
                [
                   inline_keyboard_button(answers[2], 'game_' + Quotes.normalize_author_for_game(answers[2])),
                   inline_keyboard_button(answers[3], 'game_' + Quotes.normalize_author_for_game(answers[3])),
                ],
            ]

            if context:
                context = ' - <i>[author]</i> ' + escape_all(context)
            else:
                context = ''

            self.__send_inline_keyboard(f"{escape_all(quote)}{context}\n\n<i>{self.bot.game_question}</i>", buttons)

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
                self.__edit_message(messge_id, "Stream could not be started because of an error.",
                                    self.lofi_keyboard(playing))

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
                self.__edit_message(messge_id, "Volume down 10% - current volume: " + str(volume - 10),
                                    self.lofi_keyboard(playing))
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
                        self.__edit_message(messge_id, "Playing... - current volume: " + str(10),
                                            self.lofi_keyboard(True))
                        return
                if lofi_player.audio_set_volume(volume + 10) == 0:
                    self.__edit_message(messge_id, "Volume up 10% - current volume: " + str(volume + 10),
                                        self.lofi_keyboard(playing))
                else:
                    self.__edit_message(messge_id, "There was an error pumpin' up. Try hitting 'Play'.",
                                        self.lofi_keyboard(playing))
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

    # noinspection PyUnusedLocal
    def game_callback(self, query: str, message_id: int):
        answer = query.split('_', 1)[1]
        result = self.quotes.answer_game(self.user.uid, answer)
        if result is None:
            self.__send_message("I somehow forgot the question, sorry")
            return
        elif result is True:
            self.__send_message("🏆 You're winner! 🏆\nAnother one? /game")
            return
        else:
            self.__send_message(f"Nope, that quote was from {result}\nAnother one? /game")

    def tolab_callback(self, query: str, message_id: int, user_id: int):
        # ---------------- READMEEEEEEEEEEEEEE --------------------
        # PLEASE, do not touch anything if you're not absolutely sure about what are you doing. Thanks
        query = query.replace(".", ":")
        data = query.split(":")

        if data[0] == 'hour':
            for idx, session in enumerate(self.bot.active_sessions):
                if session[0] == user_id:
                    day = self._get_tolab_gui_days(idx, self.bot.active_sessions[idx][2])
                    sir_message = ""
                    print(f"query = {query}")
                    if len(data[-1]) > 2 or len(data[-1]) < 2 and data[-2] != 'hour':
                        if len(data[-2]) > 2 or len(data[-2]) < 2:
                            self.bot.edit_message(chat_id=self.__last_chat_id, message_id=message_id,
                                                  text="❌ Use correct time format, e.g. 10:30. Please, retry /tolab")

                            print(f"data[-1] = {data[-1]}")
                            print(f"data[-2] = {data[-2]}")
                            del self.bot.active_sessions[idx]
                            return
                    if (not self.user.signedsir) and (self.user.dateofsafetytest is not None):
                        sir_message = "\nRemember to sign the SIR when you get there! 📝"
                        # if people do tolab for a day that is after tomorrow then send also the "mark it down" message
                        if day > 1:
                            sir_message += "\nMark it down on your calendar!"
                    if day < 0:
                        self.bot.edit_message(chat_id=self.__last_chat_id, message_id=message_id,
                                              text="❌ You've selected a past date. Please select a valid date.")
                        del self.bot.active_sessions[idx]
                        return
                    if day == 0:
                        day = None
                    else:
                        day = f"+{day}"
                    if len(data) > 2:
                        self.tolab(the_time=f"{data[1]}:{data[2]}", day=day, is_gui=True)
                        self.bot.edit_message(chat_id=self.__last_chat_id, message_id=message_id,
                                              text=f"✅ So you're going to lab at {data[1]}:{data[2]} of "
                                                   f"{self.bot.active_sessions[idx][2]}. See you inlab!\nUse /tolab_no "
                                                   f"to cancel. Check if anybody else is coming with /inlab.\n"
                                                   f"{sir_message}")
                    else:
                        self.tolab(the_time=f"{data[1]}", day=day, is_gui=True)
                        self.bot.edit_message(chat_id=self.__last_chat_id, message_id=message_id,
                                              text=f"✅ So you're going to lab at {data[1]}:00 of "
                                                   f"{self.bot.active_sessions[idx][2]}. See you inlab!\nUse /tolab_no "
                                                   f"to cancel. Check if anybody else is coming with /inlab.\n"
                                                   f"{sir_message}")

                    del self.bot.active_sessions[idx]
                    return
        elif data[1] == 'forward_month':
            calendar = Tolab_Calendar(data[2]).make()
            self.bot.edit_message(chat_id=self.__last_chat_id, message_id=message_id,
                                  text=f"Select a date", reply_markup=calendar)
        elif data[1] == 'backward_month':
            calendar = Tolab_Calendar(data[2]).make()
            self.bot.edit_message(chat_id=self.__last_chat_id, message_id=message_id,
                                  text=f"Select a date", reply_markup=calendar)
        elif data[1] == 'cancel_tolab':
            for idx, session in enumerate(self.bot.active_sessions):
                if session == self.__last_chat_id:
                    del self.bot.active_sessions[idx]
            self.bot.edit_message(chat_id=self.__last_chat_id, message_id=message_id,
                                  text=f"❌ Tolab canceled.")
        elif data[1] != ' ' and data[1] != 'None':
            self.bot.edit_message(chat_id=self.__last_chat_id, message_id=message_id,
                                  text=f"🕐 Now, send a message with the hour you're going to lab")
            for idx, session in enumerate(self.bot.active_sessions):
                if user_id == session[0]:
                    return
                if (idx + 1) == len(self.bot.active_sessions):
                    self.bot.active_sessions.append([user_id, message_id, f"{data[1]} {data[2]}"])
                    return
            # This is horrendous but it werks
            self.bot.active_sessions.append([user_id, message_id, f"{data[1]} {data[2]}"])

    def logout(self, words):
        if not self.user.isadmin:
            self.__send_message("Sorry, this is a feature reserved to admins. You can ask an admin to do your logout.")
            return

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
        command = str(ssh_weeelab_command['logout'][0] + username + ssh_weeelab_command['logout'][1] + '"' + logout_message + '"')
        ssh_connection = SSHUtil(username=SSH_SCMA_USER,
                                 host=SSH_SCMA_HOST_IP,
                                 private_key_path=SSH_SCMA_KEY_PATH,
                                 commands=command,
                                 timeout=5)

        # SSH worked, check return code
        if ssh_connection.execute_command():
            self.__check_weeelab_ssh(ssh_connection, username, 'Logout')

        # SSH didn't work
        else:
            # wol always exits with 0, cannot check if it worked
            Wol.send(WOL_WEEELAB)
            self.__send_message("Sent wol command. Waiting a couple minutes until it's completed.\n"
                                "I'll reach out to you when I've completed the logout process.")
            # boot time is around 115 seconds
            # check instead of guessing when the machine has finished booting
            while True:
                sleep(10)
                if ssh_connection.execute_command():
                    self.__check_weeelab_ssh(ssh_connection, username, 'Logout')
                    break

        # give the user the option to shutdown the logout machine
        self.shutdown_prompt(Machines.scma)

        return

    def login(self, words):
        if not self.user.isadmin:
            self.__send_message("Sorry, this is a feature reserved to admins. You can ask an admin to do your login.")
            return

        username = words[0]

        # send commands
        command = str(ssh_weeelab_command['login'][0] + username)
        ssh_connection = SSHUtil(username=SSH_SCMA_USER,
                                 host=SSH_SCMA_HOST_IP,
                                 private_key_path=SSH_SCMA_KEY_PATH,
                                 commands=command,
                                 timeout=5)

        # SSH worked, check return code
        if ssh_connection.execute_command():
            self.__check_weeelab_ssh(ssh_connection, username, 'Login')

        # SSH didn't work
        else:
            # wol always exits with 0, cannot check if it worked
            Wol.send(WOL_WEEELAB)
            self.__send_message("Sent wol command. Waiting a couple minutes until it's completed.\n"
                                "I'll reach out to you when I've completed the login process.")
            # boot time is around 115 seconds
            # check instead of guessing when the machine has finished booting
            while True:
                sleep(10)
                if ssh_connection.execute_command():
                    self.__check_weeelab_ssh(ssh_connection, username, 'Login')
                    break

        # give the user the option to shutdown the logout machine
        self.shutdown_prompt(Machines.scma)

        return

    def __check_weeelab_ssh(self, ssh_connection, username: str, action: str):
        # weeelab logout worked
        if ssh_connection.return_code == 0:
            self.__send_message(action + " for " + username + " completed!")
        # weeelab logout didn't work
        elif ssh_connection.return_code == 3:
            self.__send_message(action + " didn't work. Try checking the parameters you've sent me.")
        else:
            self.__send_message("Unexpected weeelab return code. Please check what happened.")
        return

    def quote(self, author: Optional[str]):
        quote, author, context, _ = self.quotes.get_random_quote(author)

        if quote is None:
            self.__send_message("No quotes found 🙁")
            return

        if context:
            context = ' ' + context
        else:
            context = ''

        self.__send_message(f"{escape_all(quote)} - <i>{escape_all(author)}</i>{escape_all(context)}")

    def motivami(self):
        quote = self.quotes.get_demotivational_quote()

        if quote is None:
            self.__send_message("No demotivational quotes found 🙁")
            return

        self.__send_message(escape_all(quote))

    def i_am_door(self):
        if not self.user.isadmin:
            self.__send_message("Sorry, this is a feature reserved to admins. You can ask an admin to do your logout.")
            return

        ssh_connection = SSHUtil(username=SSH_PIALL_USER,
                                 host=SSH_PIALL_HOST_IP,
                                 private_key_path=SSH_PIALL_KEY_PATH,
                                 commands=ssh_i_am_door_command,
                                 timeout=5)

        # SSH didn't work
        if not ssh_connection.execute_command():
            # wol always exits with 0, cannot check if it worked
            Wol.send(WOL_I_AM_DOOR)
            self.__send_message("Sent wol command. Waiting a couple minutes until it's completed.\n"
                                "I'll reach out to you when I've completed the logout process.")
            while True:
                sleep(10)
                if ssh_connection.execute_command():
                    break

        self.__send_message("IO. SONO. PORTA.")

        # give the user the option to shutdown the logout machine
        # actually don't since it could break some disks during formatting
        # self.shutdown_prompt(Machines.piall)

        return

    def shutdown_prompt(self, machine):
        try:
            machine = Machines(machine)
        except ValueError:
            self.__send_message("That machine does not exist!")
            return

        if machine == Machines.scma:
            yes = AcceptableQueriesShutdown.weeelab_yes.value
            no = AcceptableQueriesShutdown.weeelab_no.value
        elif machine == Machines.piall:
            yes = AcceptableQueriesShutdown.i_am_door_yes.value
            no = AcceptableQueriesShutdown.i_am_door_no.value
        else:
            self.__send_message("That machine does not exist!")
            return

        message = "Do you want to shutdown the machine now?"
        reply_markup = [
            [inline_keyboard_button("Kill it with fire!", callback_data=yes)],
            [inline_keyboard_button("No, it's crucial that it stays alive!", callback_data=no)]
        ]
        self.__send_inline_keyboard(message, reply_markup)

    def shutdown_callback(self, query, message_id: int, ssh_user: str, ssh_host_ip: str, ssh_key_path: str):
        shutdown_retry_times = 5

        try:
            query = AcceptableQueriesShutdown(query)
        except ValueError:
            self.__send_message("I did not understand that button press")
            return

        if query == AcceptableQueriesShutdown.weeelab_yes or \
                query == AcceptableQueriesShutdown.i_am_door_yes:
            ssh_connection = SSHUtil(username=ssh_user,
                                     host=ssh_host_ip,
                                     private_key_path=ssh_key_path,
                                     commands=shutdown_command,
                                     timeout=5)

            for _ in range(shutdown_retry_times):
                if ssh_connection.execute_command():
                    self.__edit_message(message_id, "Shutdown successful!", None)
                    break
                else:
                    self.__edit_message(message_id, "There was an issue with the shutdown. Retrying...", None)

        elif query == AcceptableQueriesShutdown.weeelab_no or \
                query == AcceptableQueriesShutdown.i_am_door_no:
            self.__edit_message(message_id, "Alright, we'll leave it alive. <i>For now.</i>", None)

    def status(self):
        if not self.user.isadmin:
            self.__send_message("Sorry, this is a feature reserved to admins.")
            return
        uptime_out = f"<code>{run_shell_cmd('uptime')}</code>"
        # enable if you want to check network speed, it takes 30ish seconds to run though
        # st_out = f"<code>{run_shell_cmd('speedtest')}</code>"
        free_h_out = f"<code>{run_shell_cmd('free -h')}</code>"
        df_h_root_out = f"<code>{run_shell_cmd('df -h /')}</code>"
        python_out = f"<code>{run_shell_cmd('pgrep -a python')}</code>"

        self.__send_message("\n\n".join([uptime_out, free_h_out, df_h_root_out, python_out]))

    @staticmethod
    def __get_telegram_link_to_person(p: Person) -> str:
        """
        :param p: Person object from the team's LDAP
        :return: Telegram-formatted string that links to the person's profile and tags them in a message
        """
        # if no nickname -> tag on cn
        # else, if " in cn -> tag on quoted nickname between "double quotes" in cn
        #       else -> tag on tag on telegram nickname between (parentheses) after cn
        return f"""{f'<b><a href="tg://user?id={p.tgid}">{p.cn}</a></b>' if not p.nickname
        else f'''{p.cn} (<b><a href="tg://user?id={p.tgid}">{p.nickname}</a></b>)'''
        if '"' not in p.cn
        else f'''{p.cn.split('"')[0]}"<b><a href="tg://user?id={p.tgid}">{p.cn.split('"')[1]}</a></b>"{p.cn.split('"')[2]}'''}"""

    @staticmethod
    def __get_next_birthday_of_person(p: Person) -> datetime.date:
        t = datetime.date.today()
        return datetime.date(year=t.year if (p.dateofbirth.month == t.month and p.dateofbirth.day > t.day) or p.dateofbirth.month > t.month else t.year + 1,
                             month=p.dateofbirth.month,
                             day=p.dateofbirth.day) if p.dateofbirth else None

    def __sorted_birthday_people(self) -> List[Person]:
        """
        :return: list of people sorted by birth date
        """
        return sorted([p for p in self.people.get_all(self.conn) if not p.accountlocked and p.dateofbirth],
                      key=lambda p: CommandHandler.__get_next_birthday_of_person(p))

    def __next_birthday_people(self, n: int = 3) -> List[Person]:
        """
        :param n: optional number of people (defaults to 3)
        :return: list of n people with coming birthdays, sorted by birth date
        """
        return self.__sorted_birthday_people()[:n]

    def next_birthdays(self):
        if not self.user.isadmin:
            self.__send_message("Sorry, this is a feature reserved to admins.")
            return

        bd_people = '\n'.join([f"{CommandHandler.__get_telegram_link_to_person(p)} "
                               f"on {str(p.dateofbirth.day).zfill(2)}/{str(p.dateofbirth.month).zfill(2)} "
                               f"in {(CommandHandler.__get_next_birthday_of_person(p) - datetime.date.today()).days} "
                               f"day(s)"
                               for p in self.__next_birthday_people()])
        self.__send_message(f"The people who have a coming birthday 🎂 are:\n\n{bd_people}")

    def birthday_wisher(self):
        """
        This function is not a command, but needs to be a CommandHandler method because it requires the list of people
        in our team and their birthdays
        """
        while True:
            try:
                sleep(calculate_time_to_sleep(hour=10, minute=0))

                birthday_people = set(CommandHandler.__get_telegram_link_to_person(p)
                                      if not p.accountlocked and p.tgid and p.dateofbirth and
                                         (p.dateofbirth.month == datetime.date.today().month and
                                          p.dateofbirth.day == datetime.date.today().day) else None
                                      for p in self.people.get_all(self.conn))
                birthday_people.remove(None)

                if birthday_people:
                    compleanno = "compleanno"
                    for birthday_person in birthday_people:
                        if 'palmi' in birthday_person.lower():
                            compleanno = "genetliaco"

                    birthday_decoration = random.choice(('🎂' * 42, '🎂🎉' * 21))
                    birthday_wishes = random.choice(
                        ('AugurEEE!!!', 'Auguriii!!!', 'Tante angurieee! 🍉🍉', 'Mega-auguriii!')
                    )

                    birthday_msg = f"{birthday_decoration}\n\n" \
                                   f"Oggi è il {compleanno} di {' e '.join(birthday_people)}!\n" \
                                   f"{birthday_wishes}" \
                                   f"\n\n{birthday_decoration}"
                    self.bot.send_message(chat_id=WEEE_CHAT_ID,
                                          text=birthday_msg)
                    sleep(60)  # TODO: do we need this?

            except Exception as e:
                print(e)

    def __sorted_test_people(self) -> List[Person]:
        """
        :return: list of people sorted by safety test date
        """
        return sorted([p for p in self.people.get_all(self.conn) if not p.accountlocked and p.dateofsafetytest],
                      key=lambda p: p.dateofsafetytest)

    def __next_test_people(self) -> List[Person]:
        """
        :return: list of people with coming safety tests, sorted by date
        """
        return [p for p in self.__sorted_test_people()
                if p.dateofsafetytest.year >= datetime.date.today().year
                and ((p.dateofsafetytest.month == datetime.date.today().month
                     and p.dateofsafetytest.day >= datetime.date.today().day)
                     or (p.dateofsafetytest.month > datetime.date.today().month))]

    def next_tests(self):
        if not self.user.isadmin:
            self.__send_message("Sorry, this is a feature reserved to admins.")
            return

        test_people = '\n'.join([f"{CommandHandler.__get_telegram_link_to_person(p)} "
                                 f"on {str(p.dateofsafetytest.day).zfill(2)}/{str(p.dateofsafetytest.month).zfill(2)}/{str(p.dateofsafetytest.year).zfill(4)} "
                                 f"in {(p.dateofsafetytest - datetime.date.today()).days} day(s)"
                                 for p in self.__next_test_people()])
        self.__send_message(f"The people who have a coming safety test 🛠 are:\n\n{test_people}"
                            if test_people else "No safety tests planned at the moment.")

    def safety_test_reminder(self):
        """
        This function is not a command, but needs to be a CommandHandler method because it requires the list of people
        in our team and their safety test dates
        """
        while True:
            try:
                # send notification early in the morning - worst case scenario, the test is at 8.30 a.m.
                sleep(calculate_time_to_sleep(hour=7, minute=30))

                test_people = []
                for p in self.people.get_all(self.conn):
                    if p.dateofsafetytest and p.dateofsafetytest == datetime.date.today():
                        if p.tgid:
                            test_people.append(CommandHandler.__get_telegram_link_to_person(p))
                        else:
                            test_people.append(p.cn)

                if test_people:
                    reminder_msg = f"⚠️⚠️⚠️\nOggi c'è il <b>test di sicurezza</b> di:\n{', '.join(test_people)}"
                    self.bot.send_message(chat_id=WEEE_CHAT2_ID,
                                          text=reminder_msg)
                    sleep(60)

            except Exception as e:
                print(e)

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

    def login_help(self):
        help_message = """
Use /login followed by a username to login that user via weeelab.\n\n\
An example would be: /logout asd.asdoni\n\
Note: the username <b>must</b> be a single word with no spaces in between.\n"""
        self.__send_message(help_message)

    def help(self):
        help_message = """Available commands and options:
/inlab - Show the people in lab
/tolab - Show other people when you are going to the lab
/log - Show log of the day
/log <i>n</i> - Show last <i>n</i> days worth of logs
/stat - Show hours you've spent in lab
/ring - Ring the bell at the door
/item <i>code</i> - Show info about an item
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
/login <i>username</i> - Login a user with weeelab
/wol - Spawns a keyboard with machines an admin can Wake On LAN
/door - sonoporta
/status - Show host machine uptime, load, memory and disk usage
/nextbirthdays - Show next people who will have a birthday
/nexttests - Show next people who will have a safety test"""
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
    users = Users(LDAP_ADMIN_GROUPS, LDAP_TREE_PEOPLE, LDAP_TREE_INVITES, LDAP_TREE_GROUPS)
    people = People(LDAP_ADMIN_GROUPS, LDAP_TREE_PEOPLE)
    conn = LdapConnection(LDAP_SERVER, LDAP_USER, LDAP_PASS)
    wol = WOL_MACHINES
    quotes = Quotes(oc, QUOTES_PATH, DEMOTIVATIONAL_PATH, QUOTES_GAME_PATH)

    # fah_text_hours = [
    #     (9, 0),
    #     # (13, 37),
    #     # (22, 0)
    # ]
    # fah_ranker_ts = [Thread(target=fah_ranker, args=(BotHandler(TOKEN_BOT), h, m))
    #                  for h, m in fah_text_hours]
    # for t in fah_ranker_ts:
    #     t.start()

    # fah_grapher_t = Thread(target=fah_grapher, args=(BotHandler(TOKEN_BOT), 9, 0))
    # fah_grapher_t.start()
    fah_ranker_t = Thread(target=fah_ranker, args=(bot, 9, 0))
    fah_ranker_t.start()

    handler = CommandHandler(bot, tarallo, logs, tolab, users, people, conn, wol, quotes)

    birthday_wisher_t = Thread(target=handler.birthday_wisher)
    birthday_wisher_t.start()

    safety_test_reminder_t = Thread(target=handler.safety_test_reminder)
    safety_test_reminder_t.start()

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

            # Ignore edited messages
            elif 'edited_message' in last_update:
                continue

            # Ignore images, stickers and stuff like that
            elif 'message' in last_update and 'text' not in last_update['message']:
                continue

            # see https://core.telegram.org/bots/api#message
            elif 'message' in last_update and 'text' in last_update['message']:
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

                elif command[0] == "/location" or command[0] == "/location@weeelab_bot":
                    if len(command) < 2:
                        handler.item_command_error('location')
                    else:
                        handler.item_location(command[1])

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
                        handler.tolabGui()

                elif command[0] == "/tolab_no" or command[0] == "/tolab_no@weeelab_bot":
                    handler.tolab("no")

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

                elif command[0] == "/game" or command[0] == "/game@weeelab_bot":
                    if len(command) > 1:
                        handler.game(command[1])
                    else:
                        handler.game()

                elif command[0] == "/logout" or command[0] == "/logout@weeelab_bot":
                    if len(command) > 1:
                        # handler.logout(command[1:])
                        logout = Thread(target=handler.logout, args=(command[1:],))
                        logout.start()
                    else:
                        handler.logout_help()
                
                elif command[0] == "/login" or command[0] == "/login@weeelab_bot":
                    if len(command) == 2:
                        login = Thread(target=handler.login, args=(command[1:],))
                        login.start()
                    else:
                        handler.login_help()

                elif command[0] == "/door" or command[0] == "/door@weeelab_bot":
                    i_am_door = Thread(target=handler.i_am_door)
                    i_am_door.start()

                elif command[0] == "/status" or command[0] == "/status@weeelab_bot":
                    handler.status()

                elif command[0] == "/quote" or command[0] == "/quote@weeelab_bot":
                    author = None
                    if len(command) > 1:
                        author = " ".join(command[1:])
                    handler.quote(author)

                elif command[0] == "/motivami" or command[0] == "/motivami@weeelab_bot":
                    handler.motivami()

                elif command[0] == "/nextbirthdays" or command[0] == "/nextbirthdays@weeelab_bot":
                    handler.next_birthdays()

                elif command[0] == "/nexttests" or command[0] == "/nexttests@weeelab_bot":
                    handler.next_tests()

                else:
                    flag = True
                    user_id = last_update['message']['from']['id']
                    tolab_active_sessions = handler.get_tolab_active_sessions()
                    for idx, session in enumerate(tolab_active_sessions):
                        if user_id in session:
                            handler.tolab_callback(f"hour:{command[0]}", session[1], user_id)
                            flag = False
                            break
                    if flag:
                        handler.unknown()

            elif 'callback_query' in last_update:
                authorized = handler.read_user_from_callback(last_update)
                if not authorized:
                    continue

                # Handle button callbacks
                query = last_update['callback_query']['data']
                message_id = last_update['callback_query']['message']['message_id']
                user_id = last_update['callback_query']['from']['id']

                if query.startswith('wol_'):
                    handler.wol_callback(query, message_id)
                elif query.startswith('lofi_'):
                    handler.lofi_callback(query, message_id)
                elif query.startswith('weeelab_'):
                    handler.shutdown_callback(query, message_id, SSH_SCMA_USER, SSH_SCMA_HOST_IP, SSH_SCMA_KEY_PATH)
                elif query.startswith('i_am_door_'):
                    handler.shutdown_callback(query, message_id, SSH_PIALL_USER, SSH_PIALL_HOST_IP, SSH_PIALL_KEY_PATH)
                elif query.startswith('game_'):
                    handler.game_callback(query, message_id)
                elif query.startswith('tolab:'):
                    handler.tolab_callback(query, message_id, user_id)
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
