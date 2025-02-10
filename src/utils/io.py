import threading
import time
import sys

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


