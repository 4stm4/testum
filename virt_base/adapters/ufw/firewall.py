from paramiko import SSHClient
from .status_parser import parse_ufw_status


class FirewallManager:
    def __init__(self, hostname, port, username, password):
        self.host = hostname
        self.port = port
        self.username = username
        self.password = password

    def _connect(self):
        self.client = SSHClient()
        self.client.load_system_host_keys()
        self.client.connect(hostname=self.host, port=self.port, username=self.username, password=self.password)


    def _disconnect(self):
        if self.client:
            self.client.close()
            self.client = None

    def _execute_command(self, command):
        self._connect()
        _, stdout, stderr = self.client.exec_command(command)
        output = stdout.readlines()
        self._disconnect()
        # stdin = stdin.read().decode()
        # output = stdout.read().decode()
        # errors = stderr.read().decode()
        # print('output', stdin, output, errors)
        # if errors:
        #     raise Exception(f"Error executing command: {errors}")

        return output

    def status(self):
        command = 'sudo ufw status'
        try:
            output = self._execute_command(command)
            result_dict = parse_ufw_status(output).dict()
            return result_dict
        except Exception as e:
            return {'error': e}

    def add_rule(self, rule):
        command = f"sudo ufw {rule}"
        output = self._execute_command(command)
        print(f"✨ Command Output: {output}")

    def delete_rule(self, rule):
        command = f"sudo ufw delete {rule}"
        output = self._execute_command(command)
