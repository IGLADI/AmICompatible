import subprocess
import re
import os


# create all needed cloud resources
def init_and_apply(terraform_dir: str, os_name: str, max_retries: int = 5):
    os.environ["TF_VAR_os"] = os_name
    subprocess.run("terraform init", shell=True, cwd=terraform_dir, check=True)

    for retry in range(max_retries):
        try:
            subprocess.run("terraform apply -auto-approve", shell=True, cwd=terraform_dir, check=True)
            break
        except subprocess.CalledProcessError as e:
            print(f"Terraform apply failed: {e}")
            # seems like the timout is ~3min
            # this should not be an issue when using a non free vm but the free tier vms (which do not comply w windows minimum requirement at all) are so slow it can easily take this long just to install ssh
            print("This is likely windows vm taking too long to install ssh which causes azure to timeout")
            print("To prevent this in the future increase the vm size when using windows")
            # this is needed as if it timouts terraform does not know what has been made as azure can still actually install ssh and this will create conflict
            print("Destroying resources and retrying")
            destroy(terraform_dir)
            if retry == max_retries - 1:
                raise Exception("Max retries reached. Terraform apply failed.")
            else:
                print(f"Retrying... Attempt {retry + 1}")
                continue


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
