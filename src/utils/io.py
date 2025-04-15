import threading
import time
import sys
import subprocess
import os
import signal


class Timer:
    def __init__(self, message="Processing..."):
        self.done_flag = threading.Event()
        self.message = message
        self.thread = threading.Thread(target=self._update_timer)

    def _update_timer(self):
        start_time = time.perf_counter()
        while not self.done_flag.is_set():
            elapsed = time.perf_counter() - start_time
            sys.stdout.write(f"\r{self.message} ({elapsed:.2f}s)")
            sys.stdout.flush()
            time.sleep(0.1)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.done_flag.set()
        self.thread.join()
        print()


def run_command_with_timeout(run_cmd, run_timeout):
    process = subprocess.Popen(
        run_cmd,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        preexec_fn=os.setsid
    )

    try:
        output, _ = process.communicate(timeout=run_timeout)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGTERM)
            time.sleep(0.01)
        except ProcessLookupError:
            print("Process group already exited.")
        output, _ = process.communicate()
        output += f"\nProcess killed after {run_timeout} seconds timeout"

    return output
