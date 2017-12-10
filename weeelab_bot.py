#!/usr/bin/env python
# coding:utf-8

"""
WEEELAB_BOT - Telegram bot.
Author: WeeeOpen Team
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
NOTE: The print commands are only for debug.
"""

# Modules
from variables import *  # internal library with the environment variables
import requests  # library to make requests to telegram server
import owncloud
# library to make requests to OwnCloud server, more details on
#  https://github.com/owncloud/pyocclient
import datetime  # library to handle time
import time
from datetime import timedelta
from collections import OrderedDict
import operator  # library to handle dictionary
import json  # library for evaluation of json file


class BotHandler:
    """ class with method used by the bot, for more details see
        https://core.telegram.org/bots/api
    """

    def __init__(self, token):
        """ init function to set bot token and reference url
        """
        self.token = token
        self.api_url = "https://api.telegram.org/bot{}/".format(token)
        # set bot url from the token

    def get_updates(self, offset=None, timeout=30):
        """ method to receive incoming updates using long polling
            [Telegram API -> getUpdates ]
        """
        params = {'offset': offset, 'timeout': timeout}
        print requests.get(self.api_url + 'getUpdates',
                           params).json()
        result = requests.get(self.api_url + 'getUpdates',
                              params).json()['result']
        # return an array of json
        return result

    def send_message(self, chat_id, text, parse_mode='Markdown',
                     disable_web_page_preview=True, reply_markup=None):
        """ method to send text messages [ Telegram API -> sendMessage ]
        """
        params = {'chat_id': chat_id, 'text': text, 'parse_mode': parse_mode,
                  'disable_web_page_preview': disable_web_page_preview,
                  'reply_markup': reply_markup}
        return requests.post(self.api_url + 'sendMessage', params)
        # On success, the sent Message is returned.

    def get_last_update(self, offset=None):
        """method to get last message if there is"""
        try:
            get_result = self.get_updates(offset)
            # recall the function to get updates
            if len(get_result) > 0:  # check if there are new messages
                return get_result[-1]  # return the last message in json format
            else:
                return -1
                # in case of error return error code used in the main function
        except (KeyError, ValueError):
            return -1


class Weeelab:
    """ class with method used by the bot.
    """

    def __init__(self):
        """ init function to set offset and create variable
        """
        # set at beginning an offset None for the get_updates function
        self.new_offset = None
        self.last_chat_id = None
        self.last_user_id = None
        self.last_user_name = None
        self.message_type = None
        self.last_chat_id = None
        self.complete_name = None
        self.log_file = None
        self.user_file = None
        self.log_lines = None
        self.lines_inlab = None
        self.log_update_data = None
        self.new_offset = None
        self.command = None
        self.oc = None
        # Initialize variables
        self.level = 0
        self.last_update = -1

    def name_ext(self, username):
        """
        Return <Name Surname> from <name.surname> string
        """
        return username.replace('.', ' ').title()

    def oc_conn(self):
        """ function to connect with owncloud
        """
        self.oc = owncloud.Client(OC_URL)
        # create an object of type Client to connect to the cloud url
        self.oc.login(OC_USER, OC_PWD)
        # connect to the cloud using authorize username and password

    def start(self, weee_bot):
        """ Command "/start", Start info
        """
        weee_bot.send_message(self.last_chat_id, '\
*WEEE-Open Telegram bot*.\nThe goal of this bot is to obtain information \
about who is currently in the lab, who has done what, compute some stats and, \
in general, simplify the life of our members and to avoid waste of paper \
as well. \nAll data is read from a weeelab log file, which is fetched from \
an OwnCloud shared folder. \nFor a list of the commands allowed send /help.', )

    def inlab(self, weee_bot):
        """ Command "/inlab", Show the number and the name of 
            people in lab.
        """
        user_inlab_list = ''
        people_inlab = self.log_file.count("INLAB")
        for index in self.lines_inlab:
            user_inlab = self.log_lines[index][
                         47:self.log_lines[index].rfind(">")]
            # extract the name of the person
            for user in self.user_file["users"]:
                user_complete_name = user["name"].lower() + \
                                     '.' + user["surname"].lower()
                if (user_inlab == user_complete_name and
                        (user["level"] == 1 or user["level"] == 2)):
                    user_inlab_list = user_inlab_list + '\n' + \
                                      '- *' + self.name_ext(user_inlab) + '*'
                elif user_inlab == user_complete_name:
                    user_inlab_list = user_inlab_list + \
                                      '\n' + '- ' + self.name_ext(user_inlab)
        if people_inlab == 0:
            # Check if there aren't people in lab
            # Send a message to the user that makes
            # the request /inlab
            weee_bot.send_message(self.last_chat_id,
                                  'Nobody is in lab right now.')
        elif people_inlab == 1:
            weee_bot.send_message(self.last_chat_id,
                                  'There is one student in lab right now:\n{}'
                                  .format(user_inlab_list))
        else:
            weee_bot.send_message(self.last_chat_id,
                                  'There are {} students in lab right now:\n{}'
                                  .format(people_inlab, user_inlab_list))

    def log(self, weee_bot):
        """ Command "/log", Show the complete LOG_PATH file 
            (only for admin user, by default only 5 lines)
            Command "/log [number]", Show the [number] most recent 
            lines of LOG_PATH file
            Command "/log all", Show all lines of LOG_PATH file.
        """
        if self.level == 1:
            lines_message = 0  # number of lines of the message
            log_data = ''
            log_print = ''
            # Check if the message is the command /log
            lines_to_print = len(self.log_lines)  # default lines number to send
            if len(self.command) > 1 and self.command[1].isdigit() \
                    and lines_to_print > int(self.command[1]):
                # check if the command is "/log [number]"
                lines_to_print = int(self.command[1])
            for lines_printed in reversed(range(0, lines_to_print)):
                if not ("INLAB" in self.log_lines[lines_printed]):
                    if log_data == self.log_lines[lines_printed][1:11]:
                        log_line_to_print = \
                            '_' + self.log_lines[lines_printed][
                                  47:self.log_lines[lines_printed].rfind(">")] \
                            + '_' + self.log_lines[lines_printed][
                                    self.log_lines[lines_printed].rfind(">")
                                    + 1:len(self.log_lines[lines_printed])]
                        log_print = log_print + '{}\n'.format(log_line_to_print)
                        lines_message += 1
                    else:
                        if len(self.command) == 1 and lines_message > 0:
                            lines_to_print = len(self.log_lines)
                        else:
                            log_data = self.log_lines[lines_printed][1:11]
                            log_line_to_print = \
                                '\n*' + log_data + '*\n_' \
                                + self.log_lines[lines_printed][
                                  47:self.log_lines[lines_printed].rfind(">")] \
                                + '_' + self.log_lines[lines_printed][
                                        self.log_lines[lines_printed].rfind(">")
                                        + 1:len(self.log_lines[lines_printed])]
                            log_print = \
                                log_print + '{}\n'.format(log_line_to_print)
                            lines_message += 1
                if lines_message > 25:
                    log_print = log_print.replace('[', '\[')
                    log_print = log_print.replace('::', ':')
                    weee_bot.send_message(self.last_chat_id,
                                          '{}\n'.format(log_print))
                    lines_message = 0
                    log_print = ''
            log_print = log_print.replace('[', '\[')
            log_print = log_print.replace('::', ':')
            weee_bot.send_message(self.last_chat_id,
                                  '{}\nLatest log update: *{}*'.format(
                                      log_print, self.log_update_data))
        else:
            weee_bot.send_message(
                self.last_chat_id,
                'Sorry! You are not allowed to use this function! \
\nOnly admin can use!')

    def stat(self, weee_bot):
        """ Command "/stat name.surname", 
            Show hours spent in lab by name.surname user.
        """
        user_hours = 0  # initialize hour variable, type int
        user_minutes = 0  # initialize minute variable, type int
        hours_sum = datetime.timedelta(hours=user_hours, minutes=user_minutes)
        found_user = False
        # create a control variable used
        # to check if name.surname is found
        allowed = False
        user_name = ""
        if len(self.command) == 1:
            user_name = self.complete_name
            # print user_name
            allowed = True
        elif (len(self.command) != 1) and (self.level == 1):
            # Check if the command has option or not
            user_name = str(self.command[1])
            # store the option in a variable
            allowed = True
        else:
            weee_bot.send_message(self.last_chat_id, 'Sorry! You are not allowed \
to see stat of other users! \nOnly admin can!')
        if allowed:
            for lines in self.log_lines:
                if not ("INLAB" in lines) and \
                        (user_name == lines[47:lines.rfind(">")]):
                    found_user = True
                    # extract the hours and minute
                    # from char 39 until ], splitted by :
                    (user_hours, user_minutes) = \
                        lines[39:lines.rfind("]")].split(':')
                    # convert hours and minutes in datetime
                    partial_hours = datetime.timedelta(
                        hours=int(user_hours), minutes=int(user_minutes))
                    hours_sum += partial_hours
                    # sum to the previous hours
            if not found_user:
                weee_bot.send_message(self.last_chat_id, 'No statistics for the \
given user. Have you typed it correctly? (name.surname)')
            else:
                total_second = hours_sum.total_seconds()
                total_hours = int(total_second // 3600)
                total_minutes = int((total_second % 3600) // 60)
                weee_bot.send_message(self.last_chat_id, 'Stat for the user {}\n\
HH:MM = {:02d}:{:02d}\n\nLatest log update:\n*{}*'.format(
                    self.name_ext(user_name), total_hours,
                    total_minutes, self.log_update_data))
                # write the stat of the user

    def top(self, weee_bot):
        """ Command "/top", 
            Show a list of the top users in lab (defaul top 50).
        """
        # Check if the message is the command /top
        users_name = []
        users_hours = {}
        top_list_print = 'Top User List!\n'
        position = 0
        number_top_list = 100
        today = datetime.date.today()
        month = today.month
        year = today.year
        month_log = 4
        year_log = 2017
        if self.level == 1:
            if len(self.command) == 1:
                month_log = month
                year_log = year
            elif self.command[1] == "all":
                month_log = 4
                year_log = 2017
            for log_datayear in range(year_log, year + 1):
                for log_datamonth in range(month_log, month + 1):
                    try:
                        if log_datamonth == month and log_datayear == year:
                            self.log_file = self.oc.get_file_contents(LOG_PATH)
                            # self.log_file = open(LOG_PATH).read()
                            self.log_lines = self.log_file.splitlines()
                        else:
                            if log_datamonth < 10:
                                datamonth = "0" + str(log_datamonth)
                            else:
                                datamonth = str(log_datamonth)
                            self.log_file = self.oc.get_file_contents(
                                LOG_BASE + "log" + str(log_datayear) +
                                datamonth + ".txt")
                            # self.log_file = open(LOG_BASE + "log" +
                            # str(log_datayear) + datamonth + ".txt")
                            self.log_lines = self.log_file.splitlines()
                        for lines in self.log_lines:
                            if not ("INLAB" in lines):
                                name = \
                                    lines[47:lines.rfind(">")].encode('utf-8')
                                (user_hours, user_minutes) = \
                                    lines[39:lines.rfind("]")].split(':')
                                partial_hours = datetime.timedelta(
                                    hours=int(user_hours),
                                    minutes=int(user_minutes))
                                if name in users_name:
                                    # check if user was already found
                                    users_hours[name] += partial_hours
                                    # add to the key with the same name
                                    # the value partial_hours
                                else:
                                    users_name.append(name)
                                    # create a new key with the name
                                    users_hours[name] = partial_hours
                                    # add the hours to the key
                    except owncloud.owncloud.HTTPResponseError:
                        print "Error open file."
            # sort the dict by value in descendant order
            sorted_top_list = sorted(users_hours.items(),
                                     key=operator.itemgetter(1), reverse=True)
            # print sorted_top_list
            for rival in sorted_top_list:
                # print the elements sorted
                if position < number_top_list:
                    # check if the list is completed
                    # extract the hours and minutes from dict,
                    # splitted by :
                    total_second = rival[1].total_seconds()
                    total_hours = int(total_second // 3600)
                    total_minutes = int((total_second % 3600) // 60)
                    # add the user to the top list
                    for user in self.user_file["users"]:
                        user_complete_name = user["name"].lower() + '.' + \
                                             user["surname"].lower()
                        if rival[0] == user_complete_name:
                            position += 1
                            # update the counter of position on top list
                            if user["level"] == 1 or user["level"] == 2:
                                top_list_print = \
                                    top_list_print + \
                                    '{}) \[{:02d}:{:02d}] *{}*\n'.format(
                                        position, total_hours,
                                        total_minutes, self.name_ext(rival[0]))
                            else:
                                top_list_print = \
                                    top_list_print + \
                                    '{}) \[{:02d}:{:02d}] {}\n'.format(
                                        position, total_hours,
                                        total_minutes, self.name_ext(rival[0]))
            weee_bot.send_message(self.last_chat_id,
                                  '{}\nLatest log update: \n*{}*'.format(
                                      top_list_print, self.log_update_data))
            # send the top list to the user
        else:
            weee_bot.send_message(
                self.last_chat_id,
                'Sorry! You are not allowed to use this function! \
\nOnly admin can use!')

    def user(self, weee_bot):
        """ Command "/user",
            Add a new user.
        """
        if self.level == 1:
            if len(self.command) < 6:
                weee_bot.send_message(
                    self.last_chat_id,
                    'Check the syntax for the command (/help)')
            else:
                new_user = OrderedDict()
                new_user['name'] = self.command[1]
                new_user['surname'] = self.command[2]
                new_user['serial'] = self.command[3]
                new_user['telegramID'] = self.command[4]
                if len(self.command) > 6:
                    new_user['nickname'] = self.command[5]
                    new_user['level'] = int(self.command[6])
                else:
                    new_user['nickname'] = " "
                    new_user['level'] = int(self.command[5])
                file_users = self.user_file
                file_users["users"].append(new_user)
                self.oc.put_file_contents(USER_PATH, json.dumps(file_users,
                                                                indent=4))
                weee_bot.send_message(self.last_chat_id, 'New user added.')
        else:
            weee_bot.send_message(
                self.last_chat_id,
                'Sorry! You are not allowed to use this function! \
\nOnly admin can use!')

    def help(self, weee_bot):
        """ Command "/help", Show an help.
        """
        help_message = "Available commands and options:\n\n\
/inlab - Show the people in lab\n/log - Show last 5 login\n+ _number_ - \
Show last _number_ login\n+ _all_ - Show all login\n/stat - Show hours spent \
in lab by the user\n"
        if self.level == 1:
            help_message += "\n*only for admin user*\n\
/stat _name.surname_ - Show hours spent in lab by this user\n\
/top - Show a list of top users in lab\n\
/user _name_ _surname_ _serial_ _telegramID_ _nickname_ (optional) _level_ - \
Add a new user. "
            weee_bot.send_message(self.last_chat_id, '{}'.format(help_message))
        else:
            weee_bot.send_message(self.last_chat_id,
                                  'Sorry! You are not allowed to use this \
bot \nPlease contact us [mail] (weeeopen@polito.it), visit our \
[WeeeOpen FB page] (https://www.facebook.com/weeeopenpolito/) and the site \
[WeeeOpen](http://weeeopen.polito.it/) for more info. \n\
After authorization /start the bot.')

    def load_data(self):
        """ Load the data for the script
        """
        try:
            self.complete_name = ''
            self.log_file = self.oc.get_file_contents(LOG_PATH)
            # log file stored in Owncloud server
            self.user_file = json.loads(self.oc.get_file_contents(USER_PATH),
                                        object_pairs_hook=OrderedDict)
            # self.user_file = json.loads(open(USER_PATH,'r+').read())
            # User data stored in Owncloud server
            self.log_lines = self.log_file.splitlines()
            self.lines_inlab = \
                [i for i, lines in enumerate(
                    self.log_lines) if 'INLAB' in lines]
            # store the data of the last update of the log file,
            # the data is in UTC so we add 2 for eu/it local time
            self.log_update_data = \
                self.oc.file_info(LOG_PATH).get_last_modified() \
                + timedelta(hours=2)
            last_update_id = self.last_update['update_id']
            # store the id of the bot taken from the message
            self.new_offset = last_update_id + 1
            # store the update id of the bot
            self.command = self.last_update['message']['text'].split()
            # store all the words in the message in an array
            # (split by space)
            self.last_chat_id = self.last_update['message']['chat']['id']
            # store the id of the chat between user and bot read from
            # the message in a variable
            self.last_user_id = self.last_update['message']['from']['id']
            # store the id of the user read from the message in a variable
            self.last_user_name = \
                self.last_update['message']['from']['first_name']
            # store the name of the user read from the message in a variable
            self.message_type = self.last_update['message']['chat']['type']
            for user in self.user_file["users"]:
                if user["telegramID"] == str(self.last_user_id):
                    self.level = user["level"]
                    self.complete_name = \
                        user["name"].lower() + '.' + user["surname"].lower()
            print self.last_update['message']  # DEBUG

        except KeyError:  # catch the exception if raised
            self.message_type = None
            print "ERROR!"  # DEBUG

    def update_user(self):
        """ Update the user of the bot
        """
        user_bot_contents = self.oc.get_file_contents(USER_BOT_PATH)
        # read the content of the user file stored in owncloud server
        if str(self.last_user_id) in user_bot_contents:
            # Check if the user is already recorded
            pass
        else:
            # Store a new user name and id in a file on owncloud server,
            # encoding in utf.8
            try:
                user_bot_contents = user_bot_contents.decode('utf-8') \
                                    + '\'' + last_user_name.decode('utf-8') \
                                    + '\'' + ': ' + '\'' + str(
                    last_user_id).decode('utf-8') \
                                    + '\'' + str(', ').decode('utf-8')
                oc.put_file_contents(
                    USER_BOT_PATH, user_bot_contents.encode('utf-8'))
                # write on the file the new data
            except (AttributeError, UnicodeEncodeError):
                print "ERROR user.txt"
                pass

    def main(self):
        function = {
            '/start': self.start,
            '/inlab': self.inlab,
            '/log': self.log,
            '/stat': self.stat,
            '/top': self.top,
            '/user': self.user,
            '/help': self.help
        }
        weee_bot = BotHandler(TOKEN_BOT)  # create the bot object
        self.oc_conn()
        self.new_offset = None
        while True:
            try:
                # call the function to check if there are new messages
                # and takes the last message from the server
                self.last_update = weee_bot.get_last_update(self.new_offset)
                # Initialize variables
                self.level = 0
                self.last_chat_id = None
                self.last_user_id = None
                self.last_user_name = None
                self.message_type = None
                if self.last_update != -1:
                    self.load_data()
                    if self.message_type == "private":
                        if self.level != 0:
                            function.get(self.command[0])(weee_bot)
                        else:
                            weee_bot.send_message(
                                self.last_chat_id,
                                'Sorry! You are not allowed to use this \
bot \nPlease contact us [mail] (weeeopen@polito.it), visit our \
[WeeeOpen FB page] (https://www.facebook.com/weeeopenpolito/) and the site \
[WeeeOpen](http://weeeopen.polito.it/) for more info. \n\
After authorization /start the bot.')
                    else:
                        print "group"  # DEBUG
                self.update_user()
            except requests.exceptions.ConnectionError:
                pass


# call the main() until a keyboard interrupt is called
if __name__ == '__main__':
    try:
        Bot = Weeelab()
        Bot.main()
    except KeyboardInterrupt:
        exit()
