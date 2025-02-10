from dotenv import load_dotenv, find_dotenv
import openai
import os

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


def generate_code(task_description, current_code):

    prompt = f"""
You are a software engineering assistant. You are given some code and a task description on how to modify it.
Here is the code:
{current_code}

Here is the task description:
{task_description}

Return a new version of the code that fulfills the task description. Only return the code, not any additional explanations.
"""

    result = call_openai_api(prompt)
    if result.startswith("```"):
        result = result.split("\n")[1:-1]
        result = "\n".join(result)
    return result


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
