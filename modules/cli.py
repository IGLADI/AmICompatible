import shutil
import signal
import subprocess
import sys
import threading
from logging import Logger

from .custom_logging import log


# w help of chatgpt for signal, subprocess, threading
@log
def run(
    *args,
    logger: Logger,
    ignore_interrupts: bool = False,
    ignore_all_interrupts: bool = False,
    env: dict | None = None,
    text=True,
    check=True,
    **kwargs,
) -> tuple:
    """
    Run a command in a subprocess, with options to handle keyboard interrupts.

    Args:
        *args: Command and arguments to execute.
        logger: Logger instance for logging messages.
        ignore_interrupts: If True, only the first keyboard interrupt is passed to the subprocess. Defaults to False.
        ignore_all_interrupts: If True, all keyboard interrupts are ignored. Defaults to False.
        env: Environment variables to set for the subprocess. Defaults to None.
        text: If True, the output will be treated as text. Defaults to True.
        check: If True, an exception is raised if the subprocess exits with a non-zero status. Defaults to True.
        **kwargs: Additional keyword arguments passed to subprocess.Popen.

    Returns:
        subprocess.CompletedProcess: The completed process, including stdout and stderr.

    Raises:
        KeyboardInterrupt: If the command is interrupted by a keyboard signal and `check` is True.
        subprocess.CalledProcessError: If the subprocess exits with a non-zero status and `check` is True.
    """
    if ignore_all_interrupts:
        logger.info("Executing critical command, ignoring all keyboard interrupts...")
    elif ignore_interrupts:
        logger.info("Executing a command, only passing the first keyboard interrupt...")

    @log
    def handler(logger):
        """
        Handles keyboard interrupts during the execution of a subprocess.

        Args:
            _: Placeholder for signum.
            __: Placeholder for frame.
        """
        if ignore_all_interrupts:
            logger.info("Keyboard interrupts ignored.")
        elif ignore_interrupts:
            # nonlocal is needed to modify the variable in the outer scope but not in the global scope
            nonlocal first_interrupt
            if first_interrupt:
                logger.info("First Ctrl+C received, passing to subprocess...")
                first_interrupt = False
                proc.send_signal(signal.SIGINT)
            else:
                logger.info("Subsequent Ctrl+C ignored.")
        else:
            logger.info("Keyboard interrupt received, terminating subprocess...")
            proc.terminate()

    first_interrupt = True
    old_handler = signal.signal(
        signal.SIGINT, lambda signum, frame: handler(logger=logger)
    )
    logger.debug("Signal handler set.")

    try:
        proc = subprocess.Popen(
            *args,
            # shell=shell,
            text=text,
            **kwargs,
            env=env,
            # Use stdout and stderr as the current terminal output
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            # immediately view the output
            bufsize=1,
            universal_newlines=True,
            # separate sessions to prevent the command itself from handling the interrupt
            start_new_session=True,
        )
        logger.debug("Subprocess started.")

        stdout_lines = []
        stderr_lines = []

        @log
        def log_stream(pipe, log_level, stream, accumulator, logger: Logger):
            for line in iter(pipe.readline, ""):
                if line:
                    logger.log(log_level, line.rstrip())
                    stream.write(line)
                    stream.flush()
                    accumulator.append(line)  # Store the output

            pipe.close()

        # Create threads to concurrently capture stdout and stderr
        stdout_thread = threading.Thread(
            target=log_stream,
            args=(proc.stdout, logger.level, sys.stdout, stdout_lines),
            kwargs={"logger": logger},
        )
        stderr_thread = threading.Thread(
            target=log_stream,
            args=(proc.stderr, getattr(logger, "ERROR", 40), sys.stderr, stderr_lines),
            kwargs={"logger": logger},
        )
        stdout_thread.start()
        stderr_thread.start()
        logger.debug("Output capture threads started.")

        proc.wait()
        stdout_thread.join()
        stderr_thread.join()
        logger.debug("Subprocess and output capture threads completed.")

        stdout = "".join(stdout_lines)
        stderr = "".join(stderr_lines)

        # Raise exception if the process did not exit successfully
        if check and proc.returncode != 0:
            if (
                proc.returncode == 130
            ):  # 130 typically indicates termination due to SIGINT
                raise KeyboardInterrupt("Command interrupted.")
            else:
                raise subprocess.CalledProcessError(
                    returncode=proc.returncode,
                    cmd=args[0] if args else kwargs.get("args"),
                    output=stdout,
                    stderr=stderr,
                )

        return stdout, stderr
    finally:
        if ignore_all_interrupts or ignore_interrupts:
            signal.signal(signal.SIGINT, old_handler)
            logger.info("Command executed, keyboard interrupts restored.")


def check_dependencies():
    # no need to install az cli, this is not needed to run the script only to get the credentials in aic.yml
    for cmd in ["terraform", "ansible"]:
        if shutil.which(cmd) is None:
            print(f"Error: '{cmd}' is not installed or not in PATH.")
            sys.exit(1)
