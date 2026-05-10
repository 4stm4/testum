import paramiko


class Installer:

    def __init__(self, hostname, port, username, password):
        self.host = hostname
        self.port = port
        self.username = username
        self.password = password

    def qemu_libvirt(self):
        try:
            # Установление SSH соединения
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(self.host, self.port,
                        username=self.username, password=self.password)

            # Список команд для установки qemu и libvirt
            commands = [
                "sudo apt update",
                "sudo apt upgrade -y",
                "sudo apt install -y qemu-kvm libvirt-daemon-system libvirt-clients bridge-utils",
                "sudo adduser `id -un` libvirt",
                "sudo adduser `id -un` libvirt-qemu"
            ]

            # Выполнение команд
            for command in commands:
                stdin, stdout, stderr = ssh.exec_command(command)
                stdout.channel.recv_exit_status()  # Ожиданание завершения команды
                print(stdout.read().decode('utf-8'))
                print(stderr.read().decode('utf-8'))

                return 'Установка завершена успешно! 🎉'
        except Exception as e:
            return f"Произошла ошибка: {str(e)} 😞"
        finally:
            ssh.close()

    def firewall(self):
        command = 'sudo apt install ufw'
        try:
            output = self._execute_command(command)
            return output
        except Exception as e:
            return e
