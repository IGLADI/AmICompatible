import multiprocessing
import os
import random
import secrets
import shutil
import signal
import string
from logging import Logger

import paramiko

from modules import cli

from . import ansible, custom_logging, jenkins, metrics, ssh, terraform
from .custom_logging import log


def handler(logger: Logger):
    raise KeyboardInterrupt("Interrupt signal received. Exiting...")


@log
def deploy_and_test(os_name: str, cfg: dict, terraform_dir: str, log_dir: str, logger: Logger, interrupt: multiprocessing.Value) -> tuple:  # type: ignore
    """
    Deploy a VM and run tests on it.

    Args:
        os_name: Name of the operating system.
        cfg: Configuration dictionary.
        terraform_dir: Directory containing Terraform files.
        log_dir: Directory for log files.
        logger: Logger instance for logging.
        interrupt: Shared value across processes to handle interrupts.

    Returns:
        OS name, status, and metrics.
    """
    try:
        # reset the interrupt signal
        signal.signal(signal.SIGINT, lambda signum, frame: handler(logger=logger))
        # due to racing condition the main thread can not have the time to cancel all the futures
        if interrupt.value:
            return os_name, "cancelled", None

        os.mkdir(log_dir)
        logger = custom_logging.setup_logger(
            f"{log_dir}/main.log", cfg["log_level"], "main"
        )

        env = os.environ.copy()
        logger.debug("Environment variables copied.")

        # for multiple users executing simultaneous runs on the same subscription
        resource_group_name = f"{cfg['rg_prefix']}-{os_name}-{''.join(random.choices(string.ascii_letters + string.digits, k=32))}"
        env["TF_VAR_resource_group_name"] = resource_group_name
        logger.debug(f"Resource group name set to {resource_group_name}")

        if "windows" in os_name.lower():
            password = generate_azure_password(logger=logger)
            env["TF_VAR_password"] = password
            logger.debug("Password generated for Windows VM.")
            metrics = deploy_vm_and_run_tests(
                f"{terraform_dir}/windows",
                os_name,
                cfg,
                env,
                log_dir,
                logger=logger,
                password=password,
                windows=True,
            )
        else:
            metrics = deploy_vm_and_run_tests(
                f"{terraform_dir}/linux",
                os_name,
                cfg,
                env=env,
                log_dir=log_dir,
                logger=logger,
            )
            logger.debug("Linux VM deployment initiated.")

        logger.info(f"Deployment and test for {os_name} succeeded.")
        return os_name, "succeeded", metrics
    except Exception as e:
        logger.error(f"Deployment or test for {os_name} failed: {e}")
        return os_name, f"failed: {e}", None


@log
def deploy_vm_and_run_tests(
    terraform_dir: str,
    os_name: str,
    cfg: dict,
    env: dict,
    log_dir: str,
    logger: Logger,
    password: str | None = None,
    windows: bool = False,
) -> tuple[list, list]:
    """
    Deploy a VM and run tests on it.

    Args:
        terraform_dir: Directory containing Terraform files.
        os_name: Name of the operating system.
        cfg: Configuration dictionary.
        env: Environment variables.
        log_dir: Directory for log files.
        logger: Logger instance for logging.
        password: Password for the VM.
        windows: Whether the VM is a Windows VM.

    Returns:
        Metrics results.
    """
    client = None
    metrics_collector = None

    terraform_logger = custom_logging.setup_logger(
        f"{log_dir}/terraform.log", cfg["log_level"], "terraform", f"{log_dir}/main.log"
    )
    ansible_logger = custom_logging.setup_logger(
        f"{log_dir}/ansible.log", cfg["log_level"], "ansible", f"{log_dir}/main.log"
    )
    jenkins_logger = custom_logging.setup_logger(
        f"{log_dir}/jenkins.log", cfg["log_level"], "jenkins", f"{log_dir}/main.log"
    )
    metrics_logger = custom_logging.setup_logger(
        f"{log_dir}/metrics.log", cfg["log_level"], "metrics", f"{log_dir}/main.log"
    )

    try:
        logger.info(f"Deploying {os_name} VM")
        terraform.init_and_apply(
            terraform_dir,
            os_name,
            env=env,
            logger=terraform_logger,
        )
        logger.debug("Terraform apply completed.")

        logger.info("Getting the public IP address...")
        ip = terraform.get_public_ip(terraform_dir, os_name, logger=terraform_logger)
        logger.debug(f"Public IP address obtained: {ip}")

        logger.info("Connecting to the VM via SSH...")
        # for windows this only serves to wait for ssh to be available
        client = ssh.connect_to_vm(ip, logger=logger, password=password)
        logger.debug("SSH connection established.")
        ansible.download_remote_dependency(
            os_name, logger=ansible_logger, password=password, windows=windows, ip=ip
        )
        logger.debug("Remote dependencies downloaded.")

        if windows:
            logger.info("Recreating the ssh connection with powershell as shell...")
            client.close()
            client = ssh.connect_to_vm(ip, logger=logger, password=password)
            logger.debug("SSH connection re-established with PowerShell.")

        logger.info("Copying project files...")
        copy_project_files(
            client,
            ip,
            cfg["project_root"],
            logger=logger,
            password=password,
            windows=windows,
        )
        logger.debug("Project files copied.")

        metrics_collector = metrics.MetricsCollector(
            client, logger=metrics_logger, windows=windows
        )
        metrics_collector.start(logger=logger)
        logger.debug("Metrics collection started.")

        logger.info("Running Jenkins pipeline...")
        jenkins.run_jenkins_pipeline(
            client,
            cfg["jenkins_file"],
            cfg["plugin_file"],
            cfg["project_root"],
            logger=jenkins_logger,
            windows=windows,
        )
        logger.debug("Jenkins pipeline executed.")

        metrics_results = metrics_collector.get_results(logger=metrics_logger)
        logger.debug("Metrics results obtained.")
        return metrics_results
    finally:
        logger.error("Cleaning up...")
        if metrics_collector:
            metrics_results = metrics_collector.stop(logger=metrics_logger)
            logger.debug("Metrics collection stopped.")
        terraform.destroy(terraform_dir, os_name, env, logger=terraform_logger)
        logger.debug("Terraform resources destroyed.")
        if client:
            client.close()
            logger.debug("SSH connection closed.")


@log
def copy_project_files(
    client: paramiko.SSHClient,
    ip: str,
    project_root: str,
    logger: Logger,
    password: str | None = None,
    windows: bool = False,
) -> None:
    """
    Copy project files to the VM.

    Args:
        client: SSH client connected to the VM.
        ip: IP address of the VM.
        project_root: Root directory of the project.
        logger: Logger instance for logging.
        password: Password for the VM.
        windows: Whether the VM a Windows VM.

    Raises:
        ValueError: If the combination of arguments is not supported.
    """
    if password and windows:
        # scp does not support password auth OOTB so we use sshpass to automate the password input
        # for windows path check out https://stackoverflow.com/questions/10235778/scp-from-linux-to-windows
        cli.run(
            f"sshpass -p {password} scp -o StrictHostKeyChecking=no -r {project_root}/* aic@{ip}:C:/Windows/system32/config/systemprofile/AppData/Local/Jenkins/.jenkins/workspace/aic_job",
            logger=logger,
            shell=True,
            check=True,
        )
        cli.run(
            f"sshpass -p {password} scp -o StrictHostKeyChecking=no ./modules/approve-scripts.groovy aic@{ip}:/C:/Users/aic ",
            logger=logger,
            shell=True,
            check=True,
        )
        logger.debug("Project files copied to VM.")
    elif not windows:
        # copy the project files to the VM
        cli.run(
            f"scp -o StrictHostKeyChecking=no -i ./temp/id_rsa -r {project_root} aic@{ip}:~/project",
            logger=logger,
            shell=True,
            check=True,
        )
        ssh.execute_ssh_command(
            client,
            "sudo cp -r ~/project/* /var/lib/jenkins/workspace/aic_job",
            logger=logger,
        )
        # regive jenkins ownership of the workspace
        ssh.execute_ssh_command(
            client, "sudo chown -R jenkins:jenkins /var/lib/jenkins", logger=logger
        )
        cli.run(
            f"scp -o StrictHostKeyChecking=no -i ./temp/id_rsa ./modules/approve-scripts.groovy aic@{ip}:~",
            logger=logger,
            shell=True,
            check=True,
        )
        logger.debug("Project files copied to VM.")
    else:
        raise ValueError("Copy Project: This combination of arguments is not supported")


@log
def cleanup(logger: Logger) -> None:
    """
    Clean up temporary files and directories.
    """
    if os.path.exists("temp"):
        shutil.rmtree("temp")


@log
def generate_azure_password(logger: Logger) -> str:
    """
    Generate a password that meets Azure requirements.

    Args:
        logger: Logger instance for logging.

    Returns:
        Generated password.
    """
    while True:
        password = secrets.token_urlsafe(32)
        # check if it fulfills the azure password requirements (made with help of copilot)
        if (
            any(c.islower() for c in password)
            and any(c.isupper() for c in password)
            and any(c.isdigit() for c in password)
        ):
            return password
        else:
            logger.warning(
                "Password does not meet Azure requirements, generating a new one..."
            )
