import os
import re
import json
import shutil

from config import CODE_PATH


class Logger:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Logger, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "initialized"):
            return
        self.initialized = True

        self.initial_path = CODE_PATH
        with open(self.initial_path, "r", encoding="utf-8") as f:
            self.initial_code = f.read()

        self.logger_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "log"))
        self.logger_original_path = os.path.join(self.logger_path, "original.rs")

        create_log = False
        if os.path.exists(self.logger_path):
            if (
                not os.path.exists(self.logger_original_path)
                or open(self.logger_original_path, "r", encoding="utf-8").read() != self.initial_code
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

        run_dirs = [d for d in os.listdir(self.logger_path) if re.fullmatch(r"run\d{3}", d)]
        next_run = f"{(max(map(lambda d: int(d[3:]), run_dirs), default=0) + 1):03d}"
        self.run_dir = os.path.join(self.logger_path, f"run{next_run}")
        os.makedirs(self.run_dir)

        self.goal_num = "000"

    def begin_goal(self, prompt):
        self.goal_num = f"{(int(self.goal_num) + 1):03d}"
        self.goal_path = os.path.join(self.run_dir, f"goal{self.goal_num}")
        os.makedirs(self.goal_path)

        self.prompt_num = "001"

        with open(os.path.join(self.goal_path, "prompts.txt"), "w", encoding="utf-8") as f:
            f.write(f"Prompt {int(self.prompt_num)}\n{prompt}\n")
        print("Prompt: ", prompt)

    def log_generated_code(self, replacements, new_code, attempt_num):
        with open(os.path.join(self.goal_path, f"replacements{self.prompt_num}.json"), "w") as f:
            json.dump(json.loads(replacements), f, indent=4)
        with open(os.path.join(self.goal_path, f"code{self.prompt_num}.rs"), "w") as f:
            f.write(new_code)
        self.prompt_num = f"{(int(self.prompt_num) + 1):03d}"

        with open(os.path.join(self.goal_path, "prompts.txt"), "a", encoding="utf-8") as f:
            f.write(f"Successful generation after {attempt_num} attempt(s)\n")

    def log_status(self, status):
        with open(os.path.join(self.goal_path, "prompts.txt"), "a", encoding="utf-8") as f:
            f.write(status + "\n")
        print(status)
