import os  # system library needed to read the environment variables


def __unpack_wol(wol):
    wol = wol.split("|")
    result = {}
    for machine in wol:
        machine = machine.split(":", 1)
        result[machine[0]] = machine[1]
    return result


# get environment variables
OC_URL = os.environ.get("OC_URL")  # url of the OwnCloud server
OC_USER = os.environ.get("OC_USER")  # OwnCloud username
OC_PWD = os.environ.get("OC_PWD")  # OwnCloud password
# path of the log file to read in OwnCloud (/folder/file.txt)
LOG_PATH = os.environ.get("LOG_PATH")
TOLAB_PATH = os.environ.get("TOLAB_PATH")
QUOTES_PATH = os.environ.get("QUOTES_PATH")
QUOTES_GAME_PATH = os.environ.get("QUOTES_GAME_PATH")
DEMOTIVATIONAL_PATH = os.environ.get("DEMOTIVATIONAL_PATH")
# base path
LOG_BASE = os.environ.get("LOG_BASE")
# path of the file to store bot users in OwnCloud (/folder/file.txt)
USER_BOT_PATH = os.environ.get("USER_BOT_PATH")
TOKEN_BOT = os.environ.get("TOKEN_BOT")  # Telegram token for the bot API
TARALLO = os.environ.get("TARALLO")  # tarallo URL
TARALLO_TOKEN = os.environ.get("TARALLO_TOKEN")  # tarallo token

LDAP_SERVER = os.environ.get("LDAP_SERVER")  # ldap://ldap.example.com:389
LDAP_USER = os.environ.get("LDAP_USER")  # cn=whatever,ou=whatever
LDAP_PASS = os.environ.get("LDAP_PASS")  # foo
LDAP_SUFFIX = os.environ.get("LDAP_SUFFIX")  # dc=weeeopen,dc=it
LDAP_TREE_GROUPS = os.environ.get("LDAP_TREE_GROUPS")  # ou=Groups,dc=weeeopen,dc=it
LDAP_TREE_PEOPLE = os.environ.get("LDAP_TREE_PEOPLE")  # ou=People,dc=weeeopen,dc=it
LDAP_TREE_INVITES = os.environ.get("LDAP_TREE_INVITES")  # ou=Invites,dc=weeeopen,dc=it
LDAP_ADMIN_GROUPS = os.environ.get("LDAP_ADMIN_GROUPS")  # ou=Group,dc=weeeopen,dc=it|ou=OtherGroup,dc=weeeopen,dc=it
if LDAP_ADMIN_GROUPS is not None:
    LDAP_ADMIN_GROUPS = LDAP_ADMIN_GROUPS.split("|")

INVITE_LINK = os.environ.get("INVITE_LINK")  # https://example.com/register.php?invite= (invite code will be appended, no spaces in invite code)

SSH_SCMA_USER = os.environ.get("SSH_SCMA_USER")  # foo
SSH_SCMA_HOST_IP = os.environ.get("SSH_SCMA_HOST_IP")  # 10.20.30.40
SSH_SCMA_KEY_PATH = os.environ.get("SSH_SCMA_KEY_PATH")  # /home/whatever/ssh_key

SSH_PIALL_USER = os.environ.get("SSH_PIALL_USER")
SSH_PIALL_HOST_IP = os.environ.get("SSH_PIALL_HOST_IP")
SSH_PIALL_KEY_PATH = os.environ.get("SSH_PIALL_KEY_PATH")

WOL_MACHINES = os.environ.get("WOL_MACHINES")  # machine:00:0a:0b:0c:0d:0e|other:10:2a:3b:4c:5d:6e
if WOL_MACHINES is not None:
    WOL_MACHINES = __unpack_wol(WOL_MACHINES)
WOL_WEEELAB = os.environ.get("WOL_WEEELAB")  # 00:0a:0b:0c:0d:0e
WOL_I_AM_DOOR = os.environ.get("WOL_I_AM_DOOR")

MAX_WORK_DONE = int(os.environ.get("MAX_WORK_DONE"))  # 2000

WEEE_CHAT_ID = int(os.environ.get("WEEE_CHAT_ID"))
WEEE_FOLD_ID = int(os.environ.get("WEEE_FOLD_ID"))
WEEE_CHAT2_ID = int(os.environ.get("WEEE_CHAT2_ID"))

LOCAL_WEEELAB = bool(os.environ.get("LOCAL_WEEELAB", False))  # 1, True
USE_GRILLO_DB = bool(os.environ.get("USE_GRILLO_DB", False))  # 1, True
GRILLO_DB_HOST = os.environ.get("GRILLO_DB_HOST")
GRILLO_DB_PORT = int(os.environ.get("GRILLO_DB_PORT"))
GRILLO_DB_NAME = os.environ.get("GRILLO_DB_NAME")
GRILLO_DB_USER = os.environ.get("GRILLO_DB_USER")
GRILLO_DB_PASS = os.environ.get("GRILLO_DB_PASS")
