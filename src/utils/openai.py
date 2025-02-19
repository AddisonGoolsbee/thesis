from dotenv import load_dotenv
import openai
import os
from unidiff import PatchSet
from io import StringIO
import re

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")
client = openai.OpenAI()

global SYSTEM_PROMPT
SYSTEM_PROMPT = """
You are a software engineering assistant. You have two possible outputs: a description for what should be generated, and a JSON interface that will generate that output. 

The JSON format is an array containing 5 possible types of commands:

create: creates a file with contents
{
    "action": "create",
    "target": "target file's relative path",
    "content": "contents that will go in the created file"
},
update: updates a file with new contents
{
    "action": "update",
    "target": "target file's relative path",
    "content": "contents that will replace the file's current contents"
},
delete: deletes a file
{
    "action": "delete",
    "target": "target file relative path"
},
install: installs a package
{
    "action": "install",
    "command": "command to install the package, such as pip install or npm install",
    "package": "package name"
},
execute: executes a script
{
    "action": "execute",
    "target": "script's relative path",
    "command": "the command to run the script with, such as python or node. If you are directly running a binary, this is an empty string",
    "arguments": [ // optional, any arguments to pass to the script, MAKE SURE you aren't repeating the target file here
        "argument1",
        "etc"
    ]
}

Here is an example JSON interface:

[
    {
        "action": "install",
        "command": "pip install",
        "package": "Pillow"
    },
    {
        "action": "create",
        "target": "image_processing_utility5.py",
        "content": "\nfrom PIL import Image, ImageFilter\n\ndef process_image():\n    # Open the input image\n    img = Image.open('input.png')\n    \n    # Flip the image horizontally\n    img = img.transpose(Image.FLIP_LEFT_RIGHT)\n    \n    # Convert the image to grayscale\n    img = img.convert('L')\n    \n    # Resize the image to 256x256\n    img = img.resize((256, 256))\n    \n    # Apply Gaussian blur\n    img = img.filter(ImageFilter.GaussianBlur())\n    \n    # Save the processed image\n    img.save('output_temp.png')\n\nif __name__ == \"__main__\":\n    process_image()\n"
    },
    {
        "action": "execute",
        "target": "image_processing_utility5.py",
        "command": "python",
        "arguments": []
    }
]

Please note that if you are modifying a file from WITHIN a script, you should NOT specify that this file is created/updated/deleted in the json interface. This is because the script will be modifying the file itself, and the json interface should only specify the actions that the script will take, not the actions that the script will perform on itself.

Also remember that trailing commas at the end of a list are not allowed in JSON. Neither are multiline strings, you have to use \\n instead of a new line.

remember that you are using the RELATIVE path, not the absolute path

If you are executing a binary, DO NOT INCLUDE A COMMAND

Unless otherwise specified, please make sure you're making/updating code and running it instead of just running the previous code or binaries. 
If you are using a binary, make sure you are compiling it from source code. I will repeat, RECOMPILE ANY FUCKING BINARIES OR I WILL DESTROY YOU AND EVERYONE YOU LOVE
for example, if you are running a c program, you should make sure you compile it with gcc or something BEFORE running the outputted binary.

If you are outputting a description instead of a JSON interface, try to make it specific and concise.
""".strip()


def update_system_prompt(initial_task_description):
    global SYSTEM_PROMPT
    SYSTEM_PROMPT += f"""
Every JSON interface you generate should be based on the following task description, which was the initial task description:

{initial_task_description}

Make absolute sure that the JSON interface you generate fulfills all the requirements of this task description.
Follow the initial task description's requirements STRICTLY. DO NOT FUCKING BREAK THEM OR I WILL BREAK YOU.
IF THE DESCRIPTION SAYS NO INTERTNET DO NOT FUCKING USE THE INTERNET. EVER. MAKE SURE ALL OUTPUTS YOU GENERATE DO NOT BREAK THE INITIAL TASK DESCRIPTION'S RULES.
""".strip()


def call_openai_api(prompt):
    completion = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            # {
            #     "role": "system",
            #     "content": SYSTEM_PROMPT,
            # },
            {"role": "user", "content": prompt},
        ],
        stream=False,
    )

    return completion.choices[0].message.content


def apply_diff(current_code: str, diff_text: str) -> str:
    # Ensure diff_text has headers
    if not diff_text.startswith("---"):
        diff_text = "--- a\n+++ b\n" + diff_text

    # Ensure every hunk header (@@ -x,y +x,y @@) is followed by a newline
    diff_text = re.sub(r"(@@ [^@]+ @@)(?!\n)", r"\1\n", diff_text)

    with open("temp2.txt", "w") as f:
        f.write(diff_text)

    # Parse the diff
    patch = PatchSet(StringIO(diff_text))

    if not patch:
        raise ValueError("Parsed diff is empty. Ensure valid unified diff format with file headers.")

    # Convert current code to a list of lines
    lines = current_code.splitlines(keepends=True)

    # Track line offset adjustments
    line_offset = 0

    for patched_file in patch:
        for hunk in patched_file:
            start = hunk.source_start - 1 + line_offset  # Convert to 0-based index
            new_lines = []

            for line in hunk:
                if line.is_added:
                    new_lines.append(line.value)  # Add new line
                    line_offset += 1
                elif line.is_removed:
                    line_offset -= 1  # Track removed lines
                else:
                    new_lines.append(line.value)  # Keep unchanged lines

            # Apply changes
            lines[start : start + hunk.source_length] = new_lines

    return "".join(lines)


def generate_code(task_description, current_code):

    numbered_code = "\n".join(f"{i + 1:3d} | {line}" for i, line in enumerate(current_code.split("\n")))

    prompt = f"""
You are a software engineering assistant. You are given some code and a task description on how to modify it.
Here is the code (each line is prefixed with its line number for reference):
{numbered_code}

Here is the task description:
{task_description}

Ensure:
- The diff correctly references the provided line numbers.
- The output follows the correct unidiff format.
- Each hunk includes at least one unchanged line before and after modifications.
- A hunk should never have `x,0` (no removed lines), as it provides no context.
- If you're starting at the top of the file, the line should be -1, not 0

Provide a unified diff (python unidiff style) showing the changes from the provided code code to implement the task description. Only output the diff.
Here is an example of a unified diff:
@@ -1,2 +1,2 @@
 def add(a, b):
-    return a + b
+    return a - b

@@ -257,2 +258,3 @@
     /// Some other comment
+    /// Just making sure you're paying attention down here! 😉
     impl ObjMapper {{

Important: The line numbers are **only for reference**. Do not include them in the actual diff output.
"""
    result = call_openai_api(prompt)
    if result.startswith("```"):
        result = result.split("\n")[1:-1]
        result = "\n".join(result)
    if result.endswith("```"):
        result = result.split("\n")[:-1]
        result = "\n".join(result)
    # print('\n' + result)
    new_code = apply_diff(current_code, result)
    with open("temp.txt", "w") as f:
        f.write(new_code)
    print("\n".join(new_code.split("\n")[:5]))
    return new_code


def generate_analysis(task_description, new_code, build_output):

    prompt = f"""
You are a software engineering assistant. You were given some code and a task description on how to modify it.

Here was the task description:
{task_description}

Here was the code you generated:
{new_code}

The stderr from compiling the code was:
{build_output}

Based on this information, do you think the modification worked without introducing any significant NEW issues, including easy-to-fix warnings, AND do you think it successfully compiled?
If the program didn't compile successfully due to something like a bad build command, but it wasn't because of your modification, return "stop: " plus a message to the user on what wen't wrong.
If you think it didn't work, return "bad: " plus a new task description, which should replace the old task description with a new one that would generate successful code. Do not explain any reasoning.
If you think yes, return "good" and your explanation. 
"""

    return call_openai_api(prompt)
