from modules import config, ssh, vm
import sys
import os


def main():
    try:
        cfg = config.load_config()
        config.setup_terraform_vars(cfg)

        os.makedirs("temp", exist_ok=True)
        ssh.create_ssh_key()

        # other providers can be added by creating new terraform directories
        match cfg["platform"]:
            case "azure":
                terraform_dir = "./terraform/azure"
            case _:
                print(f"Error: Unsupported platform '{cfg['platform']}' specified.")
                sys.exit(1)

        for os_name in cfg["os"]:
            try:
                vm.deploy_and_test_vm(terraform_dir, os_name, cfg)
                print(f"Deployment and test for {os_name} succeeded.")
            except Exception as e:
                print(f"Deployment and test for {os_name} failed: {e}")
    finally:
        vm.cleanup()


if __name__ == "__main__":
    main()
