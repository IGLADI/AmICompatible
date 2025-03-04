import threading
import time
from logging import Logger

import paramiko
import plotext

from . import ssh
from .custom_logging import log


@log
def display_and_save_metrics(
    results: dict, metrics_results: dict, log_dir: str, logger: Logger
) -> None:
    """
    Display metrics results in simple line graph.

    Args:
        results: Dictionary containing test results.
        metrics_results: Dictionary containing metrics results.
        log_dir: Directory for log files.
        logger: Logger instance for logging.
    """
    plotext.theme("dark")
    plotext.plotsize(plotext.terminal_width(), 20)
    for os_name, result in results.items():
        if result == "succeeded":
            cpu_usage, ram_usage = metrics_results[os_name]

            plotext.clear_data()
            # for some reason this is considered data so we need to reset it after each data clear
            plotext.ylim(0, 100)
            plotext.plot(cpu_usage, label="CPU Usage")
            plotext.plot(ram_usage, label="RAM Usage")
            plotext.xlabel("Time (s)")
            plotext.ylabel("Usage (%)")
            plotext.title(f"Resource Usage on {os_name}")
            plotext.show()
            plotext.save_fig(f"{log_dir}/{os_name}/metrics.result")
            # space between each os
            print("")


# we use a class just to easily stop the thread, this could be a different file too but it makes more sense create a module per scope/feature in this case
class MetricsCollector:
    @log
    def __init__(
        self,
        client: paramiko.SSHClient,
        logger: Logger,
        interval: int = 1,
        windows: bool = False,
    ) -> None:
        """
        Initialize the MetricsCollector.

        Args:
            client: SSH client connected to the VM.
            logging: Logger instance for logging.
            interval: Interval between metric collections in seconds.
            windows: Whether the VM is a Windows VM.
        """
        self.client = client
        self.logger = logger
        self.interval = interval
        self.windows = windows
        self.cpu_usage = []
        self.ram_usage = []
        self._stop_flag = False
        self._thread = None

    @log
    def start(self, logger: Logger) -> None:
        """
        Start collecting metrics.

        Args:
            logger: Logger instance for logging.
        """
        self._stop_flag = False
        self._thread = threading.Thread(
            target=self._collect_metrics, kwargs={"logger": logger}
        )
        self._thread.start()
        self.logger.debug("Metrics collection thread started.")

    @log
    def _collect_metrics(self, logger: Logger) -> None:
        """
        Collect metrics.

        Args:
            logger: Logger instance for logging.
        """
        while not self._stop_flag:
            cpu = self._get_cpu_sample(logger=logger)
            self.cpu_usage.append(cpu)
            ram = self._get_ram_sample(logger=logger)
            self.ram_usage.append(ram)
            time.sleep(self.interval)
        self.logger.debug("Metrics collection in progress.")

    # generated by chatgpt
    @log
    def _get_cpu_sample(self, logger: Logger) -> float:
        """
        Get a CPU usage sample.

        Args:
            logger: Logger instance for logging.

        Returns:
            CPU usage percentage.
        """
        if self.windows:
            stdout, stderr = ssh.execute_ssh_command(
                self.client,
                "(Get-Counter '\\Processor(_Total)\\% Processor Time').CounterSamples.CookedValue",
                logger=logger,
                print_output=False,
            )
        else:
            stdout, stderr = ssh.execute_ssh_command(
                self.client,
                "top -bn1 | grep '%Cpu' | sed 's/.*, *\\([0-9.]*\\)%* id.*/\\1/' | awk '{print 100 - $1}'",
                logger=logger,
                print_output=False,
            )
        return float(stdout)

    # generated by chatgpt
    @log
    def _get_ram_sample(self, logger: Logger) -> float:
        """
        Get a RAM usage sample.

        Args:
            logger: Logger instance for logging.

        Returns:
            RAM usage percentage.
        """
        if self.windows:
            stdout, stderr = ssh.execute_ssh_command(
                self.client,
                "(Get-Counter '\\Memory\\% Committed Bytes In Use').CounterSamples.CookedValue",
                logger=logger,
                print_output=False,
            )
        else:
            stdout, stderr = ssh.execute_ssh_command(
                self.client,
                "free | grep Mem | awk '{print $3/$2 * 100.0}'",
                logger=logger,
                print_output=False,
            )
        return float(stdout)

    @log
    def get_results(self, logger: Logger) -> tuple[list, list]:
        """
        Get the collected metrics results.

        Args:
            logger: Logger instance for logging.

        Returns:
            CPU usage and RAM usage.
        """
        self.stop(logger=logger)
        self.logger.debug("Metrics collection stopped.")
        return self.cpu_usage, self.ram_usage

    @log
    def stop(self, logger: Logger) -> None:
        """
        Stop collecting metrics.

        Args:
            logger: Logger instance for logging.
        """
        self._stop_flag = True
        if self._thread is not None:
            self._thread.join()
            self.logger.debug("Metrics collection thread ended.")
