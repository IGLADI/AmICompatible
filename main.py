import concurrent.futures
import os
import random
import string
import sys

from modules import config, vm


def main():
    try:
        cfg = config.load_config()
        config.setup_terraform_vars(cfg)

        vm.init()

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

        def deploy_and_test(os_name):
            try:
                env = os.environ.copy()
                # for multiple users executing simultaneous runs on the same subscription
                resource_group_name = f"{cfg["rg_prefix"]}-{os_name}-{''.join(random.choices(string.ascii_letters + string.digits, k=32))}"
                env["TF_VAR_resource_group_name"] = resource_group_name

                if "windows" in os_name.lower():
                    password = vm.generate_password()
                    env["TF_VAR_password"] = password
                    vm.deploy_and_test_vm(f"{terraform_dir}/windows", os_name, cfg, env, password, windows=True)
                else:
                    vm.deploy_and_test_vm(f"{terraform_dir}/linux", os_name, cfg, env=env)
                print(f"Deployment and test for {os_name} succeeded.")
                return os_name, "succeeded"
            except Exception as e:
                print(f"Deployment or test for {os_name} failed: {e}")
                return os_name, f"failed: {e}"

        # help of copilot for multithreading
        with concurrent.futures.ThreadPoolExecutor(cfg["max_threads"]) as executor:
            future_to_os = {executor.submit(deploy_and_test, os_name): os_name for os_name in cfg["os"]}
            for future in concurrent.futures.as_completed(future_to_os):
                os_name, result = future.result()
                results[os_name] = result

        print("\nTest Results:")
        for os_name, result in results.items():
            print(f"{os_name}: {result}")
        if all(result == "succeeded" for result in results.values()):
            sys.exit(0)
        else:
            sys.exit(1)
    finally:
        vm.cleanup()


if __name__ == "__main__":
    main()
