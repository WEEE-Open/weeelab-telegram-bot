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
* `help`  :  Show all the commands and a short explanations.

## Specifica "formale"/TODO

Dividere in classi autocontenute che abbiano un senso, eventualmente riutilizzabili nel weeelab.

### Classe Riga
- Costruttore che accetta data login e nome utente e durata (opzionale), altro costruttore che accetta riga del log (se si possono fare costruttori multipli)
- Contiene i dati della riga
- La data si memorizza con una libreria opportuna
- Nel log restano data, ora di ingresso, durata o `INLAB` o altro identificatore di chi e' in lab (oltre a nome e attivita' svolte)
- Fare parser del log che usa un for o `split` con un numero limitato di frammenti o qualcosa del genere, non puo' esplodere tutto se c'e' il separatore nella descrizione attivita' svolte
- Funzioni varie per aggiungere e modificare date e altre informazioni
- toString che spara fuori riga del log

### Classe LogFile (o interfaccia, meglio, sempre che in Python ci siano)
- Funzione che legge tutto il file e restituisce array di Riga
- Funzioni varie (readLast, readLastNRighe, Write, etc...) che maneggiano solo oggetti Riga
- Se ritenete utile: funzione setFile che imposta il nome dei file da scrivere, se usata più volte ne imposta >1 e Write scrive tutti i file
- In qualche modo fare la cosa della sostituzione della riga quando si fa il logout (ingegnatevi, siete ingegneri)
- Implementazione separata, o anche la stessa, che legge/scrive su OwnCloud con opportuna libreria
- In futuro potrebbe essere implementata con altri metodi di recupero/scrittura del file (e.g. accesso a a qualche server), dev'essere trasparente, devo poter infilare la nuova classe e il bot non deve esplodere

### Tutto il resto

Nell'attuale mega-classe generale oppure procedurale e basta, non e' obbligatorio mettere TUTTO in una classe

### Varie ed eventuali
- Togliere 1 commento per riga, e' inutile e non aggiunge nulla
- Non inizializzare inutilmente le variabili utilizzate nei foreach, visto che il foreach le inizializza
- Python 3
- Le classi sopra descritte vanno utilizzate anche nel weeelab, quando sara' riscritto in Python 3. Implementare le parti necessarie al bot e basta, il resto lo faremo dopo e separeremo i repo.

### Branch
- `master` versione di produzione del bot
- `dev` versione di sviluppo, utilizzata dal bot dev
- `dev-telepot` da cancellare\mergiare
