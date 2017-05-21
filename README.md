# weeelab-telegram-bot
[![License](http://img.shields.io/:license-GPL3.0-blue.svg)](http://www.gnu.org/licenses/gpl-3.0.html)
![Version](https://img.shields.io/badge/version-0.1-yellow.svg)

WEEE Open Telegram bot.

The goal of this bot is to obtain information of who's currently in 
the lab, who has done what, compute some stats and in general simplify 
life. And avoid more paper sign sheets.

All data is read from a  [weeelab](https://github.com/WEEE-Open/weeelab) log 
file, which is fetched from an OwnCloud shared folder.

## Installation

Deployment of this bot has been tested only on Heroku: just connect the 
repo.

For local installation, get Python 2 and run `pip install -r 
requirements.txt` to install dependencies.

`bot` is the main program, and it requires some environment variables to 
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
    `inlab` : Show the number of people in lab.  
    `log`   : Show the complete OC_PATH file (only for admin user, by default only 5 lines)
        -   `number`   : Insert a number and show the `number` of lines of `OC_PATH` file.
    `stat`  :  Show the hours in lab of the user (option needed)
        -   `name.surname`  : Show the hours for this user.
    `top`   :  Show a list of the top users in lab (defaul top 10)
        -   `number`   : Insert a number and show the list with `number` element;
        -   `all`      : Show the list of all the users.
    `sync`  :  Show the info about last edit of the `OC_PATH` file.

## TODO

- [X] Implement a function to compute stats for a user
- [X] Finish documenting commands
