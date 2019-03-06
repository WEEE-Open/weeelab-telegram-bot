import json

import requests


# TODO: remove this class, replace with python-tarallo
class TaralloSession:
    def __init__(self, url: str):
        self.cookie = None
        self.last_status = None
        self.url = url

    def login(self, username, password):
        """
        Try to log in, if necessary.

        :rtype: bool
        :return: Logged in or not?
        """

        if self.cookie is not None:
            whoami = requests.get(self.url + '/v1/session', cookies=self.cookie)
            self.last_status = whoami.status_code

            if whoami.status_code == 200:
                return True

            # Attempting to log in would be pointless, there's some other error
            if whoami.status_code != 401:
                return False

        body = dict()
        body['username'] = username
        body['password'] = password
        headers = {"Content-Type": "application/json"}
        res = requests.post(self.url + '/v1/session', data=json.dumps(body), headers=headers)
        self.last_status = res.status_code

        if res.status_code == 204:
            self.cookie = res.cookies
            return True
        else:
            return False

    def get_history(self, item, limit):
        history = requests.get(self.url + '/v1/items/{}/history?length={}'.format(item, str(limit)), cookies=self.cookie)
        self.last_status = history.status_code

        if history.status_code == 200:
            return history.json()['data']
        elif history.status_code == 404:
            return None
        else:
            raise RuntimeError("Unexpected return code")
