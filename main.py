import concurrent.futures
import multiprocessing
import os
import signal
import sys
from logging import Logger

from modules import config, custom_logging, metrics, ssh, vm
from modules.custom_logging import log


@log
def handler(interrupt: multiprocessing.Value, results: dict, cfg: dict, logger: Logger) -> None:  # type: ignore
    """
    Handle interrupt signals.

    Args:
        interrupt: Shared value across processes to handle interrupts.
        results: Dictionary to store results.
        cfg: Configuration dictionary.
        logger: Logger instance for logging.
    """
    if not interrupt.value:
        logger.warning("Interrupt signal received. Setting interrupt flag.")
        interrupt.value = True
    else:
        return


def main() -> None:
    try:
        cfg = config.load_config()
        print("Configuration loaded.")

        log_dir = custom_logging.create_log_folder(cfg["log_dir"])
        logger = custom_logging.setup_logger(
            f"{log_dir}/main.log", cfg["log_level"], "main"
        )

        logger.debug(f"Configuration: {cfg}")

        config.setup_terraform_vars(cfg, logger=logger)
        logger.debug("Terraform variables set up.")

        os.makedirs("temp", exist_ok=True)
        logger.debug("Ensured 'temp' directory exists.")
        ssh.create_ssh_key(logger=logger)
        logger.info("SSH key created.")

        # other providers can be added by creating new terraform directories
        # this is for futureproofness, currently only azure is supported
        # we could also do this trough terraform variables, this will be chosen when we add more providers
        match cfg["platform"]:
            case "azure":
                terraform_dir = "./terraform/azure"
                logger.debug(
                    "Platform set to Azure. Using terraform directory: ./terraform/azure"
                )
            case _:
                logger.error(
                    f"Error: Unsupported platform '{cfg['platform']}' specified."
                )
                sys.exit(1)

        results = {}
        # set them as cancelled until they are done
        for os_name in cfg["os"]:
            if os_name not in results:
                results[os_name] = "cancelled"
                logger.info(f"Marking {os_name} as cancelled due to interrupt.")
        metrics_results = {}

        # multithreading done with help of copilot
        # permit to share data between processes
        with multiprocessing.Manager() as manager:
            interrupt = manager.Value("b", False)
            # ignore interupts in the main thread
            signal.signal(
                signal.SIGINT,
                lambda signum, frame: handler(interrupt, results, cfg, logger=logger),
            )
            # separate processes else the keyboard interrupt will not be passed to the threads
            logger.debug("Starting ProcessPoolExecutor.")
            with concurrent.futures.ProcessPoolExecutor(cfg["max_threads"]) as executor:
                # Submit tasks for each OS deployment
                future_to_os = {
                    executor.submit(
                        vm.deploy_and_test,
                        os_name,
                        cfg,
                        terraform_dir,
                        f"{log_dir}/{os_name}",
                        logger=logger,
                        interrupt=interrupt,
                    ): os_name
                    for os_name in cfg["os"]
                }
                logger.debug(f"Submitted {len(future_to_os)} deployment tasks.")
                for future in concurrent.futures.as_completed(future_to_os):
                    # prevent to store errors on cancelled deployments
                    if not interrupt.value:
                        os_name, result, metrics_result = future.result()
                        results[os_name] = result
                        metrics_results[os_name] = metrics_result
                    else:
                        logger.warning(
                            "Skipping result processing due to interrupt flag."
                        )

        logger.info("Metrics:")
        metrics.display_and_save_metrics(
            results, metrics_results, log_dir, logger=logger
        )

        logger.info("Test Results:")
        for os_name, result in results.items():
            if result == "succeeded":
                # color coting the output done w help of chatgpt
                logger.info(f"\033[92m{os_name}: {result}\033[0m")
            elif result == "cancelled":
                logger.warning(f"\033[93m{os_name}: {result}\033[0m")
            else:
                logger.error(f"\033[91m{os_name}: {result}\033[0m")

        if all(result == "succeeded" for result in results.values()):
            logger.info("All deployments succeeded. Exiting with status 0.")
            sys.exit(0)
        else:
            logger.error(
                "One or more deployments failed or were cancelled. Exiting with status 1."
            )
            sys.exit(1)
    finally:
        logger.info("Cleaning up resources.")
        vm.cleanup(logger=logger)
        logger.info("Cleanup complete.")


if __name__ == "__main__":
    main()
