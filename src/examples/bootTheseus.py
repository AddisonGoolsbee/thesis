#!/usr/bin/env python3
import select
import subprocess
import re
import threading
import time
import sys
import os
import signal
import pexpect

process = None
debug_dev = None
terminal_dev = None
error_found = False
ready_event = threading.Event()

SESSION = "theseus"
BOOT_CMD = "gmake orun -C ~/Desktop/Theseus/ net=user graphic=no SERIAL1=pty SERIAL2=pty"
UNIT_TEST_CMD = "ping 8.8.8.8 -t 3"


def cleanup(signum=None, frame=None):
    global process
    print("Cleaning up Theseus!", flush=True)
    if process and process.poll() is None:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except Exception:
            pass
    sys.exit(0)


def capture_ttys():
    global process, debug_dev, terminal_dev, error_found

    print(f"Running command: {BOOT_CMD}", flush=True)

    process = subprocess.Popen(
        BOOT_CMD,
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
            break
        # print(line, end="", flush=True)

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

    end_time = time.time() + 0.3
    while time.time() < end_time and process.poll() is None:
        rlist, _, _ = select.select([process.stdout], [], [], 0.1)
        if rlist:
            line = process.stdout.readline()
            if not line:
                continue
            # print(line, end="", flush=True)
            if "gmake: *** [Makefile:997: orun] Error 1" in line:
                error_found = True
                break

    if error_found:
        print("❌ gmake failed inside bootTheseus!", flush=True)
        cleanup()

    ready_event.set()


def wait_for_prompt(ser, prompt=b">", timeout=10):
    start = time.time()
    buffer = b""
    while time.time() - start < timeout:
        ser.write(b"\r")
        time.sleep(0.2)
        buffer += ser.read(1024)
        if prompt in buffer:
            # print(prompt.decode(), flush=True)
            return True
    return False


def clean_ansi_and_control(output: str) -> str:
    # Remove ANSI escape sequences
    output = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", output)
    # Remove bell, carriage return, and vertical tab
    output = re.sub(r"[\x07\r\v]", "", output)
    # Handle backspace sequences like "a\b" → remove the character before
    while "\b" in output:
        output = re.sub(r".\x08", "", output)
    return output


def perform_unit_test(debug, terminal):
    child = pexpect.spawn(f"screen -S {SESSION} {terminal}", encoding="utf-8")
    time.sleep(0.1)

    child.send("\r")
    child.expect(">", timeout=5)
    print("✅ Theseus booted successfully! Running unit test...", flush=True)

    child.send(UNIT_TEST_CMD + "\r")

    output = ""
    while True:
        try:
            chunk = child.read_nonblocking(size=1024, timeout=2)
            if ">" in chunk and len(output) > 40:
                break
            output += chunk
        except pexpect.exceptions.TIMEOUT:
            if len(output) < 50:
                output = ""
                child.send(UNIT_TEST_CMD + "\r")
                continue
            break

    clean_output = clean_ansi_and_control(output)

    with open("temp.txt", "w") as f:
        f.write(clean_output)

    child.send("\x01" + "d")  # Ctrl-A D to detach
    child.close()

    subprocess.run(["screen", "-S", SESSION, "-X", "quit"])


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, cleanup)
    signal.signal(signal.SIGINT, cleanup)

    thread = threading.Thread(target=capture_ttys)
    thread.start()

    print("⏳ Waiting for Theseus to boot...", flush=True)
    ready_event.wait()

    if not error_found:
        perform_unit_test(debug_dev, terminal_dev)

    cleanup()

    thread.join()
