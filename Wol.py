import subprocess


class Wol:
    @staticmethod
    def send(mac):
        subprocess.run(["wol", "-p", "9", mac])
