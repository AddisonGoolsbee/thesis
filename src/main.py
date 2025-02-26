import subprocess

from utils.openai import generate_code, generate_analysis
from utils.io import Timer


def main():
    task_description = "Reorder a few lines of code in a way that it won't affect the code's functionality."
    # code_path = "temp.rs"
    code_path = "/Users/addisongoolsbee/Desktop/Theseus/kernel/e1000/src/lib.rs"
    original_code_path = f"original.rs"
    # build_cmd = f"rustc {code_path} -o prog"
    build_cmd = f"gmake iso -C /Users/addisongoolsbee/Desktop/Theseus/ net=user"

    with open(code_path, "r", encoding="utf-8") as f:
        current_code = f.read()
        new_code = current_code

    with open(original_code_path, "w", encoding="utf-8") as f:
        f.write(current_code)

    # Main loop:
    # 1. Generate new code given the prompt
    # 2. If it compiles, you're done. Otherwise, generate new prompt and go back to 1
    MAX_RETRIES = 5
    while True:
        print("Prompt: ", task_description)
        with Timer("Generating..."):
            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    new_code = generate_code(task_description, current_code)
                    break
                except Exception as e:
                    print(f"\nError: {e} (Attempt {attempt}/{MAX_RETRIES})")
                    if attempt == MAX_RETRIES:
                        print("Max retries reached. Aborting.")
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
                print("Compilation ✅")
                return
            elif analysis.lower().startswith("bad: "):
                print("Compilation ❌")
                task_description = analysis[5:]
                break
            elif analysis.lower().startswith("stop: "):
                print("Compilation ❌")
                print("Build command error: ", analysis[6:])
                return
            else:
                print("Analysis unsuccessful, retrying...")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nExiting program.")
        exit(0)
