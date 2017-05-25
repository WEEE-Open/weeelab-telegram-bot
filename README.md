# weeelab-telegram-bot
[![License](http://img.shields.io/:license-GPL3.0-blue.svg)](http://www.gnu.org/licenses/gpl-3.0.html)
![Version](https://img.shields.io/badge/version-0.1-yellow.svg)

WEEE-Open Telegram bot.

The goal of this bot is to obtain information about who is currently in the lab,  
who has done what, compute some stats and, in general, simplify the life of our members...  
And to avoid waste of paper as well.  

All data is read from a  [weeelab](https://github.com/WEEE-Open/weeelab) log file, which is fetched from an OwnCloud shared folder.  

## Installation

Deployment of this bot has been tested only on Heroku: just connect the repo.

For local installation, get `python2` and run `pip install -r requirements.txt` to install dependencies.

`bot` is the main script, and it requires some environment variables to 
run:
* `OC_PATH`: path of the file to read in owncloud (/folder/file.txt)
* `OC_URL`: url of the owncloud server
* `OC_USER`: OwnCloud username
* `OC_PWD`: OwnCloud password
* `TOKEN_BOT`: Telegram token for the bot API
* `USER_LIST_NAME`: Python list of the user allowed to use the bot


## Command syntax
`/start` the bot and type `/[COMMAND] [OPTION]`.  

Available commands:

* `inlab` : Show the number of people in lab.
* `log`   : Show the complete OC_PATH file (only for admin user, by default only 5 lines)
  * `[number]`   : Show the `[number]` most recent lines of `OC_PATH` file.
  * `all`      : Show all lines of OC_PATH file.
* `stat name.surname`  :  Show hours spent in lab by this user.
* `top`   :  Show a list of top users in lab (defaul top 10)
  * `[number]`     : Show the top `[number]` elements.
  * `all`      : Show list with all users.
* `sync`  :  Show last edit date and time of the `OC_PATH` file.
* `help`  :  Show all the commands and a short explanations.

## TODO

- [X] Implement a function to compute stats for a user
- [X] Finish documenting commands
