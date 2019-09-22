from time import time
from dataclasses import dataclass
from typing import Optional
import ldap


class LdapConnection:
    def __init__(self, server: str, bind_dn: str, password: str):
        self.bind_dn = bind_dn
        self.password = password
        self.server = server

    def __enter__(self):
        self.conn = ldap.initialize(f"ldap://{self.server}:389")
        self.conn.protocol_version = ldap.VERSION3
        self.conn.start_tls_s()
        self.conn.simple_bind_s(self.bind_dn, self.password)
        return self.conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.conn.unbind_s()


class DuplicateEntryError(BaseException):
    pass

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
    nickname: Optional[str] = None

    @staticmethod
    def search(tgid: int, tgnick: Optional[str], admin_groups, conn, tree: str):
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
            return None
        if len(result) > 1:
            raise DuplicateEntryError(f"Telegram ID {tgid} associated to {len(result)} entries")

        tup = result.pop()
        dn = tup[0]
        attributes = tup[1]
        del tup, result

        isadmin = False
        for group in attributes['memberof']:
            if str(group) in admin_groups:
                isadmin = True
                break
        if 'telegramnickname' in attributes:
            nickname = attributes['telegramnickname'][0].decode()
        else:
            nickname = None
        if nickname != tgnick:
            User.update_nickname(dn, tgnick, conn)
        return User(dn, tgid, attributes['uid'][0].decode(), attributes['cn'][0].decode(), attributes['givenname'][0].decode(), attributes['sn'][0].decode(), isadmin, tgnick)

    @staticmethod
    def update_nickname(dn: str, new_nickname: Optional[str], conn):
        if new_nickname is None:
            conn.modify_s(dn, [
                (ldap.MOD_DELETE, 'telegramNickname', None)
            ])
        else:
            conn.modify_s(dn, [
                (ldap.MOD_REPLACE, 'telegramNickname', new_nickname.encode('UTF-8'))
            ])

    def __post_init__(self):
        self.update()

    def update(self):
        self.last_update = time()
