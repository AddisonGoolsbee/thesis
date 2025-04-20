import shutil
import subprocess
from enum import Enum, auto
import atexit
from utils.openai import (
    generate_basic_test_analysis,
    generate_code,
    generate_build_analysis,
    generate_code_safety_analysis,
    generate_code_generation_failure_analysis,
)
from utils.io import Timer, run_command_with_timeout
from utils.logger import Logger
from utils.misc import count_unsafe
from utils.strategizer import Strategizer, StrategyStatus
from config import *


class Oxidizer:
    MAX_GENERATION_RETRIES = 5
    MAX_PROMPTS = 10

    def __init__(self):
        self.logger = Logger()
        self.strategizer = Strategizer(self.logger)
        self.best_code = None

        atexit.register(self.cleanup)

    def cleanup(self):
        shutil.copy(self.logger.logger_original_path, self.logger.initial_path)
        print("Reverted code to original state.")
        print("Logs saved to ", self.logger.run_dir)

    def run(self):
        with open(CODE_PATH, "r", encoding="utf-8") as f:
            current_code = f.read()
            self.current_unsafe_lines = count_unsafe(current_code)
            self.best_code = current_code

        # Main loop:
        while True:
            with Timer("Generating new strategy..."):
                strategy_prompt = self.strategizer.generate_strategy(self.best_code)

            result, new_code = self.run_strategy(strategy_prompt, self.best_code)
            self.strategizer.add_strategy(strategy_prompt, result)

            if result == StrategyStatus.SUCCESS:
                self.best_code = new_code

            if self.current_unsafe_lines == 0:
                self.logger.log_status("No unsafe lines remaining. Exiting.")
                break

    def run_strategy(self, strategy_prompt, current_code):
        task_description = strategy_prompt
        num_prompts = 0

        while True:
            self.logger.log_prompt(task_description)
            num_prompts += 1
            if num_prompts > self.MAX_PROMPTS:
                return StrategyStatus.FAILED_TOO_LONG

            # Step 1: Generate new code via patch file
            with Timer("Generating code..."):
                for attempt in range(1, self.MAX_GENERATION_RETRIES + 1):
                    try:
                        new_code, replacements = generate_code(task_description, current_code)
                        self.logger.log_generated_code(replacements, new_code, attempt)
                        break
                    except Exception as e:
                        print(f"\nError: {e} (Attempt {attempt}/{self.MAX_GENERATION_RETRIES})")
                        if attempt == self.MAX_GENERATION_RETRIES:
                            self.logger.log_status("Max code generation retries reached. Aborting.")
                            analysis = generate_code_generation_failure_analysis(
                                task_description,
                                current_code,
                                self.MAX_GENERATION_RETRIES,
                            )
                            task_description = analysis

            with open(CODE_PATH, "w", encoding="utf-8") as f:
                f.write(new_code)

            # Step 2: Compilation
            with Timer("Building..."):
                process = subprocess.run(BUILD_CMD, shell=True, capture_output=True, text=True)
            build_output = f"[Return code: {process.returncode}]\n {process.stderr}"

            with Timer("Analyzing compilation..."):
                analysis = generate_build_analysis(task_description, new_code, build_output)

            if analysis.lower().startswith("good"):
                self.logger.log_status("Compilation ✅")
            elif analysis.lower().startswith("bad: "):
                self.logger.log_status("Compilation ❌")
                task_description = analysis[5:]
                continue
            elif analysis.lower().startswith("stop: "):
                self.logger.log_status("Compilation ❌ (build command error)")
                self.logger.log_status(f"Build command error: {analysis[6:]}")
                exit(1)
            else:
                self.logger.log_status("Analysis unsuccessful, retrying...")
                continue

            # Step 3: Run the program with a basic unit test
            with Timer("Running basic test..."):
                run_output = run_command_with_timeout(BASIC_TEST_CMD, BASIC_TEST_TIMEOUT, BASIC_TEST_EXPECTED_OUTPUT)

            if BASIC_TEST_EXPECTED_OUTPUT in run_output:
                self.logger.log_status("Basic test ✅")
            else:
                self.logger.log_status("Basic test ❌")
                self.logger.log_status(f"Expected output: {BASIC_TEST_EXPECTED_OUTPUT}")
                self.logger.log_status(f"Output: {run_output}")
                with Timer("Analyzing basic test..."):
                    analysis = generate_basic_test_analysis(
                        task_description,
                        current_code,
                        new_code,
                        f"The excpected output was:\n{BASIC_TEST_EXPECTED_OUTPUT}\nThe output from running the program was:\n{run_output}",
                    )
                    task_description = analysis
                continue

            # Step 4: Compare lines of unsafe code
            num_old_unsafe_lines, _ = count_unsafe(current_code)
            num_new_unsafe_lines, _ = count_unsafe(new_code)
            self.logger.log_status(
                f"Result: {num_old_unsafe_lines} unsafe lines -> {num_new_unsafe_lines} unsafe lines"
            )
            if num_old_unsafe_lines <= num_new_unsafe_lines:
                self.logger.log_status("Code safety improved ❌")
                with Timer("Analyzing why new code is not safer..."):
                    analysis = generate_code_safety_analysis(
                        task_description,
                        current_code,
                        new_code,
                        num_old_unsafe_lines,
                        num_new_unsafe_lines,
                    )
                if analysis.lower().startswith("good: "):
                    self.logger.log_status("Strategy can still be used. Trying with new prompt.")
                    task_description = analysis[6:]
                    continue
                else:
                    self.logger.log_status(
                        f"Strategy cannot be used to make code safer for the following reason: {analysis[5:]}"
                    )
                    if num_old_unsafe_lines > num_new_unsafe_lines:
                        return StrategyStatus.CODE_SAFETY_DETERIORATED, new_code
                    else:
                        return StrategyStatus.CODE_SAFETY_UNCHANGED, new_code
            else:
                self.logger.log_status("Code safety improved ✅")
                self.current_unsafe_lines = num_new_unsafe_lines
                return StrategyStatus.SUCCESS, new_code


if __name__ == "__main__":
    oxidizer = Oxidizer()
    try:
        oxidizer.run()
    except KeyboardInterrupt:
        print("\nExiting program via keyboard interrupt.")
    except Exception as e:
        print("\nProgram crashed with exception:")
        print(e)
