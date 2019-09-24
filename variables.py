import os  # system library needed to read the environment variables

# get environment variables
OC_URL = os.environ.get('OC_URL')  # url of the OwnCloud server
OC_USER = os.environ.get('OC_USER')  # OwnCloud username
OC_PWD = os.environ.get('OC_PWD')  # OwnCloud password
# path of the file with authorized users in OwnCloud (/folder/file.json)
USER_PATH = os.environ.get('USER_PATH')
# path of the log file to read in OwnCloud (/folder/file.txt)
LOG_PATH = os.environ.get('LOG_PATH')
TOLAB_PATH = os.environ.get('TOLAB_PATH')
# base path
LOG_BASE = os.environ.get('LOG_BASE')
# path of the file to store bot users in OwnCloud (/folder/file.txt)
USER_BOT_PATH = os.environ.get('USER_BOT_PATH')
TOKEN_BOT = os.environ.get('TOKEN_BOT')  # Telegram token for the bot API
BOT_USER = os.environ.get('BOT_USER')  # user tarallo
BOT_PSW = os.environ.get('BOT_PSW')  # password tarallo
TARALLO = os.environ.get('TARALLO')  # Url tarallo

LDAP_SERVER = os.environ.get('LDAP_SERVER')  # ldap.example.com
LDAP_USER = os.environ.get('LDAP_USER')  # cn=whatever,ou=whatever
LDAP_PASS = os.environ.get('LDAP_PASS')  # foo
LDAP_SUFFIX = os.environ.get('LDAP_SUFFIX')  # dc=weeeopen,dc=it
LDAP_TREE_PEOPLE = os.environ.get('LDAP_TREE_PEOPLE')
LDAP_TREE_INVITES = os.environ.get('LDAP_TREE_INVITES')
LDAP_ADMIN_GROUPS = os.environ.get('LDAP_ADMIN_GROUPS').split('|')  # ou=Group,dc=weeeopen,dc=it|ou=OtherGroup,dc=weeeopen,dc=it

INVITE_LINK = os.environ.get('INVITE_LINK')  # https://example.com/register.php?invite= (invite code will be appended, no spaces in invite code)
