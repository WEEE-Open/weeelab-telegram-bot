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
# library to make requests to OwnCloud server, more details on
#  https://github.com/owncloud/pyocclient
import owncloud
import datetime  # library to handle time
import time
from datetime import timedelta
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

    def get_updates(self, offset=None, limit=1, timeout=30):
        """ method to receive incoming updates using long polling
            [Telegram API -> getUpdates ]
        """
        global new_offset
        try:
            params = {'offset': offset, 'limit': limit, 'timeout': timeout}
            #print offset
            result = requests.get(self.api_url + 'getUpdates',
                                  params).json()['result']  # return an array of json
        except KeyError: # catch the exception if raised
            result = None
            new_offset= None
            # print "ERROR! (getupdate)" # DEBUG
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
        get_result = self.get_updates(offset)  # recall the function to get updates
        if not get_result:
            return -1
        elif len(get_result) > 0:  # check if there are new messages
            return get_result[-1]  # return the last message in json format
        else:
            return -1
            # in case of error return an error code used in the main function


def name_ext(username):
    """ function created by @Hyd3L, complete code at
        https://github.com/WEEE-Open/weeelab
        Return <Name Surname> from <name.surname> string
    """
    first_name = username.split('.')[0].capitalize()
    # Extract the name and capitalize it
    last_name = username.split('.')[1].capitalize()
    # Extract the surname and capitalize it
    return first_name + " " + last_name
    # Return a string of type "Name Surname"


# set variable used in main function
weee_bot = BotHandler(TOKEN_BOT)  # create the bot object


def main():
    """main function of the bot"""
    global new_offset
    oc = owncloud.Client(OC_URL)
    # create an object of type Client to connect to the cloud url
    oc.login(OC_USER, OC_PWD)
    # connect to the cloud using authorize username and password
    new_offset = None
    # set at beginning an offset None for the get_updates function

    while True:
        # call the function to check if there are new messages
        last_update = weee_bot.get_last_update(new_offset)
        # takes the last message from the server
        # Variables for /inlab command
        user_inlab_list = ''
        # people_inlab = 0
        # found_user_inlab = False
        # Variables for /log command
        lines_to_print = 0  # default lines number to send
        lines_message = 0  # number of lines of the message
        log_data = ''
        log_print = ''
        # Variables for /stat command
        user_hours = 0  # initialize hour variable, type int
        user_minutes = 0  # initialize minute variable, type int
        # total_hours = 0
        # total_minutes = 0
        hours_sum = datetime.timedelta(hours=user_hours, minutes=user_minutes)
        # Initialize hours sum variable, type datetime
        # Variables for /top command
        users_name = []
        users_hours = {}
        top_list_print = 'Top User List!\n'
        position = 0
        number_top_list = 50
        today = datetime.date.today()
        month = today.month
        year = today.year
        # Initialize variables
        level = 0
        last_chat_id = None
        last_user_id = None
        last_user_name = None
        message_type = None

        if last_update != -1:
            try:
                complete_name = ''
                log_file = oc.get_file_contents(LOG_PATH)
                # log file stored in Owncloud server
                user_file = json.loads(oc.get_file_contents(USER_PATH))
                # User data stored in Owncloud server
                log_lines = log_file.splitlines()
                lines_inlab = [i for i, lines in enumerate(log_lines)
                               if 'INLAB' in lines]
                # store the data of the last update of the log file,
                # the data is in UTC so we add 2 for eu/it local time
                log_update_data = oc.file_info(LOG_PATH) \
                                      .get_last_modified() + timedelta(hours=2)
                last_update_id = last_update['update_id']
                # store the id of the bot taken from the message
                new_offset = last_update_id + 1
                # store the update id of the bot
                command = last_update['message']['text'].split()
                # store all the words in the message in an array
                # (split by space)
                last_chat_id = last_update['message']['chat']['id']
                # store the id of the chat between user and bot read from
                # the message in a variable
                last_user_id = last_update['message']['from']['id']
                # store the id of the user read from the message in a variable
                last_user_name = last_update['message']['from']['first_name']
                # store the name of the user read from the message
                # in a variable
                # last_user_username = last_update['message']['from']['username']
                # store the username of the user read from the message
                # in a variable
                message_type = last_update['message']['chat']['type']
                for user in user_file["users"]:
                    if user["telegramID"] == str(last_user_id):
                        level = user["level"]
                        complete_name = \
                            user["name"].lower() + '.' \
                            + user["surname"].lower()
                print last_update['message']  # DEBUG

            except KeyError:  # catch the exception if raised
                message_type = None
                print "ERROR!"  # DEBUG

            if message_type == "private":
                if level != 0:  # check if the user is allowed to use the bot
                    """ ADD COMMANDS HERE """
                    # Short introduction
                    """ Command "/start", Start info
                    """
                    if command[0] == "/start" or \
                                    command[0] == "/start@weeelabdev_bot":
                        # Check if the message is the command /start
                        weee_bot.send_message(last_chat_id, '\
*WEEE-Open Telegram bot*.\nThe goal of this bot is to obtain information \
about who is currently in the lab, who has done what, compute some stats and, \
in general, simplify the life of our members and to avoid waste of paper \
as well. \nAll data is read from a weeelab log file, which is fetched from \
an OwnCloud shared folder. \nFor a list of the commands allowed send /help.',)
                    # Show how many students are in lab right now
                    """ Command "/inlab", Show the number and the name of 
                        people in lab.
                    """
                    if command[0] == "/inlab" or \
                                    command[0] == "/inlab@weeelabdev_bot":
                        # Check if the message is the command /inlab
                        people_inlab = log_file.count("INLAB")
                        for index in lines_inlab:
                            user_inlab = log_lines[index][
                                         47:log_lines[index].rfind(">")]
                            # extract the name of the person
                            for user in user_file["users"]:
                                user_complete_name = user["name"].lower() \
                                                     + '.' \
                                                     + user["surname"].lower()
                                if (user_inlab == user_complete_name and
                                        (user["level"] == 1 or user["level"] == 2)):
                                    user_inlab_list = user_inlab_list + '\n' \
                                                      + '- *' + \
                                                      name_ext(user_inlab) \
                                                      + '*'
                                elif user_inlab == user_complete_name:
                                    user_inlab_list = user_inlab_list + '\n' \
                                                      + '- ' \
                                                      + name_ext(user_inlab)
                        if people_inlab == 0:
                            # Check if there aren't people in lab
                            # Send a message to the user that makes
                            # the request /inlab
                            weee_bot.send_message(
                                last_chat_id, 'Nobody is in lab right now.')
                        elif people_inlab == 1:
                            weee_bot.send_message(last_chat_id,
                                                  'There is one student in \
lab right now:\n{}'.format(user_inlab_list))
                        else:
                            weee_bot.send_message(last_chat_id,
                                                  'There are {} students in \
lab right now:\n{}'.format(people_inlab, user_inlab_list))

                    # Show log file
                    """ Command "/log", Show the complete LOG_PATH file 
                        (only for admin user, by default only 5 lines)
                        Command "/log [number]", Show the [number] most recent 
                        lines of LOG_PATH file
                        Command "/log all", Show all lines of LOG_PATH file.
                    """
                    # Api limit message too long
                    if command[0] == "/log" or \
                                    command[0] == "/log@weeelabdev_bot":
                        # Check if the message is the command /log
                        lines_to_print = len(log_lines)
                        if len(command) > 1 and command[1].isdigit() \
                                and lines_to_print > int(command[1]):
                            # check if the command is "/log [number]"
                            lines_to_print = int(command[1])
                        for lines_printed in range(0, lines_to_print):
                            if not ("INLAB" in log_lines[lines_printed]):
                                if log_data == log_lines[lines_printed][1:11]:
                                    log_line_to_print = \
                                        '_' \
                                        + log_lines[lines_printed][
                                          47:log_lines[
                                              lines_printed].rfind(">")] \
                                        + '_' + log_lines[lines_printed][
                                                log_lines[lines_printed].rfind(
                                                    ">")
                                                + 1:len(
                                                    log_lines[lines_printed])]
                                    log_print = log_print + '{}\n'.format(
                                        log_line_to_print)
                                    lines_message += 1
                                else:
                                    if len(command) == 1 and lines_message > 0:
                                        lines_printed = len(log_lines)
                                    else:
                                        log_data = log_lines[
                                                lines_printed][1:11]
                                        log_line_to_print = \
                                             '\n*' + log_data + '*\n_' \
                                            + log_lines[lines_printed][
                                            47:log_lines[
                                            lines_printed].rfind(">")] \
                                             + '_' + log_lines[lines_printed][
                                            log_lines[lines_printed]
                                            .rfind(">")
                                            + 1:len(log_lines[lines_printed])]
                                        log_print = log_print + '{}\n'.format(
                                            log_line_to_print)
                                        lines_message += 1
                            if lines_message > 25:
                                log_print = log_print.replace('[', '\[')
                                log_print = log_print.replace('::', ':')
                                weee_bot.send_message(last_chat_id,
                                                          '{}\n'.format(
                                                              log_print))
                                lines_message = 0
                                log_print = ''
                        log_print = log_print.replace('[', '\[')
                        log_print = log_print.replace('::', ':')
                        weee_bot.send_message(
                            last_chat_id, '{}\nLatest log update: *{}*'
                                .format(log_print, log_update_data))

                    # Show the stat of the user
                    """ Command "/stat name.surname", 
                        Show hours spent in lab by name.surname user.
                    """
                    if command[0] == "/stat" or \
                                    command[0] == "/stat@weeelabdev_bot":
                        # Check if the message is the command /stat
                        found_user = False
                        # create a control variable used
                        # to check if name.surname is found
                        allowed = False
                        if len(command) == 1:
                            user_name = complete_name
                            # print user_name
                            allowed = True
                        elif (len(command) != 1) and \
                                (level == 1):
                            # Check if the command has option or not
                            user_name = str(command[1])
                            # store the option in a variable
                            allowed = True
                        else:
                            weee_bot.send_message(last_chat_id,
                                                  'Sorry! You are not allowed \
to see stat of other users! \nOnly admin can!')
                        if allowed:
                            for lines in log_lines:
                                if not ("INLAB" in lines) and \
                                        (user_name == lines[
                                                      47:lines.rfind(">")]):
                                    found_user = True
                                    # extract the hours and minute
                                    # from char 39 until ], splitted by :
                                    (user_hours, user_minutes) = \
                                        lines[39:lines.rfind("]")].split(':')
                                    # convert hours and minutes in datetime
                                    partial_hours = datetime.timedelta(
                                        hours=int(user_hours),
                                        minutes=int(user_minutes))
                                    hours_sum += partial_hours
                                    # sum to the previous hours
                            if not found_user:
                                weee_bot.send_message(last_chat_id,
                                                      'No statistics for the \
given user. Have you typed it correctly? (name.surname)')
                            else:
                                total_second = hours_sum.total_seconds()
                                total_hours = int(total_second // 3600)
                                total_minutes = int(
                                    (total_second % 3600) // 60)
                                weee_bot.send_message(
                                    last_chat_id, 'Stat for the user {}\n\
HH:MM = {:02d}:{:02d}\n\nLatest log update:\n*{}*'.format(name_ext(
                                        user_name), total_hours, total_minutes,
                                        log_update_data))
                                # write the stat of the user

                    # Show the top list of the users
                    """ Command "/top", 
                        Show a list of the top users in lab (defaul top 50).
                    """
                    if command[0] == "/top" or \
                                    command[0] == "/top@weeelabdev_bot":
                        # Check if the message is the command /top
                        if level == 1:
                            if len(command) == 1:
                                month_log = month
                                year_log = year
                            elif command[1] == "all":
                                month_log = 4
                                year_log = 2017
                            for log_datayear in range(year_log, year+1):
                                for log_datamonth in range(month_log, month+1):
                                    try:
                                        if month_log == month and year_log == year:
                                            log_file = oc.get_file_contents(LOG_PATH)
                                            log_lines = log_file.splitlines()
                                        else:
                                            if log_datamonth < 10:
                                                datamonth = "0" + str(log_datamonth)
                                            else:
                                                datamonth = str(log_datamonth)
                                            log_file = oc.get_file_contents(LOG_BASE + "log" + str(log_datayear) + datamonth + ".txt")
                                            log_lines = log_file.splitlines()
                                        for lines in log_lines:
                                            if not ("INLAB" in lines):
                                                name = lines[47:lines.rfind(">")].encode(
                                                    'utf-8')
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
                            # sort the dict by value in descendet order
                            sorted_top_list = sorted(users_hours.items(),
                                                    key=operator.itemgetter(
                                                    1), reverse=True)
                            # print sorted_top_list
                            for rival in sorted_top_list:
                                # print the elements sorted
                                if position < number_top_list:
                                    # check if the list is completed
                                    # extract the hours and minutes from dict,
                                    # splitted by :
                                    total_second = rival[1].total_seconds()
                                    total_hours = int(total_second // 3600)
                                    total_minutes = int(
                                            (total_second % 3600) // 60)
                                    # add the user to the top list
                                    for user in user_file["users"]:
                                        user_complete_name = \
                                            user["name"].lower() + '.' \
                                            + user["surname"].lower()
                                        if rival[0] == user_complete_name:
                                            position += 1
                                            # update the counter of position on top list
                                            if user["level"] == 1 or \
                                                        user["level"] == 2:
                                                top_list_print = \
                                                        top_list_print \
                                                        + '{}) \[{:02d}:{:02d}] \
*{}*\n'.format(position, total_hours, total_minutes, name_ext(rival[0]))
                                            else:
                                                top_list_print = \
                                                    top_list_print \
                                                    + '{}) \[{:02d}:{:02d}] \
{}\n'.format(position, total_hours, total_minutes, name_ext(rival[0]))
                            weee_bot.send_message(
                                    last_chat_id,
                                    '{}\nLatest log update: \n*{}*'.format(
                                    top_list_print, log_update_data))
                                    # send the top list to the user
                        else:
                            weee_bot.send_message(
                                last_chat_id,
                                'Sorry! You are not allowed to use this \
function! \nOnly admin can use!')
                    # Show help
                    """ Command "/help", Show an help.
                    """
                    if command[0] == "/help" or \
                                    command[0] == "/help@weeelab_bot":
                        # Check if the message is the command /help
                        help_message = "Available commands and options:\n\n\
/inlab - Show the people in lab\n/log - Show last 5 login\n+ _number_ - \
Show last _number_ login\n+ _all_ - Show all login\n/stat - Show hours spent \
in lab by the user\n"
                        if level == 1:
                            help_message += "\n*only for admin user*\n\
/stat _name.surname_ - Show hours spent in lab by this user\n\
/top - Show a list of top users in lab\n"
                        weee_bot.send_message(
                            last_chat_id, '{}'.format(help_message))
                else:
                    weee_bot.send_message(
                        last_chat_id, 'Sorry! You are not allowed to use this \
bot \nPlease contact us [mail] (weeeopen@polito.it), visit our \
[WeeeOpen FB page] (https://www.facebook.com/weeeopenpolito/) and the site \
[WeeeOpen](http://weeeopen.polito.it/) for more info. \n\
After authorization /start the bot.')
            else:
                print "group"  # DEBUG
            user_bot_contents = oc.get_file_contents(USER_BOT_PATH)
            # read the content of the user file stored in owncloud server
            if str(last_user_id) in user_bot_contents:
                # Check if the user is already recorded
                pass
            else:
                # Store a new user name and id in a file on owncloud server,
                # encoding in utf.8
                try:
                    user_bot_contents = user_bot_contents.decode('utf-8') \
                                    + '\'' + last_user_name.encode('utf-8') \
                                    + '\'' + ': ' + '\'' + str(last_user_id) \
                                    + '\'' + ', '
                    oc.put_file_contents(
                        USER_BOT_PATH, user_bot_contents.encode('utf-8'))
                # write on the file the new data
                except AttributeError:
                    pass


# call the main() until a keyboard interrupt is called
if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        exit()
