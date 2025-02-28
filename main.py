import concurrent.futures
import multiprocessing
import os
import signal
import sys

from modules import config, metrics, ssh, vm


def handler(interrupt: multiprocessing.Value, results: dict, cfg: dict) -> None:  # type: ignore
    """
    Handle interrupt signals.

    Args:
        interrupt: Shared value across processes to handle interrupts.
        results: Dictionary to store results.
        cfg: Configuration dictionary.
    """
    interrupt.value = True

    for os_name in cfg["os"]:
        if os_name not in results:
            results[os_name] = "cancelled"


def main() -> None:
    try:
        cfg = config.load_config()
        config.setup_terraform_vars(cfg)

        os.makedirs("temp", exist_ok=True)
        ssh.create_ssh_key()

        # other providers can be added by creating new terraform directories
        # this is for futureproofness, currently only azure is supported
        # we could also do this trough terraform variables, this will be chosen when we add more providers
        match cfg["platform"]:
            case "azure":
                terraform_dir = "./terraform/azure"
            case _:
                print(f"Error: Unsupported platform '{cfg['platform']}' specified.")
                sys.exit(1)

        results = {}
        metrics_results = {}

        # multithreading done with help of copilot
        # permit to share data between processes
        with multiprocessing.Manager() as manager:
            interrupt = manager.Value("b", False)
            # ignore interupts in the main thread
            signal.signal(signal.SIGINT, lambda signum, frame: handler(interrupt, results, cfg))
            # separate processes else the keyboard interrupt will not be passed to the threads
            with concurrent.futures.ProcessPoolExecutor(cfg["max_threads"]) as executor:
                future_to_os = {executor.submit(vm.deploy_and_test, os_name, cfg, terraform_dir, interrupt): os_name for os_name in cfg["os"]}
                for future in concurrent.futures.as_completed(future_to_os):
                    # prevent to store errors on cancelled deployments
                    if not interrupt.value:
                        os_name, results[os_name], metrics_results[os_name] = future.result()

        print("Metrics:")
        metrics.display_metrics(results, metrics_results)

        print("Test Results:")
        for os_name, result in results.items():
            if result == "succeeded":
                # color coting the output done w help of chatgpt
                print(f"\033[92m{os_name}: {result}\033[0m")
            elif result == "cancelled":
                print(f"\033[93m{os_name}: {result}\033[0m")
            else:
                print(f"\033[91m{os_name}: {result}\033[0m")

        if all(result == "succeeded" for result in results.values()):
            sys.exit(0)
        else:
            sys.exit(1)
    finally:
        vm.cleanup()


if __name__ == "__main__":
    main()
