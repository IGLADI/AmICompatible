import os

import yaml


def load_config(path: str = "aic.yml") -> dict:
    """
    Load configuration from a YAML file.

    Returns:
        dict: Configuration dictionary.
    """
    with open(path) as config:
        return yaml.safe_load(config)


def setup_terraform_vars(config: dict) -> None:
    """
    Set up Terraform environment variables.

    Args:
        config: Configuration dictionary.
    """
    env_vars = {
        "TF_VAR_subscription_id": config["subscription_id"],
        "TF_VAR_tenant_id": config["tenant_id"],
        "TF_VAR_appId": config["appId"],
        "TF_VAR_client_secret": config["client_secret"],
        "TF_VAR_region": config["region"],
        "TF_VAR_vm_size": config["vm_size"],
        "TF_VAR_arm_vm_size": config["arm_vm_size"],
        "TF_VAR_ssh_public_key_path": "../../../temp/id_rsa.pub",
    }
    os.environ.update(env_vars)
