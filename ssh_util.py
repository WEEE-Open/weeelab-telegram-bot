# from https://qxf2.com/blog/ssh-using-python-paramiko/

import os
import sys

import paramiko

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import socket
from sys import stderr


class SSHUtil:
    """Class to connect to a remote server"""

    def __init__(self,
                 host: str = None,
                 username: str = None,
                 password: str = None,
                 timeout: float = 10.,
                 commands: [str] = None,
                 private_key_path: str = None,
                 connection_port: int = 22,
                 upload_remote_filepath: str = None,
                 upload_local_filepath: str = None,
                 download_remote_filepath: str = None,
                 download_local_filepath: str = None
                 ):  # come on, constructor, don't be sad :)
        self.ssh_output = None
        self.ssh_error = None
        self.return_code = None
        self.client = None
        self.host = host
        self.username = username
        self.password = password
        self.timeout = float(timeout)
        self.commands = commands
        self.pkey = private_key_path
        self.port = connection_port
        self.upload_remote_filepath = upload_remote_filepath
        self.upload_local_filepath = upload_local_filepath
        self.download_remote_filepath = download_remote_filepath
        self.download_local_filepath = download_local_filepath

        if host is None:
            raise HostNotFoundException
        if password is None and private_key_path is None:
            raise AuthenticationMethodNotFoundException
        if self.commands is None:
            print("WARNING: No commands given.", file=stderr)
        print(isinstance(self.commands, str))
        print(type(self.commands))
        print(self.commands)
        if isinstance(self.commands, str):
            self.commands = [self.commands]  # make iterable list from single command
            print(self.commands)

    def connect(self):
        """Login to the remote server"""
        try:
            # Paramiko.SSHClient can be used to make connections to the remote server and transfer files
            print("Establishing SSH connection...")
            self.client = paramiko.SSHClient()
            # Parsing an instance of the AutoAddPolicy to set_missing_host_key_policy() changes it to allow any host.
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            # Connect to the server
            if self.password is None:
                # this needs to be a PEM key (begins with RSA not OPENSSH)
                self.pkey = paramiko.RSAKey.from_private_key_file(self.pkey)
                self.client.connect(hostname=self.host, port=self.port, username=self.username, pkey=self.pkey,
                                    timeout=self.timeout, allow_agent=False, look_for_keys=False)
                print("Connected to the server", self.host)
            else:
                self.client.connect(hostname=self.host, port=self.port, username=self.username, password=self.password,
                                    timeout=self.timeout, allow_agent=False, look_for_keys=False)
                print("Connected to the server", self.host)
        except paramiko.AuthenticationException:
            print("Authentication failed, please verify your credentials")
            result_flag = False
        except paramiko.SSHException as sshException:
            print("Could not establish SSH connection: %s" % sshException)
            result_flag = False
        except socket.timeout as e:
            print("Connection timed out")
            result_flag = False
        except Exception as e:
            print('\nException in connecting to the server')
            print('PYTHON SAYS:', e)
            result_flag = False
            self.client.close()
        else:
            result_flag = True

        return result_flag

    def execute_command(self, commands=None):
        """Execute a command on the remote host.Return a tuple containing
        an integer status and a two strings, the first containing stdout
        and the second containing stderr from the command."""
        self.ssh_output = None
        result_flag = True
        if commands is None:
            commands = self.commands
        try:
            if self.connect():
                for command in commands:
                    print("Executing command --> {}".format(command))
                    stdin, stdout, stderr = self.client.exec_command(command, timeout=10)
                    self.ssh_output = stdout.read()
                    self.ssh_error = stderr.read()
                    self.return_code = stdout.channel.recv_exit_status()
                    if self.ssh_error:
                        print(
                            "Problem occurred while running command:" + command + " The error is " + self.ssh_error.decode())
                        result_flag = False
                    else:
                        print("Command execution completed successfully:", '"' + command + '"')
                        print("stdout:\n" + self.ssh_output.decode())
                        print("return code is", self.return_code)
            else:
                print("Could not establish SSH connection")
                result_flag = False
        except socket.timeout as e:
            print("Command timed out.", command)
            self.client.close()
            result_flag = False
        except paramiko.SSHException:
            print("Failed to execute the command!", command)
            self.client.close()
            result_flag = False

        return result_flag

    def upload_file(self, uploadlocalfilepath, uploadremotefilepath):
        """This method uploads the file to remote server"""
        result_flag = True
        try:
            if self.connect():
                ftp_client = self.client.open_sftp()
                ftp_client.put(uploadlocalfilepath, uploadremotefilepath)
                ftp_client.close()
                self.client.close()
            else:
                print("Could not establish SSH connection")
                result_flag = False
        except Exception as e:
            print('\nUnable to upload the file to the remote server', uploadremotefilepath)
            print('PYTHON SAYS:', e)
            result_flag = False
            ftp_client.close()
            self.client.close()

        return result_flag

    def download_file(self, downloadremotefilepath, downloadlocalfilepath):
        """This method downloads the file from remote server"""
        result_flag = True
        try:
            if self.connect():
                ftp_client = self.client.open_sftp()
                ftp_client.get(downloadremotefilepath, downloadlocalfilepath)
                ftp_client.close()
                self.client.close()
            else:
                print("Could not establish SSH connection")
                result_flag = False
        except Exception as e:
            print('\nUnable to download the file from the remote server', downloadremotefilepath)
            print('PYTHON SAYS:', e)
            result_flag = False
            ftp_client.close()
            self.client.close()

        return result_flag


class HostNotFoundException(Exception):
    def __init__(self, arg):
        self.strerror = arg


class AuthenticationMethodNotFoundException(Exception):
    def __init__(self, arg):
        self.strerror = arg


# ---USAGE EXAMPLES
if __name__ == '__main__':
    print("Start of %s" % __file__)

    # Initialize the ssh object
    ssh_obj = SSHUtil()

    # Sample code to execute commands
    if ssh_obj.execute_command(ssh_obj.commands):
        print("Commands executed successfully\n")
    else:
        print("Unable to execute the commands\n")

    """
    #Sample code to upload a file to the server
    if ssh_obj.upload_file(ssh_obj.uploadlocalfilepath,ssh_obj.uploadremotefilepath) is True:
        print "File uploaded successfully", ssh_obj.uploadremotefilepath
    else:
        print  "Failed to upload the file"

    #Sample code to download a file from the server
    if ssh_obj.download_file(ssh_obj.downloadremotefilepath,ssh_obj.downloadlocalfilepath) is True:
        print "File downloaded successfully", ssh_obj.downloadlocalfilepath
    else:
        print  "Failed to download the file"
    """
