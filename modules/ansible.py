import subprocess


def create_ansible_inventory(ip, os_name, password=None, powershell=False, windows=False):
    if password and windows:
        if powershell:
            inventory = f"{ip} ansible_user=aic ansible_password={password} ansible_ssh_common_args='-o StrictHostKeyChecking=no' ansible_remote_tmp='C:\\Windows\\Temp' ansible_shell_type=powershell ansible_python_interpreter=none"
        else:
            inventory = f"{ip} ansible_user=aic ansible_password={password} ansible_ssh_common_args='-o StrictHostKeyChecking=no' ansible_remote_tmp='C:\\Windows\\Temp' ansible_shell_type=cmd ansible_python_interpreter=none"
    elif not windows:
        inventory = f"{ip} ansible_user=aic ansible_ssh_private_key_file=./temp/id_rsa ansible_ssh_common_args='-o StrictHostKeyChecking=no'"
    else:
        raise ValueError("Create Inventory: This combination of arguments is not supported")
    with open(f"./temp/{os_name}.ini", "w") as ini:
        ini.write(inventory)


def download_remote_dependency(os_name, password=None, windows=False, ip=None):
    print("Creating Ansible inventory...")
    create_ansible_inventory(ip, os_name, password, windows=windows)

    if password and windows:
        # set pwsh as default shell
        subprocess.run(
            f"ansible-playbook -i ./temp/{os_name}.ini ansible/windows/shell.yml",
            shell=True,
            check=True,
        )
        # install dependencies
        create_ansible_inventory(ip, os_name, password, True, windows)
        subprocess.run(
            f"ansible-playbook -i ./temp/{os_name}.ini ansible/windows/dependency.yml",
            shell=True,
            check=True,
        )
    elif not windows:
        # rsa path is in the ini file
        subprocess.run(f"ansible-playbook -i ./temp/{os_name}.ini ansible/linux/dependency.yml", shell=True, check=True)
    else:
        raise ValueError("Download Dependency: This combination of arguments is not supported")
