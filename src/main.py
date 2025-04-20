import shutil
import subprocess

from utils.openai import generate_basic_test_analysis, generate_code, generate_build_analysis
from utils.io import Timer, run_command_with_timeout
from utils.logger import Logger
from utils.misc import count_unsafe
from config import *


def main():
    task_description = "Make the swap function safe"

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
            analysis = generate_build_analysis(task_description, new_code, build_output)

        if analysis.lower().startswith("good"):
            logger.log_status("Compilation ✅")
        elif analysis.lower().startswith("bad: "):
            logger.log_status("Compilation ❌")
            task_description = analysis[5:]
            continue
        elif analysis.lower().startswith("stop: "):
            logger.log_status("Compilation ❌ (build command error)")
            logger.log_status(f"Build command error: {analysis[6:]}")
        else:
            logger.log_status("Analysis unsuccessful, retrying...")
            continue

        # Step 3: Run the program with a basic unit test
        with Timer("Running basic test..."):
            run_output = run_command_with_timeout(BASIC_TEST_CMD, BASIC_TEST_TIMEOUT, BASIC_TEST_EXPECTED_OUTPUT)
            print(run_output)

        if BASIC_TEST_EXPECTED_OUTPUT in run_output:
            logger.log_status("Basic test ✅")
        else:
            logger.log_status("Basic test ❌")
            logger.log_status(f"Expected output: {BASIC_TEST_EXPECTED_OUTPUT}")
            logger.log_status(f"Output: {run_output}")
            with Timer("Analyzing basic test..."):
                analysis = generate_basic_test_analysis(
                    task_description,
                    current_code,
                    new_code,
                    f"The excpected output was:\n{BASIC_TEST_EXPECTED_OUTPUT}\nThe output from running the program was:\n{run_output}",
                )
            continue

        # Step 4: Compare lines of unsafe code
        num_old_unsafe_lines, _ = count_unsafe(current_code)
        num_new_unsafe_lines, _ = count_unsafe(new_code)
        print(f'Result: {num_old_unsafe_lines} unsafe lines -> {num_new_unsafe_lines} unsafe lines')

        print("Reached the end of the loop")
        break


if __name__ == "__main__":
    logger = Logger()
    try:
        main()
    except KeyboardInterrupt:
        print("\nExiting program via keyboard interrupt.")
    except Exception as e:
        print("\nProgram crashed with exception:")
        print(e)
    finally:
        shutil.copy(logger.logger_original_path, logger.initial_path)
        print("Reverted code to original state.")
        print("Logs saved to ", logger.run_dir)
        exit(0)
