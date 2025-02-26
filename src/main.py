import shutil
import subprocess

from utils.openai import generate_code, generate_analysis
from utils.io import Timer
from utils.logger import Logger


def main():
    task_description = "Reorder a few lines of code in a way that it won't affect the code's functionality. And add a funny comment to the top"
    # code_path = "temp.rs"
    code_path = "/Users/addisongoolsbee/Desktop/Theseus/kernel/e1000/src/lib.rs"
    # build_cmd = f"rustc {code_path} -o prog"
    build_cmd = f"gmake iso -C /Users/addisongoolsbee/Desktop/Theseus/ net=user"

    with open(code_path, "r", encoding="utf-8") as f:
        current_code = f.read()
        new_code = current_code

    logger = Logger()

    # Main loop:
    # 1. Generate new code given the prompt
    # 2. If it compiles, you're done. Otherwise, generate new prompt and go back to 1
    logger.begin_goal(task_description)
    MAX_RETRIES = 5
    while True:
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

        with open(code_path, "w", encoding="utf-8") as f:
            f.write(new_code)

        with Timer("Building......"):
            result = subprocess.run(build_cmd, shell=True, capture_output=True, text=True)
        build_output = f"[Return code: {result.returncode}]\n {result.stderr}"

        while True:
            with Timer("Analyzing compilation..."):
                analysis = generate_analysis(task_description, new_code, build_output)
            if analysis.lower().startswith("good"):
                logger.log_status("Compilation ✅")
                return
            elif analysis.lower().startswith("bad: "):
                logger.log_status("Compilation ❌")
                task_description = analysis[5:]
                break
            elif analysis.lower().startswith("stop: "):
                logger.log_status("Compilation ❌")
                logger.log_status("Build command error: ", analysis[6:])
                return
            else:
                logger.log_status("Analysis unsuccessful, retrying...")


if __name__ == "__main__":
    try:
        main()
        raise KeyboardInterrupt
    except KeyboardInterrupt:
        print("\nExiting program.")
        logger = Logger()
        shutil.copy(logger.original_path, logger.initial_path)
        print('Reverted code to original state.')
        print('Logs saved to:', logger.run_dir)
        exit(0)
