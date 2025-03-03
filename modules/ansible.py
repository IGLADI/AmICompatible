from logging import Logger

from modules import cli

from .custom_logging import log


@log
def create_ansible_inventory(
    ip: str, os_name: str, logger: Logger, password: str | None = None, powershell: bool = False, windows: bool = False
) -> None:
    """
    Create an Ansible inventory file.

    Args:
        ip: IP address of the target machine.
        os_name: Operating system name.
        logger: Logger instance for logging.
        password: Password for the target machine (if applicable).
        powershell: Whether to use PowerShell for Windows.
        windows: Whether the target machine is Windows.
    """
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


@log
def download_remote_dependency(os_name: str, logger: Logger, password: str | None = None, windows: bool = False, ip: str | None = None) -> None:
    """
    Download remote dependencies using Ansible.

    Args:
        os_name: Operating system name.
        logger: Logger instance for logging.
        password: Password for the target machine (if applicable).
        windows: Whether the target machine is Windows.
        ip: IP address of the target machine.
    """
    logger.info("Creating Ansible inventory...")
    create_ansible_inventory(ip, os_name, logger=logger, password=password, windows=windows)
    if password and windows:
        logger.info("Setting PowerShell as the default remote shell...")
        cli.run(
            f"ansible-playbook -i ./temp/{os_name}.ini ansible/windows/shell.yml",
            logger=logger,
            shell=True,
            check=True,
        )
        create_ansible_inventory(ip, os_name, logger=logger, password=password, powershell=True, windows=windows)
        logger.info("Downloading remote dependencies...")
        cli.run(
            f"ansible-playbook -i ./temp/{os_name}.ini ansible/windows/dependency.yml",
            logger=logger,
            shell=True,
            check=True,
        )
    elif not windows:
        # rsa path is in the ini file
        logger.info("Downloading remote dependencies...")
        cli.run(f"ansible-playbook -i ./temp/{os_name}.ini ansible/linux/dependency.yml", logger=logger, shell=True, check=True)
    else:
        raise ValueError("Download Dependency: This combination of arguments is not supported")
