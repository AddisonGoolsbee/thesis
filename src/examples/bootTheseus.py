#!/usr/bin/env python3
import subprocess
import re
import time
import sys
import os
import signal

process = None  # global so finally block can access it

def handle_sigterm(signum, frame):
    raise KeyboardInterrupt

signal.signal(signal.SIGTERM, handle_sigterm)

def capture_ttys():
    global process

    run_cmd = "gmake orun -C ~/Desktop/Theseus/ net=user graphic=no SERIAL1=pty SERIAL2=pty"
    debug_dev = None
    terminal_dev = None
    saw_make_error = False
    collected_lines = []

    print(f"Running command: {run_cmd}", flush=True)
    print("Waiting for ttys information...", flush=True)

    process = subprocess.Popen(
        run_cmd,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        preexec_fn=os.setsid,
    )

    pattern = r"char device redirected to (/dev/ttys\d+) \(label (serial\d+-base)\)"

    while process.poll() is None:
        line = process.stdout.readline()
        if not line:
            continue
        print(line, end="", flush=True)
        collected_lines.append(line)

        match = re.search(pattern, line)
        if match:
            ttys_path = match.group(1)
            label = match.group(2)
            if label == "serial0-base":
                debug_dev = ttys_path
            elif label == "serial1-base":
                terminal_dev = ttys_path
            if debug_dev and terminal_dev:
                break

    # Wait one more second for late errors
    end_time = time.time() + 1
    while time.time() < end_time and process.poll() is None:
        line = process.stdout.readline()
        if not line:
            continue
        print(line, end="", flush=True)
        collected_lines.append(line)
        if "gmake: *** [Makefile:997: orun] Error 1" in line:
            saw_make_error = True

    if saw_make_error:
        print("❌ gmake failed inside bootTheseus!", flush=True)
        sys.exit(1)

    print(f"\nDEBUG_DEV: {debug_dev}", flush=True)
    print(f"TERMINAL_DEV: {terminal_dev}", flush=True)
    print("\nScript completed. The gmake orun process is still running.", flush=True)
    print("Press Ctrl+C to exit.", flush=True)

    # Keep alive until forcibly killed
    while True:
        time.sleep(1)


def cleanup():
    global process
    if process and process.poll() is None:
        try:
            print(f"Killing gmake process group {process.pid}", flush=True)
            os.killpg(process.pid, signal.SIGTERM)
        except Exception:
            pass


if __name__ == "__main__":
    try:
        capture_ttys()
    finally:
        cleanup()
