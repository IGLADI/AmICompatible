import re
import subprocess
from logging import Logger

from modules import cli

from .custom_logging import log


@log
def init_and_apply(
    terraform_dir: str, os_name: str, logger: Logger, env: dict, max_retries: int = 1
) -> None:
    """
    Initialize and apply Terraform configuration.

    Args:
        terraform_dir: Directory containing Terraform files.
        os_name: Name of the operating system.
        logger: Logger instance for logging.
        env: Environment variables.
        max_retries: Maximum number of retries.

    Raises:
        Exception: If maximum retries are reached and Terraform apply fails.
    """
    env["TF_VAR_os"] = os_name
    logger.debug(f"Environment variable TF_VAR_os set to {os_name}")
    if "arm" in os_name.lower():
        env["TF_VAR_arm"] = "true"
        logger.debug("Environment variable TF_VAR_arm set to true")
    else:
        env["TF_VAR_arm"] = "false"
        logger.debug("Environment variable TF_VAR_arm set to false")
    cli.run(
        "terraform init",
        logger=logger,
        shell=True,
        cwd=terraform_dir,
        check=True,
        env=env,
    )

    for retry in range(1, max_retries + 1):
        try:
            # use a separate state file for each thread
            cli.run(
                f"terraform apply -state-out={os_name}.tfstate -auto-approve -lock=false",
                shell=True,
                cwd=terraform_dir,
                env=env,
                logger=logger,
                ignore_interrupts=True,
            )
            return
        except subprocess.CalledProcessError as e:
            logger.error(f"Terraform apply failed: {e}")
            # seems like the timout is ~3min
            # this should not be an issue when using a non free vm but the free tier vms (which do not comply w windows minimum requirement at all) are so slow it can easily take this long just to install ssh
            logger.error(
                "This is likely windows vm taking too long to install ssh which causes azure to timeout"
            )
            logger.error(
                "To prevent this in the future increase the vm size when using windows"
            )
            # this is needed as if it timouts terraform does not know what has been made as azure can still actually install ssh and this will create conflict
            logger.info("Destroying resources")
            if retry < max_retries:
                logger.info(f"Retrying... Attempt {retry + 1}")
    raise Exception("Max retries reached. Terraform apply failed.")


@log
def get_public_ip(terraform_dir: str, os_name: str, logger: Logger) -> str:
    """
    Get the public IP address of the deployed VM.

    Args:
        terraform_dir: Directory containing Terraform files.
        os_name: Name of the operating system.
        logger: Logger instance for logging.

    Returns:
        Public IP address.

    Raises:
        ValueError: If the IP address cannot be found in Terraform output.
    """
    stdout, stderr = cli.run(
        f"terraform output -state={os_name}.tfstate public_ip",
        logger=logger,
        shell=True,
        cwd=terraform_dir,
        check=True,
        text=True,
    )
    # regex to find an ipv4 w help of ChatGPT
    ip_pattern = r"\b(?:\d{1,3}\.){3}\d{1,3}\b"
    match = re.search(ip_pattern, stdout)
    if not match:
        raise ValueError("Could not find IP address in Terraform output")
    return match.group(0)


@log
def destroy(terraform_dir: str, os_name: str, env: dict, logger: Logger) -> None:
    """
    Destroy Terraform resources to limit costs.

    Args:
        terraform_dir: Directory containing Terraform files.
        os_name: Name of the operating system.
        env: Environment variables.
        logger: Logger instance for logging.
    """
    # this will send a deprecated warning as it's a legacy feature, however no new replacement seem to be valid for this edge case
    # see https://github.com/hashicorp/terraform/issues/36600
    # see https://developer.hashicorp.com/terraform/language/backend/local
    cli.run(
        f"terraform destroy -state={os_name}.tfstate -lock=false -auto-approve -compact-warnings",
        shell=True,
        cwd=terraform_dir,
        env=env,
        ignore_all_interrupts=True,
        logger=logger,
    )
    logger.info("Terraform resources destroyed.")
