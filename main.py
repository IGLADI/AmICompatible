from modules import config, ssh, vm
import sys
import os
import secrets


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
                if "windows" in os_name.lower():
                    # for windows we ssh via a password as a windows vm requires to specify a password either way
                    while True:
                        password = secrets.token_urlsafe(32)
                        # check if it fulfills the azure password requirements (made with help of copilot)
                        if any(c.islower() for c in password) and any(c.isupper() for c in password) and any(c.isdigit() for c in password):
                            break
                        else:
                            print("Password does not meet Azure requirements, generating a new one...")
                    os.environ["TF_VAR_password"] = password
                    vm.deploy_and_test_vm(f"{terraform_dir}/windows", os_name, cfg, password, windows=True)
                else:
                    vm.deploy_and_test_vm(f"{terraform_dir}/linux", os_name, cfg)
                print(f"Deployment and test for {os_name} succeeded.")
            except Exception as e:
                print(f"Deployment and test for {os_name} failed: {e}")
    finally:
        vm.cleanup()


if __name__ == "__main__":
    main()
