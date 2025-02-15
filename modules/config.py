import os

import yaml


def load_config():
    with open("aic.yml") as config:
        return yaml.safe_load(config)


def setup_terraform_vars(config):
    env_vars = {
        "TF_VAR_subscription_id": config["subscription_id"],
        "TF_VAR_tenant_id": config["tenant_id"],
        "TF_VAR_appId": config["appId"],
        "TF_VAR_client_secret": config["client_secret"],
        "TF_VAR_region": config["region"],
        "TF_VAR_vm_size": config["vm_size"],
        "TF_VAR_ssh_public_key_path": "../../../temp/id_rsa.pub",
    }
    os.environ.update(env_vars)
