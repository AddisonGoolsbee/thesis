import os
import re

class Logger:
    _instance = None

    def __new__(cls, initial_code=None):
        if cls._instance is None:
            cls._instance = super(Logger, cls).__new__(cls)
        return cls._instance

    def __init__(self, initial_code=None):
        if hasattr(self, "initialized"):
            return
        self.initialized = True
        self.logger_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "log")
        if not os.path.exists(self.logger_path):
            os.makedirs(self.logger_path)

        file_path = os.path.join(self.logger_path, "original.rs")
        if not os.path.exists(file_path):
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(initial_code)

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
            f.write(f"Prompt {int(self.prompt_num)}\n{prompt}")
        print("Prompt: ", prompt)

    def log_generated_code(self, replacements, new_code):
        with open(os.path.join(self.goal_path, f"replacements{self.prompt_num}.json"), "w") as f:
            f.write(replacements)
        with open(os.path.join(self.goal_path, f"code{self.prompt_num}.rs"), "w") as f:
            f.write(new_code)
        self.prompt_num = f"{(int(self.prompt_num) + 1):03d}"
