import os
import subprocess
import paramiko
import time


# Create single use ssh key
def create_ssh_key():
    # remove any previous key if it exists
    if os.path.exists("temp/id_rsa"):
        delete_ssh_key()
    os.makedirs("temp", exist_ok=True)
    subprocess.run("ssh-keygen -t rsa -b 4096 -f ./temp/id_rsa -N '' -q", shell=True, check=True)


def delete_ssh_key():
    os.remove("temp/id_rsa")
    os.remove("temp/id_rsa.pub")
    os.rmdir("temp")


# try connecting to the VM (needed in case the vm takes time to boot)
def connect_to_vm(ip: str, max_retries: int = 10, delay: int = 30):
    for attempt in range(max_retries):
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(hostname=ip, username="aic", key_filename="./temp/id_rsa", timeout=30)
            return ssh
        except Exception as e:
            if attempt == max_retries - 1:
                raise Exception(f"Failed to connect after {max_retries} attempts: {str(e)}")
            print(f"Connection attempt {attempt + 1} failed, waiting {delay} seconds...")
            time.sleep(delay)
    return None
