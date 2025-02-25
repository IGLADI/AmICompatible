import re
import signal
import subprocess
import sys


def init_and_apply(terraform_dir: str, os_name: str, env: dict, max_retries: int = 1) -> None:
    """
    Initialize and apply Terraform configuration.

    Args:
        terraform_dir: Directory containing Terraform files.
        os_name: Name of the operating system.
        env: Environment variables.
        max_retries: Maximum number of retries.

    Raises:
        Exception: If maximum retries are reached and Terraform apply fails.
    """
    env["TF_VAR_os"] = os_name
    if "arm" in os_name.lower():
        env["TF_VAR_arm"] = "true"
    else:
        env["TF_VAR_arm"] = "false"
    subprocess.run("terraform init", shell=True, cwd=terraform_dir, check=True, env=env)

    for retry in range(1, max_retries + 1):
        try:
            # use a separate state file for each thread
            execute_safely(f"terraform apply -state-out={os_name}.tfstate -auto-approve -lock=false", shell=True, cwd=terraform_dir, env=env)
            return
        except subprocess.CalledProcessError as e:
            print(f"Terraform apply failed: {e}")
            # seems like the timout is ~3min
            # this should not be an issue when using a non free vm but the free tier vms (which do not comply w windows minimum requirement at all) are so slow it can easily take this long just to install ssh
            print("This is likely windows vm taking too long to install ssh which causes azure to timeout")
            print("To prevent this in the future increase the vm size when using windows")
            # this is needed as if it timouts terraform does not know what has been made as azure can still actually install ssh and this will create conflict
            print("Destroying resources and retrying")
            destroy(terraform_dir, os_name, env)
            if retry < max_retries:
                print(f"Retrying... Attempt {retry + 1}")
    raise Exception("Max retries reached. Terraform apply failed.")


def get_public_ip(terraform_dir: str, os_name: str) -> str:
    """
    Get the public IP address of the deployed VM.

    Args:
        terraform_dir: Directory containing Terraform files.
        os_name: Name of the operating system.

    Returns:
        Public IP address.

    Raises:
        ValueError: If the IP address cannot be found in Terraform output.
    """
    result = subprocess.run(
        f"terraform output -state={os_name}.tfstate public_ip", shell=True, cwd=terraform_dir, check=True, capture_output=True, text=True
    )
    # regex to find an ipv4 w help of ChatGPT
    ip_pattern = r"\b(?:\d{1,3}\.){3}\d{1,3}\b"
    match = re.search(ip_pattern, result.stdout)
    if not match:
        raise ValueError("Could not find IP address in Terraform output")
    return match.group(0)


# destroy any resource made by terraform to limit costs while not in use
def destroy(terraform_dir: str, os_name: str, env: dict) -> None:
    """
    Destroy Terraform resources to limit costs.

    Args:
        terraform_dir: Directory containing Terraform files.
        os_name: Name of the operating system.
        env: Environment variables.
    """
    # this will send a deprecated warning as it's a legacy feature, however no new replacement seem to be valid for this edge case
    # see https://developer.hashicorp.com/terraform/language/backend/local
    execute_safely(
        f"terraform destroy -state={os_name}.tfstate -lock=false -auto-approve",
        shell=True,
        cwd=terraform_dir,
        env=env,
        ignore_all_interrupts=True,
    )


# w help of chatgpt for signal module
def execute_safely(*args, ignore_all_interrupts=False, env=None, **kwargs) -> int:
    """
    Execute a terraform command safely, handling keyboard interrupts.

    Args:
        ignore_all_interrupts: Whether to ignore all keyboard interrupts or only pass the first one.
        env: Environment variables.

    Raises:
        KeyboardInterrupt: If the command is interrupted.
        subprocess.CalledProcessError: If the command fails.
    """
    if ignore_all_interrupts:
        print("Executing critical terraform command, ignoring all keyboard interrupts...")
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
            env=env,
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
