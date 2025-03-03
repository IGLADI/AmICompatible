import os
from logging import Logger

import yaml

from .custom_logging import log


def load_config(path: str = "aic.yml") -> dict:
    """
    Load and validate the configuration from a YAML file.

    Args:
        path: Path to the configuration YAML file.

    Returns:
        A dictionary containing the configuration.

    Raises:
        ValueError: If any required configuration key is missing or invalid.
    """
    with open(path) as config:
        config_dict = yaml.safe_load(config)

    required_keys = [
        "platform",
        "subscription_id",
        "tenant_id",
        "appId",
        "client_secret",
        "region",
        "vm_size",
        "arm_vm_size",
        "max_threads",
        "os",
        "rg_prefix",
        "project_root",
        "jenkins_file",
        "plugin_file",
        "log_dir",
        "log_level",
    ]

    for key in required_keys:
        if key not in config_dict:
            raise ValueError(f"Missing required configuration key: {key}")

    if not isinstance(config_dict["max_threads"], int) and config_dict["max_threads"] is not None:
        raise ValueError("max_threads must be an integer or None.")

    if not isinstance(config_dict["os"], list) or not all(isinstance(item, str) for item in config_dict["os"]):
        raise ValueError("os must be a list of strings.")

    if not isinstance(config_dict["subscription_id"], str):
        raise ValueError("subscription_id must be a string.")
    if not isinstance(config_dict["appId"], str):
        raise ValueError("appId must be a string.")
    if not isinstance(config_dict["client_secret"], str):
        raise ValueError("client_secret must be a string.")
    if not isinstance(config_dict["tenant_id"], str):
        raise ValueError("tenant_id must be a string.")
    if not isinstance(config_dict["region"], str):
        raise ValueError("region must be a string.")
    if not isinstance(config_dict["vm_size"], str):
        raise ValueError("vm_size must be a string.")
    if not isinstance(config_dict["arm_vm_size"], str):
        raise ValueError("arm_vm_size must be a string.")
    if not isinstance(config_dict["rg_prefix"], str):
        raise ValueError("rg_prefix must be a string.")
    if not isinstance(config_dict["log_dir"], str):
        raise ValueError("log_dir must be a string.")

    supported_platforms = ["azure"]
    if config_dict["platform"] not in supported_platforms:
        raise ValueError(f"Unsupported platform: {config_dict['platform']}. Supported platforms are: {', '.join(supported_platforms)}.")

    if not os.path.exists(config_dict["project_root"]):
        raise ValueError("project_root must be a valid path.")
    if not os.path.exists(os.path.join(config_dict["project_root"], config_dict["jenkins_file"])):
        raise ValueError("jenkins_file must be a valid path in the project root.")
    if not os.path.exists(os.path.join(config_dict["project_root"], config_dict["plugin_file"])):
        raise ValueError("plugin_file must be a valid path in the project root.")

    os_list = [
        "WindowsServer-2025-datacenter",
        "WindowsServer-2022-datacenter",
        "WindowsServer-2016-datacenter",
        "Windows11",
        "LinuxDebian12",
        "LinuxDebian12-ARM",
        "LinuxUbuntuServer_24_04-LTS",
        "LinuxUbuntuServer_24_04-LTS-ARM",
        "LinuxRhel9",
        "LinuxRhel9-ARM",
        "LinuxFedora41",
        "LinuxFedora41-ARM",
        "LinuxRocky9",
        "LinuxRocky8-ARM",
        "LinuxAlma9",
        "LinuxAlma9-ARM",
        "LinuxOracle9",
        "LinuxOracle9-ARM",
        "LinuxSuse15",
        "LinuxSuse15-ARM",
    ]

    for os_item in config_dict["os"]:
        if os_item not in os_list:
            raise ValueError(f"Invalid os: {os_item}")

    log_levels = ["debug", "info", "warning", "error", "critical"]
    if config_dict["log_level"].lower() not in log_levels:
        raise ValueError(f"Invalid log_level: {config_dict['log_level']}. Supported log levels are: {', '.join(log_levels)}")

    return config_dict


@log
def setup_terraform_vars(config: dict, logger: Logger) -> None:
    """
    Set up Terraform environment variables.

    Args:
        config: Configuration dictionary.
        logger: Logger instance for logging.
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

    for key, value in env_vars.items():
        logger.debug(f"Setting environment variable {key} = {value}")

    os.environ.update(env_vars)
    logger.info("Terraform environment variables have been set up.")
