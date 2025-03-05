import threading
import time
import sys
import subprocess

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


def run_command_with_timeout(run_cmd, run_timeout, expected_output=None):
    output_lines = []

    try:
        process = subprocess.Popen(
            run_cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        # get output in real time
        start_time = time.time()
        while process.poll() is None:
            line = process.stdout.readline()
            if line:
                output_lines.append(line)
                if expected_output and expected_output in line:
                    process.kill()
                    break
            if time.time() - start_time > run_timeout:
                raise subprocess.TimeoutExpired(run_cmd, run_timeout)

        result_stdout = "".join(output_lines)

    except subprocess.TimeoutExpired:
        process.kill()
        result_stdout = "".join(output_lines)
        result_stdout += f"\nTimeout of {run_timeout} seconds expired."

    return result_stdout
