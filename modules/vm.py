import os
import secrets
import shutil
import subprocess

from . import ssh, terraform, jenkins


def deploy_and_test_vm(terraform_dir, os_name, cfg, password=None, windows=False):
    print(f"Deploying {os_name} VM")
    terraform.init_and_apply(terraform_dir, os_name)

    try:
        print("Getting the public IP address...")
        ip = terraform.get_public_ip(terraform_dir)

        print("Connecting to the VM via SSH...")
        # for windows this only serves to wait for ssh to be available
        client = ssh.connect_to_vm(ip, password=password)

        print("Creating Ansible inventory...")
        create_ansible_inventory(ip, password, windows=windows)

        print("Downloading remote dependencies...")
        download_remote_dependency(password, windows, ip)

        if windows:
            print("Recreating the ssh connection with powershell as shell...")
            client.close()
            client = ssh.connect_to_vm(ip, password=password)

        print("Copying project files...")
        copy_project_files(client, ip, cfg["project_root"], password, windows)

        print("Running Jenkins pipeline...")
        jenkins.run_jenkins_pipeline(client, cfg["jenkins_file"], cfg["plugin_file"], cfg["project_root"], password, windows)
    finally:
        print("Cleaning up...")
        terraform.destroy(terraform_dir)
        if client:
            client.close()


def create_ansible_inventory(ip, password=None, powershell=False, windows=False):
    if password and windows:
        if powershell:
            inventory = f"{ip} ansible_user=aic ansible_password={password} ansible_ssh_common_args='-o StrictHostKeyChecking=no' ansible_remote_tmp='C:\\Windows\\Temp' ansible_shell_type=powershell ansible_python_interpreter=none"
        else:
            inventory = f"{ip} ansible_user=aic ansible_password={password} ansible_ssh_common_args='-o StrictHostKeyChecking=no' ansible_remote_tmp='C:\\Windows\\Temp' ansible_shell_type=cmd ansible_python_interpreter=none"
    elif not windows:
        inventory = f"{ip} ansible_user=aic ansible_ssh_private_key_file=./temp/id_rsa ansible_ssh_common_args='-o StrictHostKeyChecking=no'"
    else:
        raise ValueError("This combination of arguments is not supported")
    with open("./temp/inventory.ini", "w") as ini:
        ini.write(inventory)


def download_remote_dependency(password=None, windows=False, ip=None):
    if password and windows:
        # set pwsh as default shell
        subprocess.run(
            "ansible-playbook -i ./temp/inventory.ini ansible/windows/shell.yml",
            shell=True,
            check=True,
        )
        # install dependencies
        create_ansible_inventory(ip, password, powershell=True, windows=windows)
        subprocess.run(
            "ansible-playbook -i ./temp/inventory.ini ansible/windows/dependency.yml",
            shell=True,
            check=True,
        )
    elif not windows:
        # rsa path is in the ini file
        subprocess.run("ansible-playbook -i ./temp/inventory.ini ansible/linux/dependency.yml", shell=True, check=True)
    else:
        raise ValueError("This combination of arguments is not supported")


def copy_project_files(client, ip, project_root, password=None, windows=False):
    if password and windows:
        # scp does not support password auth OOTB so we use sshpass to automate the password input
        # for windows path check out https://stackoverflow.com/questions/10235778/scp-from-linux-to-windows
        subprocess.run(
            f"sshpass -p {password} scp -r {project_root}/* aic@{ip}:C:/Windows/system32/config/systemprofile/AppData/Local/Jenkins/.jenkins/workspace/aic_job",
            shell=True,
            check=True,
        )
        subprocess.run(f"sshpass -p {password} scp ./modules/approve-scripts.groovy aic@{ip}:/C:/Users/aic", shell=True, check=True)
    elif not windows:
        # copy the project files to the VM
        subprocess.run(f"scp -i ./temp/id_rsa -r {project_root} aic@{ip}:~/project", shell=True, check=True)
        ssh.execute_ssh_command(client, "sudo cp -r ~/project/* /var/lib/jenkins/workspace/aic_job")
        # regive jenkins ownership of the workspace
        ssh.execute_ssh_command(client, "sudo chown -R jenkins:jenkins /var/lib/jenkins")
        subprocess.run(f"scp -i ./temp/id_rsa ./modules/approve-scripts.groovy aic@{ip}:~", shell=True, check=True)
    else:
        raise ValueError("This combination of arguments is not supported")


def cleanup():
    if os.path.exists("temp"):
        shutil.rmtree("temp")


def generate_password():
    while True:
        password = secrets.token_urlsafe(32)
        # check if it fulfills the azure password requirements (made with help of copilot)
        if any(c.islower() for c in password) and any(c.isupper() for c in password) and any(c.isdigit() for c in password):
            return password
        else:
            print("Password does not meet Azure requirements, generating a new one...")
