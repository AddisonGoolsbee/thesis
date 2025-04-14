import shutil
import subprocess

from utils.openai import generate_code, generate_analysis
from utils.io import Timer, run_command_with_timeout
from utils.logger import Logger


def main():
    with Timer("Booting Theseus..."):
        cmd_1 = "python3 src/examples/bootTheseus.py"
        theseus_boot_output = run_command_with_timeout(cmd_1, 1)
        print(theseus_boot_output)
        # run_output = run_command_with_timeout(RUN_CMD, RUN_TIMEOUT, RUN_EXPECTED_OUTPUT)
        exit(0)

    task_description = (
        "Add a few comments here and there and reorder some lines where it won't change the functionality"
    )
    # CODE_PATH = "temp.rs"
    CODE_PATH = "~/Desktop/Theseus/kernel/e1000/src/lib.rs"
    # BUILD_CMD = f"rustc {CODE_PATH} -o prog"
    BUILD_CMD = f"gmake iso -C ~/Desktop/Theseus/ net=user"
    RUN_CMD = f"gmake orun net=user graphic=no SERIAL1=pty SERIAL2=pty"
    # gmake orun net=user graphic=no SERIAL2=pty
    RUN_TIMEOUT = 10
    RUN_EXPECTED_OUTPUT = "This is a simple Rust program."

    with open(CODE_PATH, "r", encoding="utf-8") as f:
        current_code = f.read()
        new_code = current_code

    logger = Logger()

    logger.begin_goal(task_description)
    MAX_RETRIES = 5

    # Main loop:
    while True:
        # Step 1: Generate new code via patch file
        with Timer("Generating..."):
            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    new_code, replacements = generate_code(task_description, current_code)
                    logger.log_generated_code(replacements, new_code, attempt)
                    break
                except Exception as e:
                    print(f"\nError: {e} (Attempt {attempt}/{MAX_RETRIES})")
                    if attempt == MAX_RETRIES:
                        logger.log_status("Max code generation retries reached. Aborting.")
                        exit(1)

        with open(CODE_PATH, "w", encoding="utf-8") as f:
            f.write(new_code)

        # Step 2: Compilation
        with Timer("Building..."):
            process = subprocess.run(BUILD_CMD, shell=True, capture_output=True, text=True)
        build_output = f"[Return code: {process.returncode}]\n {process.stderr}"

        with Timer("Analyzing compilation..."):
            analysis = generate_analysis(task_description, new_code, build_output)
        if analysis.lower().startswith("good"):
            logger.log_status("Compilation ✅")
        elif analysis.lower().startswith("bad: "):
            logger.log_status("Compilation ❌")
            task_description = analysis[5:]
            continue
        elif analysis.lower().startswith("stop: "):
            logger.log_status("Compilation ❌")
            logger.log_status("Build command error: ", analysis[6:])
        else:
            logger.log_status("Analysis unsuccessful, retrying...")
            continue

        # Step 3: Run the program with a basic unit test
        with Timer("Running basic test..."):
            theseus_boot_output = run_command_with_timeout(RUN_CMD, RUN_TIMEOUT)
            run_output = run_command_with_timeout(RUN_CMD, RUN_TIMEOUT, RUN_EXPECTED_OUTPUT)

        if RUN_EXPECTED_OUTPUT in run_output:
            logger.log_status("Basic test ✅")
            break
        else:
            logger.log_status("Basic test ❌")
            logger.log_status(f"Expected output: {RUN_EXPECTED_OUTPUT}")
            logger.log_status(f"Output: {run_output}")
            continue


if __name__ == "__main__":
    try:
        main()
        raise KeyboardInterrupt
    except KeyboardInterrupt:
        print("\nExiting program.")
        logger = Logger()
        shutil.copy(logger.original_path, logger.initial_path)
        print("Reverted code to original state.")
        print("Logs saved to:", logger.run_dir)
        exit(0)
