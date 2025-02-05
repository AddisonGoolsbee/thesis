import os
import subprocess

from utils.openai import generate_code, generate_analysis

# input prompt and original code, generate new code
# put the code into the file location and build it, capture the output
# evaluate the output, return either "good" and end or "bad: new prompt" and loop to beginning


def main():
    task_description = "Put an unused variable somewhere without an underline so it causes a warning. If you reanalyze this prompt (ignore for now), treat this warning as bad"
    code_path = "temp.rs"
    new_code_path = os.path.splitext(code_path)[0] + "_temp.rs"
    build_cmd = f"rustc {new_code_path} -o prog"

    with open(code_path, "r", encoding="utf-8") as f:
        current_code = f.read()
    # update_system_prompt(task_description)

    # Main loop:
    # 1. Generate new code given the prompt
    # 2. If it compiles, you're done. Otherwise, generate new prompt and go back to 1
    while True:
        print(f"Generating code using the following prompt: {task_description}")
        new_code = generate_code(task_description, current_code)
        with open(new_code_path, "w", encoding="utf-8") as f:
            f.write(new_code)
        result = subprocess.run(build_cmd, shell=True, capture_output=True, text=True)
        build_output = result.stderr

        print("Analyzing compilation...")
        while True:
            analysis = generate_analysis(task_description, new_code, build_output)
            if analysis.lower().startswith("good"):
                print("Compilation ✅")
                return
            elif analysis.lower().startswith("bad: "):
                print("Compilation ❌")
                task_description = analysis[5:]
                break
            else:
                print("Analysis unsuccessful, retrying...")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nExiting program.")
        exit(0)
