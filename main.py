import subprocess
import configparser
import os
import sys
import ast
import re
import paramiko


def init_terraform():
    # get the conf file
    config = configparser.ConfigParser()
    config.read("aic.conf")
    platform_config = config["platform"]
    platform = platform_config.get("platform", None)
    osvm = platform_config.get("os", None)
    osvm = ast.literal_eval(osvm)
    # give the values to terraform as env vars
    os.environ["TF_VAR_subscription_id"] = platform_config["subscription_id"]
    os.environ["TF_VAR_tenant_id"] = platform_config["tenant_id"]
    os.environ["TF_VAR_appId"] = platform_config["appId"]
    os.environ["TF_VAR_client_secret"] = platform_config["client_secret"]
    os.environ["TF_VAR_region"] = platform_config["region"]
    os.environ["TF_VAR_vm_size"] = platform_config["vm_size"]
    os.environ["TF_VAR_ssh_public_key_path"] = "../../temp/id_rsa.pub"

    return platform, osvm


def create_ssh_key():
    os.makedirs("temp", exist_ok=True)
    if os.path.exists("temp/id_rsa"):
        os.remove("temp/id_rsa")
    subprocess.run("ssh-keygen -t rsa -b 4096 -f ./temp/id_rsa -N '' -q", shell=True, check=True)


def delete_ssh_key():
    os.remove("temp/id_rsa")
    os.remove("temp/id_rsa.pub")
    os.rmdir("temp")


def create_vms():
    platform, osvm = init_terraform()

    if platform == "azure":
        terraform_dir = "./terraform/azure"
        for vm in osvm:
            os.environ["TF_VAR_os"] = vm
            deploy_vm(terraform_dir)
            remove_vm(terraform_dir)
    else:
        print(f"Error: Unsupported platform '{platform}' specified.")
        sys.exit(1)


def deploy_vm(terraform_dir):
    print("Initializing Terraform for Azure...")
    subprocess.run("terraform init", shell=True, cwd=terraform_dir, check=True)

    print("Applying Terraform configuration...")
    subprocess.run("terraform apply -auto-approve", shell=True, cwd=terraform_dir, check=True)

    print("Getting the public IP address...")
    ip = (
        subprocess.run(
            "terraform output public_ip",
            shell=True,
            cwd=terraform_dir,
            check=True,
            capture_output=True,
        )
        .stdout.decode()
        .strip()
    )
    # regex to find the ip address, w help of ChatGPT
    ip_pattern = r"\b(?:\d{1,3}\.){3}\d{1,3}\b"
    ip = re.search(ip_pattern, ip).group(0)

    print("SSHing into the VM...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(hostname=ip, username="aic", key_filename="./temp/id_rsa")

    # testing a random command to showcase the ssh connection is working
    stdin, stdout, stderr = ssh.exec_command("hostname")
    print(stdout.read().decode())


def remove_vm(terraform_dir):
    print("Post script cleanup...")
    subprocess.run("terraform destroy -auto-approve", shell=True, cwd=terraform_dir, check=True)


if __name__ == "__main__":
    create_ssh_key()
    create_vms()
    delete_ssh_key()
