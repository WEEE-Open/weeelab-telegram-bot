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
* `OC_PATH`: TODO (format?)
* `OC_URL`: TODO (which URL? Where do I find it?)
* `OC_USER`: OwnCloud username
* `OC_PWD`: OwnCloud password
* `TOKEN_BOT`: Telegram token for the bot API
* `USER_LIST_NAME`: TODO (list format: comma-separated, space-separated, 
are spaces allowed?)
* `USERS`: TODO (what?)

## Command syntax
`/start` the bot and type a command.  

Available commands:  
  `lab`  : Show the number of people in lab.  
  `log`  : Show the complete log (only for admin user).  
  `inlab`:   
  `stat` :  
  `top`  :  
  `sync` :  

## TODO

- [ ] Implement a function to compute stats for a user
- [ ] Finish documenting commands
