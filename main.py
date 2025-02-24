import concurrent.futures
import multiprocessing
import os
import signal
import sys

from modules import config, ssh, vm


def ignore_interrupt(signum, frame, interrupt, executor, results, cfg):
    interrupt.value = True

    print("Gracefully terminating... No new deployments will be started.")

    for os_name in cfg["os"]:
        if os_name not in results:
            results[os_name] = "cancelled"


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

        # multithreading done with help of copilot
        # we have to use separate processes or keyboard interrupts won't be passed to the threads
        # permit to share data between processes
        with multiprocessing.Manager() as manager:
            interrupt = manager.Value("b", False)
            # ignore interupts in the main thread
            signal.signal(signal.SIGINT, lambda signum, frame: ignore_interrupt(signum, frame, interrupt, executor, results, cfg))
            # separate processes else the keyboard interrupt will not be passed to the threads
            with concurrent.futures.ProcessPoolExecutor(cfg["max_threads"]) as executor:
                future_to_os = {executor.submit(vm.deploy_and_test, os_name, cfg, terraform_dir, interrupt): os_name for os_name in cfg["os"]}
                for future in concurrent.futures.as_completed(future_to_os):
                    # prevent to store errors on cancelled deployments
                    if not interrupt.value:
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
