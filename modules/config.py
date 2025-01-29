import configparser
import os
import ast


def load_config():
    config = configparser.ConfigParser()
    config.read("aic.conf")
    platform_config = config["platform"]

    return {
        "platform": platform_config.get("platform"),
        "os_list": ast.literal_eval(platform_config.get("os", "[]")),
        "subscription_id": platform_config["subscription_id"],
        "tenant_id": platform_config["tenant_id"],
        "appId": platform_config["appId"],
        "client_secret": platform_config["client_secret"],
        "region": platform_config["region"],
        "vm_size": platform_config["vm_size"],
    }


def setup_terraform_vars(config):
    env_vars = {
        "TF_VAR_subscription_id": config["subscription_id"],
        "TF_VAR_tenant_id": config["tenant_id"],
        "TF_VAR_appId": config["appId"],
        "TF_VAR_client_secret": config["client_secret"],
        "TF_VAR_region": config["region"],
        "TF_VAR_vm_size": config["vm_size"],
        "TF_VAR_ssh_public_key_path": "../../temp/id_rsa.pub",
    }
    os.environ.update(env_vars)
