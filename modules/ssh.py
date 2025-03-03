import os
import time
from logging import Logger

import paramiko

from modules import cli

from .custom_logging import log


@log
def create_ssh_key(logger: Logger) -> None:
    """
    Create a temporary SSH key.

    Args:
        logger: Logger instance for logging.
    """
    # remove any previous key
    if os.path.exists("temp/id_rsa"):
        os.remove("temp/id_rsa")
        os.remove("temp/id_rsa.pub")
        logger.debug("Existing SSH keys removed.")
    cli.run("ssh-keygen -t rsa -b 4096 -f ./temp/id_rsa -N '' -q", logger=logger, shell=True, check=True)
    logger.debug("New SSH key generated.")


@log
def connect_to_vm(
    ip: str, logger: Logger, max_retries: int = 10, delay: int = 10, password: str | None = None, key_path: str = "./temp/id_rsa"
) -> paramiko.SSHClient | None:
    """
    Connect to a VM via SSH.

    Args:
        ip: IP address of the VM.
        logger: Logger instance for logging.
        max_retries: Maximum number of connection attempts.
        delay: Delay between connection attempts in seconds.
        password: Password for the VM.
        key_path: Path to the SSH key.

    Returns:
        SSH client connected to the VM.

    Raises:
        Exception: If the connection fails after the maximum number of attempts.
    """
    # try connecting to the VM (needed in case the vm takes time to boot)
    for attempt in range(1, max_retries + 1):
        try:
            ssh = paramiko.SSHClient()
            # automatically add the hostname to the list of known hosts
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            if password:
                ssh.connect(hostname=ip, username="aic", password=password, timeout=10)
            else:
                ssh.connect(hostname=ip, username="aic", key_filename=key_path, timeout=10)
            logger.debug(f"SSH connection established to {ip} on attempt {attempt}.")
            return ssh
        except Exception as e:
            if attempt >= max_retries:
                raise Exception(f"Failed to connect after {max_retries} attempts: {str(e)}")
            else:
                logger.warning(f"Connection attempt {attempt} failed, waiting {delay} seconds...")
                time.sleep(delay)


@log
def execute_ssh_command(client: paramiko.SSHClient, command: str, logger: Logger, print_output: bool = True) -> tuple:
    """
    Execute an SSH command on the VM.

    Args:
        client: SSH client connected to the VM.
        command: Command to execute.
        logger: Logger instance for logging.
        print_output: Whether to print the command output.

    Returns:
        Stdout and stderr of the command.

    Raises:
        Exception: If the command fails.
    """
    stdin, stdout, stderr = client.exec_command(command)
    stdout_str = stdout.read().decode().strip()
    stderr_str = stderr.read().decode().strip()
    exit_status = stdout.channel.recv_exit_status()

    if print_output:
        if stdout_str:
            logger.info(f"STDOUT: {stdout_str}")
        if stderr_str:
            logger.error(f"STDERR: {stderr_str}")
    else:
        if stdout_str:
            logger.debug(f"STDOUT: {stdout_str}")
        if stderr_str:
            logger.debug(f"STDERR: {stderr_str}")

    if exit_status != 0:
        raise Exception(f"Command '{command}' failed with exit status {exit_status}: {stderr_str}")

    logger.debug(f"Command '{command}' executed successfully.")
    return stdout_str, stderr_str
