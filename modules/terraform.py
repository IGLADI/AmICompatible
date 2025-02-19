import os
import re
import signal
import subprocess
import sys


# create all needed cloud resources
# we have set the retries to 1 now we know the issue and fix
def init_and_apply(terraform_dir: str, os_name: str, max_retries: int = 1):
    os.environ["TF_VAR_os"] = os_name
    subprocess.run("terraform init", shell=True, cwd=terraform_dir, check=True)

    for retry in range(1, max_retries + 1):
        try:
            execute_safely("terraform apply -auto-approve", shell=True, cwd=terraform_dir)
            return
        except subprocess.CalledProcessError as e:
            print(f"Terraform apply failed: {e}")
            # seems like the timout is ~3min
            # this should not be an issue when using a non free vm but the free tier vms (which do not comply w windows minimum requirement at all) are so slow it can easily take this long just to install ssh
            print("This is likely windows vm taking too long to install ssh which causes azure to timeout")
            print("To prevent this in the future increase the vm size when using windows")
            # this is needed as if it timouts terraform does not know what has been made as azure can still actually install ssh and this will create conflict
            print("Destroying resources and retrying")
            destroy(terraform_dir)
            if retry < max_retries:
                print(f"Retrying... Attempt {retry + 1}")
    raise Exception("Max retries reached. Terraform apply failed.")


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
    execute_safely("terraform destroy -auto-approve", shell=True, cwd=terraform_dir, ignore_all_interrupts=True)


# w help of chatgpt for signal module
def execute_safely(*args, ignore_all_interrupts=False, **kwargs):
    if ignore_all_interrupts:
        print("Executing a terraform command, ignoring all keyboard interrupts...")
    else:
        print("Executing a terraform command, only passing the first keyboard interrupt...")

    def handler(signum, frame):
        if ignore_all_interrupts:
            print("Keyboard interrupts ignored.")
        else:
            # nonlocal is needed to modify the variable in the outer scope but not in the global scope
            nonlocal first_interrupt
            if first_interrupt:
                print("First Ctrl+C received, passing to subprocess...")
                first_interrupt = False
                proc.send_signal(signal.SIGINT)
            else:
                print("Subsequent Ctrl+C ignored.")

    first_interrupt = True
    old_handler = signal.signal(signal.SIGINT, handler)

    try:
        proc = subprocess.Popen(
            *args,
            **kwargs,
            # Use stdout and stderr as the current terminal output
            stdout=sys.stdout,
            stderr=sys.stderr,
            # immediately view the output
            bufsize=1,
            universal_newlines=True,
            # separate sessions to prevent terraform itself from handling the interrupt
            start_new_session=True,
        )

        proc.wait()

        # raise an exception if the process did not exit successfully
        if proc.returncode != 0:
            if proc.returncode == 130:  # Return code 130 indicates process termination due to SIGINT
                raise KeyboardInterrupt("Command interrupted.")
            else:
                raise subprocess.CalledProcessError(
                    returncode=proc.returncode,
                    cmd=args[0] if args else kwargs.get("args"),
                )

        return proc.returncode
    finally:
        signal.signal(signal.SIGINT, old_handler)
        print("Command executed, keyboard interrupts restored.")
