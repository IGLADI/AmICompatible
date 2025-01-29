import subprocess
import re
import os


# create all needed cloud resources
def init_and_apply(terraform_dir: str, os_name: str):
    os.environ["TF_VAR_os"] = os_name
    subprocess.run("terraform init", shell=True, cwd=terraform_dir, check=True)
    subprocess.run("terraform apply -auto-approve", shell=True, cwd=terraform_dir, check=True)


def get_public_ip(terraform_dir: str):
    result = subprocess.run("terraform output public_ip", shell=True, cwd=terraform_dir, check=True, capture_output=True, text=True)
    # regex to find an ipv4 w help of ChatGPT
    ip_pattern = r"\b(?:\d{1,3}\.){3}\d{1,3}\b"
    match = re.search(ip_pattern, result.stdout)
    if not match:
        raise ValueError("Could not find IP address in Terraform output")
    return match.group(0)


# destroy any resource made by terraform to limit costs while not in use
def destroy(terraform_dir: str):
    subprocess.run("terraform destroy -auto-approve", shell=True, cwd=terraform_dir, check=True)
