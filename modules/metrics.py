import threading
import time

import plotext

from . import ssh


def display_metrics(results, metrics_results):
    """
    Display metrics.

    Args:
        results: Dictionary containing test results.
        metrics_results: Dictionary containing metrics results.
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
            # space between each os
            print("")


class MetricsCollector:
    def __init__(self, client, interval=1, windows=False):
        """
        Initialize the MetricsCollector.

        Args:
            client: SSH client connected to the VM.
            interval: Interval between metric collections in seconds.
            windows: Whether the VM is a Windows VM.
        """
        self.client = client
        self.interval = interval
        self.windows = windows
        self.cpu_usage = []
        self.ram_usage = []
        self._stop_flag = False
        self._thread = None

    def start(self):
        """
        Start collecting metrics.
        """
        self._stop_flag = False
        self._thread = threading.Thread(target=self._collect_metrics)
        self._thread.start()

    def _collect_metrics(self):
        """
        Collect metrics.
        """
        while not self._stop_flag:
            cpu = self._get_cpu_sample()
            self.cpu_usage.append(cpu)
            ram = self._get_ram_sample()
            self.ram_usage.append(ram)
            time.sleep(self.interval)

    # generated by chatgpt
    def _get_cpu_sample(self):
        """
        Get a CPU usage sample.

        Returns:
            CPU usage percentage.
        """
        if self.windows:
            stdout, stderr = ssh.execute_ssh_command(
                self.client,
                "(Get-Counter '\\Processor(_Total)\\% Processor Time').CounterSamples.CookedValue",
                print_output=False,
            )
        else:
            stdout, stderr = ssh.execute_ssh_command(
                self.client, "top -bn1 | grep '%Cpu' | sed 's/.*, *\\([0-9.]*\\)%* id.*/\\1/' | awk '{print 100 - $1}'", print_output=False
            )
        return float(stdout)

    # generated by chatgpt
    def _get_ram_sample(self):
        """
        Get a RAM usage sample.

        Returns:
            RAM usage percentage.
        """
        if self.windows:
            stdout, stderr = ssh.execute_ssh_command(
                self.client,
                "(Get-Counter '\\Memory\\% Committed Bytes In Use').CounterSamples.CookedValue",
                print_output=False,
            )
        else:
            stdout, stderr = ssh.execute_ssh_command(self.client, "free | grep Mem | awk '{print $3/$2 * 100.0}'", print_output=False)
        return float(stdout)

    def get_results(self):
        """
        Get the collected metrics results.

        Returns:
            CPU usage and RAM usage.
        """
        self.stop()
        return self.cpu_usage, self.ram_usage

    def stop(self):
        """
        Stop collecting metrics.
        """
        self._stop_flag = True
        if self._thread is not None:
            self._thread.join()
