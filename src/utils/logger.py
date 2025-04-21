import atexit
import os
import re
import json
import shutil
import time

from config import CODE_PATH, CARGO_PATH


class Logger:
    def __init__(self):
        self.initial_path = CODE_PATH
        self.initial_toml_path = CARGO_PATH
        self.start_time = time.time()
        self.best_unsafe_lines = None
        with open(self.initial_path, "r", encoding="utf-8") as f:
            self.initial_code = f.read()
        if CARGO_PATH:
            with open(self.initial_toml_path, "r", encoding="utf-8") as f:
                self.initial_toml = f.read()
        else:
            self.initial_toml = None

        self.logger_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "log"))
        self.logger_original_path = os.path.join(self.logger_path, "original.rs")
        self.logger_original_toml_path = os.path.join(self.logger_path, "original.toml")

        create_log = False
        if os.path.exists(self.logger_path):
            if (
                not os.path.exists(self.logger_original_path)
                or open(self.logger_original_path, "r", encoding="utf-8").read() != self.initial_code
                or (CARGO_PATH and (not os.path.exists(self.logger_original_toml_path)
                or open(self.logger_original_toml_path, "r", encoding="utf-8").read() != self.initial_toml))
            ):
                print("log/original.rs has changed, removing old log folder")
                shutil.rmtree(self.logger_path)
                create_log = True
        else:
            print("No log folder found")
            create_log = True

        if create_log:
            print("Creating new log folder")
            os.makedirs(self.logger_path)
            with open(self.logger_original_path, "w", encoding="utf-8") as f:
                f.write(self.initial_code)
            if CARGO_PATH:
                with open(self.logger_original_toml_path, "w", encoding="utf-8") as f:
                    f.write(self.initial_toml)

        run_dirs = [d for d in os.listdir(self.logger_path) if re.fullmatch(r"run\d{3}", d)]
        next_run = f"{(max(map(lambda d: int(d[3:]), run_dirs), default=0) + 1):03d}"
        self.run_dir = os.path.join(self.logger_path, f"run{next_run}")
        print("Logs for this run can be found in ", self.run_dir)
        os.makedirs(self.run_dir)
        self.strategy_num = "000"

        atexit.register(self.cleanup)

    def cleanup(self):
        with open(os.path.join(self.run_dir, "summary.log"), "a", encoding="utf-8") as f:
            f.write(f"\nResult: {self.initial_unsafe_lines} unsafe lines -> {self.best_unsafe_lines if self.best_unsafe_lines else self.initial_unsafe_lines} unsafe lines in {int((time.time() - self.start_time) / 60)}:{int((time.time() - self.start_time) % 60):02d}\n")

        shutil.copy(self.logger_original_path, self.initial_path)
        if CARGO_PATH:
            shutil.copy(self.logger_original_toml_path, self.initial_toml_path)
            print("Reverted Cargo.toml to original state.")
        print("Reverted code to original state.")
        print("Logs saved to ", self.run_dir)
        if os.path.exists(os.path.join(self.run_dir, "best.rs")):
            print("Best generated code saved to ", os.path.join(self.run_dir, "best.rs"))
        if CARGO_PATH:
            if os.path.exists(os.path.join(self.run_dir, "best.toml")):
                print("Best generated Cargo.toml saved to ", os.path.join(self.run_dir, "best.toml"))

    def begin_run(self, initial_unsafe_lines):
        self.initial_unsafe_lines = initial_unsafe_lines
        with open(os.path.join(self.run_dir, "summary.log"), "a", encoding="utf-8") as f:
            f.write(f"Initial unsafe lines: {initial_unsafe_lines}\n")

    def log_strategy(self, prompt):
        self.most_recent_prompt = prompt
        self.strategy_num = f"{(int(self.strategy_num) + 1):03d}"
        self.strategy_dir = os.path.join(self.run_dir, f"strategy{self.strategy_num}")
        os.makedirs(self.strategy_dir)
        self.prompt_num = "000"

        with open(os.path.join(self.run_dir, "summary.log"), "a", encoding="utf-8") as f:
            f.write(("\n" if int(self.strategy_num) > 1 else "") + f"Strategy {int(self.strategy_num)}: {prompt}\n")

    def log_strategy_result(self, result, unsafe_lines):
        self.best_unsafe_lines = unsafe_lines

        with open(os.path.join(self.strategy_dir, "summary.log"), "a", encoding="utf-8") as f:
            f.write(
                f"\n{result}\n"
            )
        print(result)

        log_message = f"Final prompt: {self.most_recent_prompt}\n{result}\n{unsafe_lines} unsafe lines remaining\n"
        with open(os.path.join(self.run_dir, "summary.log"), "a", encoding="utf-8") as f:
            f.write(log_message + "\n")
        self.log_verbose(log_message)

    def log_prompt(self, prompt):
        self.most_recent_prompt = prompt
        self.prompt_num = f"{(int(self.prompt_num) + 1):03d}"

        log_message = f"Prompt {int(self.prompt_num)}: {prompt}"
        with open(os.path.join(self.strategy_dir, "summary.log"), "a", encoding="utf-8") as f:
            f.write(("\n" if int(self.prompt_num) > 1 else "") + log_message + "\n")
        print(log_message)
        self.log_verbose(log_message)

    def log_generated_code(self, replacements, new_code, new_toml, attempt_num, time_taken):
        with open(os.path.join(self.strategy_dir, f"replacements{self.prompt_num}.json"), "w") as f:
            json.dump(json.loads(replacements), f, indent=4)
        with open(os.path.join(self.strategy_dir, f"code{self.prompt_num}.rs"), "w") as f:
            f.write(new_code)
        if CARGO_PATH:
            with open(os.path.join(self.strategy_dir, f"toml{self.prompt_num}.toml"), "w") as f:
                f.write(new_toml)

        with open(os.path.join(self.strategy_dir, "summary.log"), "a", encoding="utf-8") as f:
            log_message = f"Successful generation in {attempt_num} attempt{'s' if attempt_num != 1 else ''} ({time_taken:.2f}s)"
            f.write(log_message + "\n")
            self.log_verbose(log_message)
    
    def log_generation_attempt(self, result, generation_attempt):
        generation_attempts_dir = os.path.join(self.strategy_dir, "generation_attempts")
        if not os.path.exists(generation_attempts_dir):
            os.makedirs(generation_attempts_dir)

        with open(os.path.join(generation_attempts_dir, f"{self.prompt_num}-{generation_attempt}.json"), "w") as f:
            json.dump(json.loads(result), f, indent=4)

    def log_status(self, status, time_taken=None):
        log_message = status + (f" ({time_taken:.2f}s)" if time_taken else "")

        with open(os.path.join(self.strategy_dir, "summary.log"), "a", encoding="utf-8") as f:
            f.write(log_message + "\n")
        print(log_message)
        self.log_verbose(log_message)

    def log_verbose(self, status):
        with open(os.path.join(self.strategy_dir, "verbose_summary.log"), "a", encoding="utf-8") as f:
            f.write(status + "\n")

    def update_best_code(self, new_code, new_toml):
        with open(os.path.join(self.run_dir, "best.rs"), "w", encoding="utf-8") as f:
            f.write(new_code)
        if CARGO_PATH:
            with open(os.path.join(self.run_dir, "best.toml"), "w", encoding="utf-8") as f:
                f.write(new_toml)
        print("Updated best code")

    def log_to_run(self, message):
        with open(os.path.join(self.run_dir, "summary.log"), "a", encoding="utf-8") as f:
            f.write(message + "\n")
