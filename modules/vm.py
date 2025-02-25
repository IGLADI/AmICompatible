import os
import random
import secrets
import shutil
import string
import subprocess

from . import ansible, jenkins, metrics, ssh, terraform


def deploy_and_test(os_name, cfg, terraform_dir, interrupt=None):
    """
    Deploy a VM and run tests on it.

    Args:
        os_name: Name of the operating system.
        cfg: Configuration dictionary.
        terraform_dir: Directory containing Terraform files.
        interrupt: Shared value across processes to handle interrupts.

    Returns:
        OS name, status, and metrics.
    """
    try:
        # due to raising condition the main thread can not have the time to cancel the futures
        if interrupt.value:
            return os_name, "cancelled"

        env = os.environ.copy()

        # for multiple users executing simultaneous runs on the same subscription
        resource_group_name = f"{cfg["rg_prefix"]}-{os_name}-{''.join(random.choices(string.ascii_letters + string.digits, k=32))}"
        env["TF_VAR_resource_group_name"] = resource_group_name

        if "windows" in os_name.lower():
            password = generate_password()
            env["TF_VAR_password"] = password
            metrics = deploy_vm_and_run_tests(f"{terraform_dir}/windows", os_name, cfg, env, password, windows=True)
        else:
            metrics = deploy_vm_and_run_tests(f"{terraform_dir}/linux", os_name, cfg, env=env)

        print(f"Deployment and test for {os_name} succeeded.")
        return os_name, "succeeded", metrics
    except Exception as e:
        print(f"Deployment or test for {os_name} failed: {e}")
        return os_name, f"failed: {e}", None


def deploy_vm_and_run_tests(terraform_dir, os_name, cfg, env, password=None, windows=False):
    """
    Deploy a VM and run tests on it.

    Args:
        terraform_dir: Directory containing Terraform files.
        os_name: Name of the operating system.
        cfg: Configuration dictionary.
        env: Environment variables.
        password: Password for the VM.
        windows : Whether the VM is a Windows VM.

    Returns:
        Metrics results.
    """
    client = None
    metrics_collector = None

    try:
        print(f"Deploying {os_name} VM")
        terraform.init_and_apply(terraform_dir, os_name, env)

        print("Getting the public IP address...")
        ip = terraform.get_public_ip(terraform_dir, os_name)

        print("Connecting to the VM via SSH...")
        # for windows this only serves to wait for ssh to be available
        client = ssh.connect_to_vm(ip, password=password)

        print("Downloading remote dependencies...")
        ansible.download_remote_dependency(os_name, password, windows, ip)

        if windows:
            print("Recreating the ssh connection with powershell as shell...")
            client.close()
            client = ssh.connect_to_vm(ip, password=password)

        print("Copying project files...")
        copy_project_files(client, ip, cfg["project_root"], password, windows)

        metrics_collector = metrics.MetricsCollector(client, windows=windows)
        metrics_collector.start()

        print("Running Jenkins pipeline...")
        jenkins.run_jenkins_pipeline(client, cfg["jenkins_file"], cfg["plugin_file"], cfg["project_root"], windows)

        metrics_results = metrics_collector.get_results()
        return metrics_results
    finally:
        print("Cleaning up...")
        if metrics_collector:
            metrics_results = metrics_collector.stop()
        terraform.destroy(terraform_dir, os_name, env)
        if client:
            client.close()


def copy_project_files(client, ip, project_root, password=None, windows=False):
    """
    Copy project files to the VM.

    Args:
        client: SSH client connected to the VM.
        ip: IP address of the VM.
        project_root: Root directory of the project.
        password: Password for the VM.
        windows: Whether the VM a Windows VM.

    Raises:
        ValueError: If the combination of arguments is not supported.
    """
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
        raise ValueError("Copy Project: This combination of arguments is not supported")


def cleanup():
    """
    Clean up temporary files and directories.
    """
    if os.path.exists("temp"):
        shutil.rmtree("temp")


def generate_password():
    """
    Generate a password that meets Azure requirements.

    Returns:
        Generated password.
    """
    while True:
        password = secrets.token_urlsafe(32)
        # check if it fulfills the azure password requirements (made with help of copilot)
        if any(c.islower() for c in password) and any(c.isupper() for c in password) and any(c.isdigit() for c in password):
            return password
        else:
            print("Password does not meet Azure requirements, generating a new one...")
