import subprocess
import time
import traceback
from utils.openai import (
    generate_test_analysis,
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
    MAX_PROMPTS = 6

    def __init__(self):
        self.logger = Logger()
        self.strategizer = Strategizer(self.logger)
        self.best_code = None
        self.best_toml = None

    def run(self):
        with open(CODE_PATH, "r", encoding="utf-8") as f:
            current_code = f.read()
            self.current_unsafe_lines, _ = count_unsafe(current_code)
            self.best_code = current_code

        if CARGO_PATH:
            with open(CARGO_PATH, "r", encoding="utf-8") as f:
                cargo_toml = f.read()
                self.best_toml = cargo_toml
                self.logger.log_to_run(f"Using Cargo.toml at {CARGO_PATH}")

        self.logger.begin_run(self.current_unsafe_lines)

        # Main loop:
        while True:
            with Timer("Generating new strategy..."):
                strategy_prompt = self.strategizer.generate_strategy(self.best_code, self.best_toml)

            result, new_code, new_toml, attempts, time_taken = self.run_strategy(
                strategy_prompt, self.best_code, self.best_toml
            )
            self.strategizer.add_strategy(strategy_prompt, result, attempts, time_taken, self.current_unsafe_lines)

            if result == StrategyStatus.SUCCESS:
                self.best_code = new_code
                self.best_toml = new_toml
                self.logger.update_best_code(new_code, new_toml)

            if self.current_unsafe_lines == 0:
                self.logger.log_status("No unsafe lines remaining. Exiting.")
                break

            if self.strategizer.should_quit():
                self.logger.log_status("Encountered 10 consecutive failed strategies. Exiting due to lack of progress.")
                break

    def run_strategy(self, strategy_prompt, initial_code, current_toml):
        current_code = initial_code
        task_description = strategy_prompt
        num_attempts = 0
        strategy_start_time = time.time()

        while True:
            attempt_start_time = time.time()
            num_attempts += 1
            if num_attempts > self.MAX_PROMPTS:
                return (
                    StrategyStatus.FAILED_TOO_LONG,
                    current_code,
                    current_toml,
                    self.MAX_PROMPTS,
                    time.time() - strategy_start_time,
                )
            self.logger.log_prompt(task_description)

            # Step 1: Generate new code via patch file
            step_start_time = time.time()
            with Timer("Generating code..."):
                break_loop = False
                for generation_attempt in range(1, self.MAX_GENERATION_RETRIES + 1):
                    try:
                        replacements, new_code, new_toml = generate_code(
                            task_description, current_code, current_toml, generation_attempt, self.logger
                        )
                        self.logger.log_generated_code(
                            replacements, new_code, new_toml, generation_attempt, time.time() - step_start_time
                        )
                        break
                    except Exception as e:
                        print(f"\nError: {e} (Attempt {generation_attempt}/{self.MAX_GENERATION_RETRIES})")
                        if generation_attempt == self.MAX_GENERATION_RETRIES:
                            self.logger.log_status(
                                "Max code generation retries reached. Aborting.", time.time() - step_start_time
                            )
                            analysis = generate_code_generation_failure_analysis(
                                task_description,
                                current_code,
                                self.MAX_GENERATION_RETRIES,
                                strategy_prompt,
                            )
                            task_description = analysis
                            self.logger.log_status(f"Attempt took {time.time() - attempt_start_time:.2f}s")
                            break_loop = True
                            break

                if break_loop:
                    continue

            current_code = new_code
            with open(CODE_PATH, "w", encoding="utf-8") as f:
                f.write(new_code)

            # Step 2: Compile the code
            step_start_time = time.time()
            with Timer("Building..."):
                process = subprocess.run(BUILD_CMD, shell=True, capture_output=True, text=True)
            build_output = f"[Return code: {process.returncode}]\n {process.stderr}"
            self.logger.log_verbose(f"Build output:\n{build_output}")

            if process.returncode == 0 and process.stderr == "":
                self.logger.log_status("Compilation ✅", time.time() - step_start_time)
            else:
                with Timer("Analyzing compilation..."):
                    analysis = generate_build_analysis(task_description, current_code, build_output, strategy_prompt)

                if analysis.lower().startswith("good"):
                    self.logger.log_status("Compilation ✅", time.time() - step_start_time)
                elif analysis.lower().startswith("bad: "):
                    self.logger.log_status("Compilation ❌", time.time() - step_start_time)
                    task_description = analysis[5:]
                    self.logger.log_status(f"Attempt took {time.time() - attempt_start_time:.2f}s")
                    continue
                elif analysis.lower().startswith("stop: "):
                    self.logger.log_status("Compilation ❌ (build command error)", time.time() - step_start_time)
                    self.logger.log_status(f"Build command error: {analysis[6:]}")
                    exit(1)
                else:
                    self.logger.log_status("Analysis unsuccessful, retrying...", time.time() - step_start_time)
                    self.logger.log_status(f"Attempt took {time.time() - attempt_start_time:.2f}s")
                    continue

            # Step 3: Run a testing script to check if the code works
            step_start_time = time.time()
            with Timer("Running test script..."):
                run_output = run_command_with_timeout(TEST_CMD, TEST_TIMEOUT, TEST_EXPECTED_OUTPUT)

            if TEST_EXPECTED_OUTPUT in run_output:
                self.logger.log_status("Test script ✅", time.time() - step_start_time)
            else:
                self.logger.log_status("Test script ❌", time.time() - step_start_time)
                self.logger.log_status(f"Expected output: {TEST_EXPECTED_OUTPUT}")
                self.logger.log_status(f"Output: {run_output}")
                step_start_time = time.time()
                with Timer("Analyzing test script..."):
                    analysis = generate_test_analysis(
                        task_description,
                        current_code,
                        new_code,
                        f"The excpected output was:\n{TEST_EXPECTED_OUTPUT}\nThe output from running the program was:\n{run_output}",
                        strategy_prompt,
                    )
                    task_description = analysis
                self.logger.log_status("Generated new prompt", time.time() - step_start_time)
                self.logger.log_status(f"Attempt took {time.time() - attempt_start_time:.2f}s")
                continue

            # Step 4: Compare lines of unsafe code
            step_start_time = time.time()
            num_old_unsafe_lines, _ = self.current_unsafe_lines
            num_new_unsafe_lines, _ = count_unsafe(new_code)
            self.logger.log_status(
                f"Result: {num_old_unsafe_lines} unsafe lines -> {num_new_unsafe_lines} unsafe lines"
            )
            if num_old_unsafe_lines <= num_new_unsafe_lines:
                self.logger.log_status("Code safety improved ❌")
                with Timer("Analyzing why new code is not safer..."):
                    analysis = generate_code_safety_analysis(
                        task_description,
                        initial_code,
                        new_code,
                        num_old_unsafe_lines,
                        num_new_unsafe_lines,
                        strategy_prompt,
                    )
                self.logger.log_status("Analysis complete", time.time() - step_start_time)
                if analysis.lower().startswith("good: "):
                    self.logger.log_status("Strategy can still be used. Trying with new prompt.")
                    task_description = analysis[6:]
                    self.logger.log_status(f"Attempt took {time.time() - attempt_start_time:.2f}s")
                    continue
                else:
                    self.logger.log_status(
                        f"\nStrategy cannot be used to make code safer for the following reason: {analysis[5:]}",
                    )
                    if num_old_unsafe_lines > num_new_unsafe_lines:
                        return (
                            StrategyStatus.CODE_SAFETY_DETERIORATED,
                            new_code,
                            new_toml,
                            num_attempts,
                            time.time() - strategy_start_time,
                        )
                    else:
                        return (
                            StrategyStatus.CODE_SAFETY_UNCHANGED,
                            new_code,
                            new_toml,
                            num_attempts,
                            time.time() - strategy_start_time,
                        )
            else:
                self.logger.log_status("Code safety improved ✅")
                self.current_unsafe_lines = num_new_unsafe_lines
                return (
                    StrategyStatus.SUCCESS,
                    new_code,
                    new_toml,
                    num_attempts,
                    time.time() - strategy_start_time,
                )


if __name__ == "__main__":
    oxidizer = Oxidizer()
    try:
        oxidizer.run()
    except KeyboardInterrupt:
        print("\nExiting program via keyboard interrupt.")
    except Exception as e:
        print("\nProgram crashed with exception:")
        traceback.print_exc()
