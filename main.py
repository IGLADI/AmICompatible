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
        # this is for futureproofness, currently only azure is supported
        # we could also do this trough terraform variables, this will be chosen when we have more providers
        match cfg["platform"]:
            case "azure":
                terraform_dir = "./terraform/azure"
            case _:
                print(f"Error: Unsupported platform '{cfg['platform']}' specified.")
                sys.exit(1)

        results = {}
        for os_name in cfg["os"]:
            try:
                if "windows" in os_name.lower():
                    # for windows we ssh via a password as a windows vm requires to specify a password either way
                    password = vm.generate_password()
                    os.environ["TF_VAR_password"] = password
                    vm.deploy_and_test_vm(f"{terraform_dir}/windows", os_name, cfg, password, windows=True)
                else:
                    vm.deploy_and_test_vm(f"{terraform_dir}/linux", os_name, cfg)
                print(f"Deployment and test for {os_name} succeeded.")
                results[os_name] = "succeeded"
            except Exception as e:
                print(f"Deployment and test for {os_name} failed: {e}")
                results[os_name] = f"failed: {e}"

        print("\nTest Results:")
        for os_name, result in results.items():
            print(f"{os_name}: {result}")
    finally:
        vm.cleanup()


if __name__ == "__main__":
    main()
