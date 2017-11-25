# weeelab-telegram-bot
[![License](http://img.shields.io/:license-GPL3.0-blue.svg)](http://www.gnu.org/licenses/gpl-3.0.html)
![Version](https://img.shields.io/badge/version-1.0-yellow.svg)

WEEE-Open Telegram bot.

The goal of this bot is to obtain information about who is currently in the lab,  
who has done what, compute some stats and, in general, simplify the life of our members...  
And to avoid waste of paper as well.  

All data is read from a  [weeelab](https://github.com/WEEE-Open/weeelab) log file, which is fetched from an OwnCloud shared folder.  

## Installation

Deployment of this bot has been tested only on Heroku: just connect the repo.

For local installation, get `python2` and run `pip install -r requirements.txt` to install dependencies.

`weeelab_bot.py` is the main script, and it requires some environment variables (imported from `variables.py`) to 
run:
* `OC_URL`: Url of the owncloud server
* `OC_USER`: OwnCloud username
* `OC_PWD`: OwnCloud password
* `TOKEN_BOT`: Telegram token for the bot API
* `LOG_PATH`: Path of the file to read in owncloud (/folder/file.txt)
* `USER_BOTH_PATH`: Path of the file to store bot users in OwnCloud (/folder/file.txt)
* `USER_PATH`: Path of the file with authorized users in OwnCloud (/folder/file.json)

## Command syntax
`/start` the bot and type `/[COMMAND] [OPTION]`.  

Available commands:

* `inlab` : Show the people in lab
* `log`   : Show the complete OC_PATH file (only for admin user, by default lines of the day)
  * `[number]`   : Show the `[number]` most recent lines of `OC_PATH` file.
  * `all`      : Show all lines of OC_PATH file.
* `stat`   :  Show hours spent in lab by the user.
* `top`   :  Show a list of top users in lab (only for admin, default top 50)
  * `all`      : Show the top users from the beginning.
* `user`  :  Add a new user (name surname serial telegramID nickname (optional) level).
* `help`  :  Show all the commands and a short explanations.

## TODO

- [X] Implement a function to compute stats for a user
- [X] Finish documenting commands
