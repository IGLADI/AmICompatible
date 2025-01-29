from modules import config, ssh, vm
import sys


def main():
    try:
        ssh.create_ssh_key()

        cfg = config.load_config()
        config.setup_terraform_vars(cfg)

        if cfg["platform"] == "azure":
            terraform_dir = "./terraform/azure"
        else:
            print(f"Error: Unsupported platform '{cfg['platform']}' specified.")
            sys.exit(1)

        for os_name in cfg["os_list"]:
            vm.deploy_and_test_vm(terraform_dir, os_name)
    finally:
        ssh.delete_ssh_key()


if __name__ == "__main__":
    main()
