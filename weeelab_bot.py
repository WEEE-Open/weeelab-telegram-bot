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
# noinspection PyUnresolvedReferences
import owncloud
import datetime  # library to handle time
from datetime import timedelta
import json
import re
import traceback


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

	def get_updates(self, timeout=30):
		""" method to receive incoming updates using long polling
			[Telegram API -> getUpdates ]
		"""
		# try:
		params = {'offset': self.offset, 'timeout': timeout}
		# print offset
		print((requests.get(self.api_url + 'getUpdates', params).json()))
		result = requests.get(self.api_url + 'getUpdates', params).json()['result']  # return an array of json
		if len(result) > 0:
			self.offset = result[-1]['update_id'] + 1

		return result

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
			'reply_markup': reply_markup}
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


class TaralloSession:
	def __init__(self):
		self.cookie = None
		self.last_status = None

	def login(self, username, password):
		"""
		Try to log in, if necessary.

		:rtype: bool
		:return: Logged in or not?
		"""

		if self.cookie is not None:
			whoami = requests.get(TARALLO + '/v1/session', cookies=self.cookie)
			self.last_status = whoami.status_code

			if whoami.status_code == 200:
				return True

			# Attempting to log in would be pointless, there's some other error
			if whoami.status_code != 403:
				return False

		body = dict()
		body['username'] = username
		body['password'] = password
		headers = {"Content-Type": "application/json"}
		res = requests.post(TARALLO + '/v1/session', data=json.dumps(body), headers=headers)
		self.last_status = res.status_code

		if res.status_code == 200:
			self.cookie = res.cookies
			return True
		else:
			return False

	def get_history(self, item, limit):
		history = requests.get(TARALLO + '/v1/items/{}/history?length={}'.format(item, str(limit)), cookies=self.cookie)
		self.last_status = history.status_code

		if history.status_code == 200:
			return history.json()['data']
		elif history.status_code == 404:
			return None
		else:
			raise RuntimeError("Unexpected return code")


class WeeelabLogs:
	def __init__(self, oc: owncloud):
		self.log = []
		self.log_last_update = None
		self.users = None
		self.oc = oc

	def get_log(self):
		self.log = []
		log_file = self.oc.get_file_contents(LOG_PATH).decode('utf-8')
		log_lines = log_file.splitlines()

		for line in log_lines:
			if len(line) == 0:
				# TODO: remove this print if it actually prints.
				# or the "if" if it never prints.
				print("Empty line in log (probably last line) => this check is actually useful")
				continue
			self.log.append(WeeelabLine(line))

		# store the data of the last update of the log file,
		# the data is in UTC so we add 2 for eu/it local time
		# TODO: this is sometimes +1 because ora legale, use a timezone library and compute correct time
		self.log_last_update = self.oc.file_info(LOG_PATH).get_last_modified() + timedelta(hours=2)

		return self

	def get_users(self):
		self.users = None
		self.users = json.loads(self.oc.get_file_contents(USER_PATH).decode('utf-8'))["users"]

		return self

	def get_inlab(self):
		# PyCharm, you suggested that, why are you making me remove it?
		# noinspection PyUnusedLocal
		line: WeeelabLine
		inlab = []

		for line in self.log:
			if line.inlab:
				inlab.append(line.username)

		return inlab

	def search_user_tid(self, user_id: str):
		"""
		Search user data from a Telegram ID

		:param user_id: Telegram user ID
		:return: The entry from users.json or None
		"""
		for user in self.users:
			if user["telegramID"] == str(user_id):
				return user
		return None

	def search_user_username(self, username: str):
		"""
		Search user data from a username

		:param username: Normalized, unique, official username
		:return: The entry from users.json or None
		"""
		for user in self.users:
			if username == user["username"]:
				return user
		return None

	def store_new_user(self, tid, name, surname, username):
		new_users_file = self.oc.get_file_contents(USER_BOT_PATH)
		new_users = new_users_file.decode('utf-8')

		if str(tid) in new_users:
			return
		else:
			# Store a new user name and id in a file on owncloud server,
			# encoding in utf.8
			try:
				new_users = new_users + "{} {} (@{}): {}\n".format(name, surname, username, id)
				self.oc.put_file_contents(USER_BOT_PATH, new_users.encode('utf-8'))
			except (AttributeError, UnicodeEncodeError):
				print("ERROR writing user.txt")
				pass

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


def escape_all(string):
	return string.replace('_', '\\_').replace('*', '\\*').replace('`', '\\``').replace('[', '\\[')


def main():
	"""main function of the bot"""
	oc = owncloud.Client(OC_URL)
	oc.login(OC_USER, OC_PWD)

	weee_bot = BotHandler(TOKEN_BOT)
	tarallo = TaralloSession()
	logs = WeeelabLogs(oc)

	while True:
		# call the function to check if there are new messages
		last_update = weee_bot.get_last_update()

		# TODO: remove all this stuff man mano
		hours_sum = datetime.timedelta(hours=0, minutes=0)
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

		if last_update != -1:
			try:
				command = last_update['message']['text'].split()

				last_chat_id = last_update['message']['chat']['id']
				last_user_id = last_update['message']['from']['id']
				last_user_name = last_update['message']['from']['first_name']

				if 'username' in last_update['message']['from']:
					last_user_username = last_update['message']['from']['username']
				else:
					last_user_username = "no username"
				if 'surname' in last_update['message']['from']:
					last_user_surname = last_update['message']['from']['surname']
				else:
					last_user_surname = ""

				message_type = last_update['message']['chat']['type']
				print(last_update['message'])

				# Don't respond to messages in group chats
				if message_type == "private":
					# TODO: get_users downloads users.json from the cloud. For performance this could be done only once in a while
					logs.get_users()
					user = logs.search_user_tid(last_user_id)

					if user is None or user["level"] == 0:
						weee_bot.send_message(
							last_chat_id, 'Sorry! You are not allowed to use this bot \
\nPlease contact us via email (weeeopen@polito.it), visit our \
<a href="https://www.facebook.com/weeeopenpolito/">WEEE Open FB page</a> or the site \
<a href="http://weeeopen.polito.it/">WEEE Open</a> for more info.\
\nAfter authorization /start the bot again.')
						if user is None:
							logs.store_new_user(last_user_id, last_user_name, last_user_surname, last_user_username)
					else:
						# If this is unused it's alright, evey command sets it without concatenation the first time
						# It's useful to keep around to prevent accidental concatenations and if we ever want to
						# prepend something to every message...
						msg = ''
						level = user["level"]

						if command[0] == "/start" or \
							command[0] == "/start@weeelab_bot":
							weee_bot.send_message(last_chat_id, '\
*WEEE Open Telegram bot*.\nThe goal of this bot is to obtain information \
about who is currently in the lab, who has done what, compute some stats and, \
in general, simplify the life of our members and to avoid waste of paper \
as well. \nAll data is read from a weeelab log file, which is fetched from \
an OwnCloud shared folder.\nFor a list of the commands allowed send /help.', )

						# --- INLAB ------------------------------------------------------------------------------------
						if command[0] == "/inlab" or \
							command[0] == "/inlab@weeelab_bot":

							inlab = logs.get_log().get_inlab()

							if len(inlab) == 0:
								msg = 'Nobody is in lab right now.'
							elif len(inlab) == 1:
								msg = 'There is one student in lab right now:\n'
							else:
								msg = 'There are {} students in lab right now:\n'.format(str(len(inlab)))

							for username in inlab:
								entry = logs.search_user_username(username)
								if entry is None:
									msg = msg + '\n- <b>{}</b>'.format(username)
								else:
									msg = msg + '\n- <b>{}</b>'.format(logs.get_name_and_surname(entry))

							weee_bot.send_message(last_chat_id, msg)

						# --- HISTORY ----------------------------------------------------------------------------------
						elif command[0] == "/history" or \
							command[0] == "/history@weeelab_bot":
							if len(command) < 2:
								weee_bot.send_message(
									last_chat_id, 'Sorry insert the item to search')
							else:
								item = command[1]
								if len(command) < 3:
									limit = 4
								else:
									limit = int(command[2])
									if limit < 1:
										limit = 1
									elif limit > 50:
										limit = 50
								try:
									if tarallo.login(BOT_USER, BOT_PSW):
										history = tarallo.get_history(item, limit)
										if history is None:
											weee_bot.send_message(last_chat_id, 'Item {} not found.'.format(item))
										else:
											msg = '<b>History of item {}</b>\n'.format(item)
											entries = 0
											for index in range(0, len(history)):
												change = history[index]['change']
												h_user = history[index]['user']
												h_location = history[index]['other']
												h_time = datetime.datetime.fromtimestamp(int(history[index]['time'])).strftime('%d-%m-%Y %H:%M:%S')
												if change == 'M':
													msg += '➡️ Moved to <b>{}</b>\n'.format(h_location)
												elif change == 'U':
													msg += '🛠️ Updated features\n'
												elif change == 'C':
													msg += '📋 Created\n'
												elif change == 'R':
													msg += '✏️ Renamed from <b>{}</b>\n'.format(h_location)
												elif change == 'D':
													msg += '❌ Deleted\n'
												else:
													msg += 'Unknown change {}'.format(change)
												entries += 1
												msg += '{} by {}\n\n'.format(h_time, h_user)
												if entries >= 4:
													weee_bot.send_message(last_chat_id, msg)
													msg = ''
													entries = 0
											if entries != 0:
												weee_bot.send_message(last_chat_id, msg)
									else:
										weee_bot.send_message(last_chat_id, 'Sorry, cannot authenticate with T.A.R.A.L.L.O.')
								except RuntimeError:
									fail_msg = 'Sorry, an error has occurred (HTTP status: {}).'.format(str(tarallo.last_status))
									weee_bot.send_message(last_chat_id,	fail_msg)

						# --- LOG --------------------------------------------------------------------------------------
						elif command[0] == "/log" or \
							command[0] == "/log@weeelab_bot":

							# TODO: this also downloads the file for each request. Maybe don't do it every time.
							logs.get_log()
							logs.log.reverse()
							today_only = False

							if len(command) > 1 and command[1].isdigit():
								# Command is "/log [number]"
								lines_to_print = int(command[1])
							elif len(command) == 1:
								# Won't actually print 50 lines, it stops as soon as it finds another day
								today_only = True
								lines_to_print = 50
							else:
								lines_to_print = 500

							# Can't print lines that don't exist
							lines_to_print = min(len(logs.log), lines_to_print)

							days = {}
							# TODO: this range stuff can probably be simplified
							for i in reversed(list(range(0, lines_to_print))):
								line = logs.log[1 + i - len(logs.log)]
								day = '<b>' + line.day() + '</b>\n'

								if day not in days:
									if today_only and len(days) >= 1:
										break
									days[day] = []

								entry = logs.search_user_username(line.username)
								if entry:
									print_name = logs.get_name_and_surname(entry)
								else:
									print_name = entry.username

								if line.inlab:
									days[day].append('<i>{}</i> is in lab\n'.format(print_name))
								else:
									days[day].append('<i>{}</i>: {}\n'.format(print_name, line.text))

							msg = ''
							for day in days:
								msg = msg + day + ''.join(days[day]) + '\n'

							msg = msg + 'Latest log update: <b>{}</b>'.format(logs.log_last_update)
							weee_bot.send_message(last_chat_id, msg)

						# --- STAT -------------------------------------------------------------------------------------
						elif command[0] == "/stat" or \
							command[0] == "/stat@weeelabdev_bot":
							weee_bot.send_message(last_chat_id, "Yet to be reimplemented :(\n\
							Also this time will count your hours across every month, not just the last one.")
	# 						found_user = False
	# 						# create a control variable used
	# 						# to check if name.surname is found
	# 						allowed = False
	# 						if len(command) == 1:
	# 							user_name = complete_name
	# 							# print user_name
	# 							allowed = True
	# 						elif (len(command) != 1) and \
	# 								(level == 1):
	# 							# Check if the command has option or not
	# 							user_name = str(command[1])
	# 							# store the option in a variable
	# 							allowed = True
	# 						else:
	# 							weee_bot.send_message(last_chat_id,
	# 							                      'Sorry! You are not allowed \
	# to see stat of other users! \nOnly admin can!')
	# 						if allowed:
	# 							for lines in log_lines:
	# 								if not ("INLAB" in lines) and \
	# 										(user_name == lines[47:lines.rfind(">")]):
	# 									found_user = True
	# 									# extract the hours and minute
	# 									# from char 39 until ], splitted by :
	# 									(user_hours, user_minutes) = lines[39:44].split(':')
	# 									# convert hours and minutes in datetime
	# 									partial_hours = datetime.timedelta(
	# 										hours=int(user_hours),
	# 										minutes=int(user_minutes))
	# 									hours_sum += partial_hours
	# 							# sum to the previous hours
	# 							if not found_user:
	# 								weee_bot.send_message(last_chat_id,
	# 								                      'No statistics for the \
	# given user. Have you typed it correctly? (name.surname)')
	# 							else:
	# 								total_second = hours_sum.total_seconds()
	# 								total_hours = int(total_second // 3600)
	# 								total_minutes = int(
	# 									(total_second % 3600) // 60)
	# 								weee_bot.send_message(
	# 									last_chat_id, 'Stat for {}\n\
	# HH:MM = {:02d}:{:02d}\n\nLatest log update:\n*{}*'.format(user_name, total_hours, total_minutes, logs.log_last_update))
	# 					# write the stat of the user

						# --- TOP --------------------------------------------------------------------------------------
						elif command[0] == "/top" or \
							command[0] == "/top@weeelabdev_bot":
							weee_bot.send_message(last_chat_id, "Yet to be reimplemented :(")
	# 						# Check if the message is the command /top
	# 						if level == 1:
	# 							if len(command) == 1:
	# 								month_log = month
	# 								month_range = month
	# 								year_log = year
	# 							elif command[1] == "all":
	# 								month_log = 1
	# 								month_range = 12
	# 								year_log = 2017
	# 							for log_datayear in range(year_log, year + 1):
	# 								for log_datamonth in range(month_log, month_range + 1):
	# 									try:
	# 										if log_datamonth == month and log_datayear == year:
	# 											log_file = oc.get_file_contents(LOG_PATH)
	# 											log_lines = log_file.splitlines()
	# 										else:
	# 											if log_datamonth < 10:
	# 												datamonth = "0" + str(log_datamonth)
	# 											else:
	# 												datamonth = str(log_datamonth)
	# 											log_file = oc.get_file_contents(
	# 												LOG_BASE + "log" + str(log_datayear) + datamonth + ".txt")
	# 											log_lines = log_file.splitlines()
	# 										for lines in log_lines:
	# 											if not ("INLAB" in lines):
	# 												name = lines[47:lines.rfind(">", 47, 80)].encode(
	# 													'utf-8')
	# 												(user_hours, user_minutes) = \
	# 													lines[39:lines.rfind("]", 39, 46)].split(':')
	# 												partial_hours = datetime.timedelta(
	# 													hours=int(user_hours),
	# 													minutes=int(user_minutes))
	# 												if name in users_name:
	# 													# check if user was already found
	# 													users_hours[name] += partial_hours
	# 												# add to the key with the same name
	# 												# the value partial_hours
	# 												else:
	# 													users_name.append(name)
	# 													# create a new key with the name
	# 													users_hours[name] = partial_hours
	# 										# add the hours to the key
	# 									except owncloud.owncloud.HTTPResponseError:
	# 										print()
	# 										"Error open file."
	# 							# sort the dict by value in descendet order
	# 							sorted_top_list = sorted(
	# 								list(users_hours.items()),
	# 								key=operator.itemgetter(1), reverse=True)
	# 							# print sorted_top_list
	# 							for rival in sorted_top_list:
	# 								# print the elements sorted
	# 								if position < number_top_list:
	# 									# check if the list is completed
	# 									# extract the hours and minutes from dict,
	# 									# splitted by :
	# 									total_second = rival[1].total_seconds()
	# 									total_hours = int(total_second // 3600)
	# 									total_minutes = int(
	# 										(total_second % 3600) // 60)
	# 									# add the user to the top list
	# 									for user in user_file["users"]:
	# 										if rival[0] == user["username"]:
	# 											position += 1
	# 											# update the counter of position on top list
	# 											if user["level"] == 1 or \
	# 												user["level"] == 2:
	# 												top_list_print = \
	# 													top_list_print \
	# 													+ '{}) \[{:02d}:{:02d}] \
	# *{}*\n'.format(position, total_hours, total_minutes, get_name_and_surname(user))
	# 											else:
	# 												top_list_print = \
	# 													top_list_print \
	# 													+ '{}) \[{:02d}:{:02d}] \
	# {}\n'.format(position, total_hours, total_minutes, get_name_and_surname(user))
	# 							weee_bot.send_message(
	# 								last_chat_id,
	# 								'{}\nLatest log update: \n*{}*'.format(
	# 									top_list_print, log_update_data))
	# 						# send the top list to the user
	# 						else:
	# 							weee_bot.send_message(
	# 								last_chat_id,
	# 								'Sorry! You are not allowed to use this \
	# function! \nOnly admin can use!')
						# Show help

						# --- HELP -------------------------------------------------------------------------------------
						elif command[0] == "/help" or \
							command[0] == "/help@weeelab_bot":
							help_message = "Available commands and options:\n\n\
/inlab - Show the people in lab\n\
/log - Show log of the day\n\
/log <i>n</i> - Show last <i>n</i> log lines\n\
/log <i>all</i> - Show entire log from this month\n\
/stat - Show hours you've spent in lab\n\
/history <i>item</i> - Show history for an item, straight outta T.A.R.A.L.L.O.\n\
/history <i>item</i> <i>n</i> - Show <i>n</i> history entries\n"
							if level == 1:
								help_message += "\n<b>only for admin user</b>\n\
/stat <i>name.surname</i> - Show hours spent in lab by this user\n\
/top - Show a list of top users by hours spent\n"
							weee_bot.send_message(last_chat_id, help_message)
						else:
							weee_bot.send_message(last_chat_id, "What? I don't understand :(\nType /help to see a list of commands")
			except:  # catch the exception if raised
				message_type = None
				print("ERROR!")
				print(traceback.format_exc())


# call the main() until a keyboard interrupt is called
if __name__ == '__main__':
	try:
		main()
	except KeyboardInterrupt:
		exit()
