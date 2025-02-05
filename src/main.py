import os

from utils.openai import generate_code

# input prompt and original code, generate new code
# put the code into the file location and build it, capture the output
# evaluate the output, return either "good" and end or "bad: new prompt" and loop to beginning

def main():
    task_description = "Put a divide by zero somewhere in the code."
    code_path = "temp.rs"
    new_code_path = os.path.splitext(code_path)[0] + "_temp.rs"

    with open(code_path, "r", encoding="utf-8") as f:
        current_code = f.read()
    # update_system_prompt(task_description)

    # Main loop:
    # 1. Generate new code given the prompt
    # 2. If it compiles, you're done. Otherwise, generate new prompt and go back to 1
    while True:
        print("\nGenerating code...")
        new_code = generate_code(task_description, current_code)
        with open(new_code_path, "w", encoding="utf-8") as f:
            f.write(new_code)
        break


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nProgram interrupted by user. Exiting CODA.")
        exit(0)
