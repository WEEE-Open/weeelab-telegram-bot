from time import time
from dataclasses import dataclass
from typing import Optional, Iterable, List, Dict
import ldap


class LdapConnection:
    def __init__(self, server: str, bind_dn: str, password: str):
        self.bind_dn = bind_dn
        self.password = password
        self.server = server

    def __enter__(self):
        print("Connecting to LDAP")
        self.conn = ldap.initialize(f"ldap://{self.server}:389")
        self.conn.protocol_version = ldap.VERSION3
        self.conn.start_tls_s()
        self.conn.simple_bind_s(self.bind_dn, self.password)
        if self.conn is None:
            raise LdapConnectionError
        return self.conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        print("Disconnecting from LDAP")
        self.conn.unbind_s()


class LdapConnectionError(BaseException):
    pass


class DuplicateEntryError(BaseException):
    pass


class AccountLockedError(BaseException):
    pass


class AccountNotFoundError(BaseException):
    pass


class Users:
    def __init__(self, admin_groups: List[str], tree: str):
        self.__users: Dict[int, User] = {}
        self.admin_groups = admin_groups
        self.tree = tree

    def get(self, tgid, nickname: Optional[str], conn: LdapConnection):
        if not isinstance(tgid, int):
            raise IndexError(f"{tgid} is not an int")

        user = None
        # Try to get cached user
        if tgid in self.__users:
            user = self.__users[tgid]
            if not user.need_update():
                return user

        with conn as c:
            # Got it but it's stale?
            if user is not None:
                try:
                    if user.need_update():
                        user.update(c, self.admin_groups, True, nickname)
                except (AccountNotFoundError, AccountLockedError, DuplicateEntryError):
                    del self.__users[tgid]
                    user = None

            # Deleted stale user or didn't get it?
            if user is None:
                user = User.search(tgid, nickname, self.admin_groups, c, self.tree)
                self.__users[tgid] = user

        return user


@dataclass
class Person:
    uid: str
    cn: str
    isadmin: bool
    nickname: Optional[str]
    tgid: Optional[int]


class People:
    def __init__(self, admin_groups: List[str], tree: str):
        self.__people = {}
        self.last_update = 0
        self.tree = tree
        self.admin_groups = admin_groups

    def get(self, uid: str, conn: LdapConnection):
        if time() - self.last_update > 3600:
            with conn as c:
                print("Sync people from LDAP")
                self.__sync(c)
        uid = uid.lower()
        if uid in self.__people:
            return self.__people[uid]
        else:
            return None

    def __sync(self, conn):
        result = conn.search_s(self.tree, ldap.SCOPE_SUBTREE, f"(objectClass=weeeOpenPerson)", (
            'uid',
            'cn',
            'memberof',
            'telegramnickname',
            'telegramid'
        ))

        for dn, attributes in result:
            person = Person(
                attributes['uid'][0].decode(),
                attributes['cn'][0].decode(),
                User.is_admin(self.admin_groups, attributes),
                attributes['telegramnickname'][0].decode() if 'telegramnickname' in attributes else None,
                int(attributes['telegramid'][0].decode()) if 'telegramid' in attributes else None,
            )
            self.__people[person.uid.lower()] = person

        self.last_update = time()

# noinspection PyAttributeOutsideInit
@dataclass
class User:
    dn: str
    tgid: int
    uid: str
    cn: str
    givenname: str
    surname: str
    isadmin: bool
    nickname: Optional[str]

    def __post_init__(self):
        self.__set_update_time()

    def __set_update_time(self):
        self.last_update = time()

    def need_update(self):
        return time() - self.last_update > 3600

    def update(self, conn, admin_groups: List[str], also_nickname: bool, nickname: Optional[str] = None):
        print(f"Update {self.tgid} ({self.dn})")
        result = conn.read_s(self.dn, None, (
            'uid',
            'cn',
            'givenname',
            'sn',
            'memberof',
            'telegramnickname',
            'telegramid',
            'nsaccountlock'
        ))
        if len(result) == 0:
            raise AccountNotFoundError()
        if len(result) > 1:
            raise DuplicateEntryError(f"DN {self.dn} associated to {len(result)} entries (how!?)")

        dn, attributes = User.__extract_the_only_result(result)
        del result

        if 'nsaccountlock' in attributes:
            raise AccountLockedError()

        # self.tgid = int(attributes['tgid'][0].decode())
        self.uid = attributes['uid'][0].decode()
        self.cn = attributes['cn'][0].decode()
        self.givenname = attributes['givenname'][0].decode()
        self.surname = attributes['surname'][0].decode()
        self.isadmin = User.is_admin(admin_groups, attributes)
        if also_nickname:
            if User.__get_stored_nickname(attributes) != nickname:
                User.__update_nickname(dn, nickname, conn)
        self.__set_update_time()

    @staticmethod
    def search(tgid: int, tgnick: Optional[str], admin_groups, conn, tree: str):
        print(f"Search {tgid}")
        result = conn.search_s(tree, ldap.SCOPE_SUBTREE, f"(&(objectClass=weeeOpenPerson)(telegramId={tgid}))", (
            'uid',
            'cn',
            'givenname',
            'sn',
            'memberof',
            'telegramnickname',
            'telegramid',
            'nsaccountlock'
        ))
        if len(result) == 0:
            raise AccountNotFoundError()
        if len(result) > 1:
            raise DuplicateEntryError(f"Telegram ID {tgid} associated to {len(result)} entries")

        dn, attributes = User.__extract_the_only_result(result)
        del result

        if 'nsaccountlock' in attributes:
            raise AccountLockedError()

        isadmin = User.is_admin(admin_groups, attributes)
        nickname = User.__get_stored_nickname(attributes)

        if nickname != tgnick:
            User.__update_nickname(dn, tgnick, conn)
        # self.__set_update_time() done in __post_init___
        return User(dn, tgid, attributes['uid'][0].decode(), attributes['cn'][0].decode(), attributes['givenname'][0].decode(), attributes['sn'][0].decode(), isadmin, tgnick)

    @staticmethod
    def __get_stored_nickname(attributes):
        if 'telegramnickname' in attributes:
            nickname = attributes['telegramnickname'][0].decode()
        else:
            nickname = None
        return nickname

    @staticmethod
    def is_admin(admin_groups, attributes):
        if 'memberof' not in attributes:
            return False
        for group in attributes['memberof']:
            if group.decode() in admin_groups:
                return True
        return False

    @staticmethod
    def __extract_the_only_result(result):
        tup = result.pop()
        dn = tup[0]
        attributes = tup[1]
        return dn, attributes

    @staticmethod
    def __update_nickname(dn: str, new_nickname: Optional[str], conn):
        if new_nickname is None:
            conn.modify_s(dn, [
                (ldap.MOD_DELETE, 'telegramNickname', None)
            ])
        else:
            conn.modify_s(dn, [
                (ldap.MOD_REPLACE, 'telegramNickname', new_nickname.encode('UTF-8'))
            ])
