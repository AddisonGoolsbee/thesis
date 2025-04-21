from dotenv import load_dotenv
import openai
import os
from pydantic import BaseModel

from utils.misc import apply_changes

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")
client = openai.OpenAI()


def call_openai_api(prompt):
    completion = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "user", "content": prompt},
        ],
        stream=False,
    )

    return completion.choices[0].message.content


class Replacement(BaseModel):
    original: str
    new: str


class ReplacementList(BaseModel):
    replacements: list[Replacement]


def call_openai_api_for_patch(prompt):
    completion = client.beta.chat.completions.parse(
        model="gpt-4o",
        messages=[
            {"role": "user", "content": prompt},
        ],
        response_format=ReplacementList,
    )

    return completion.choices[0].message.content

def get_task_modification_requirements(original_task_description):
    requirements = f"""For the new task description, you must follow these guidelines:
- You must preserve the core strategy of the original task description: <{original_task_description}>, with the ultimate goal of modifying the code to reduce the number of unsafe lines
- This new task description should work where the current one (and the original one) did not
- Try to keep the new task description as isolated as possible, so it only affects the code in a few specific areas (if possible)
- Do not explain any reasoning. Just return the new task description.
"""
    return requirements

def generate_code(task_description, current_code):

    prompt = f"""
You are a software engineering assistant. You are given some code and a task description on how to modify it.
{current_code}

Here is the task description:
{task_description}

Instead of providing new code, provide a json object that represent replacements made to the code. "original" is the original string (must be long enough to be unique in the code), and "new" is the new string which replaces the original.

Here is an example of a set of replacements:

{{
    "replacements": [
        {{
            "original": "def simple():\n    return a + b",
            "new": "def simple():\n    return a - b"
        }},
        {{
            "original": "impl RxQueueRegisters for E1000RxQueueRegisters {{\n    fn set_rdbal(&mut self, value: u32) {{\n        self.0.rx_regs.rdbal.write(value);",
            "new": "impl RxQueueRegisters for E1000RxQueueRegisters {{\n    fn set_rdbal(&mut self, value: u32) {{\n        self.0.rx_regs.rdbal.write(value); \n    debug!(\"Wrote {{}}\", value);",
        }},
        {{
            "original": "use std::collections::HashMap;\nuse std::collections::BTreeMap;",
            "new": "use std::collections::HashMap;",
        }},
    ]
}}

Ensure:
- There are several unique lines of context in each replacement, so an exact string match can easily be found.
- The replacements should be in the order they appear in the code.
- Newlines should be preserved.
- Make sure that open/closing delimiters are matched, and you don't leave any dangling delimiters.

Only return the list of replacements, do not add comments or labels
"""
    result = call_openai_api_for_patch(prompt)
    new_code = apply_changes(current_code, result)
    return new_code, result


def generate_code_generation_failure_analysis(task_description, current_code, num_attempts, original_task_description):
    prompt = f"""
You are a software engineering assistant. You were given some code and a task description on how to modify it.

Here was the task description:
{task_description}

Here was the code you generated:
{current_code}

Using this information, you tried {num_attempts} times to generate code in a patch format that would modify the original code to generate code that would produce the expected output. All attempts failed.
Based on this information, modify the task description to make it easier to generate code that will produce the expected output, maintaining the original strategy.
{get_task_modification_requirements(original_task_description)}
"""

    return call_openai_api(prompt)


def generate_build_analysis(task_description, new_code, build_output, original_task_description, original_code):

    prompt = f"""
You are a software engineering assistant. You were given some code and a task description on how to modify it.

Here was the task description:
{task_description}

Here was the original code:
{original_code}

Here was the new code you generated:
{new_code}

The stderr from compiling the code was:
{build_output}

Based on this information, do you think the modification worked without introducing any significant NEW issues, including easy-to-fix warnings, AND do you think it successfully compiled?
If the program didn't compile successfully due to something like a bad build command, but it wasn't because of your modification, return "stop: " plus a message to the user on what wen't wrong.
If you think it DID work, return "good" and your explanation. 
If you think it didn't work, return "bad: " plus a new task description that will replace the old one, which will then be applied to the original code (the new code will be discarded).
{get_task_modification_requirements(original_task_description)}
"""

    return call_openai_api(prompt)


def generate_test_analysis(task_description, original_code, new_code, run_output, original_task_description):

    prompt = f"""
You are a software engineering assistant. You were given some code and a task description on how to modify it.

Here was the task description:
{task_description}

Here was the original code:
{original_code}

Here was the code you generated:
{new_code}

The program was compiled successfully, however the output from running the program did not include the expected output.
{run_output}

Based on this information, make a new, better task description that will modify the original code to generate code that will produce the expected output.
{get_task_modification_requirements(original_task_description)}
"""

    return call_openai_api(prompt)


def generate_code_safety_analysis(
    task_description, original_code, new_code, num_old_unsafe_lines, num_new_unsafe_lines, original_task_description
):

    prompt = f"""
You are a software engineering assistant. You were given some code and a task description on how to modify it to make it safer.

Here was the task description:
{task_description}

Here was the original code:
{original_code}

Here was the code you generated:
{new_code}

The program compiled and ran successfully, preserving the original functionality.

However, {"the new code has the same number of unsafe lines as the original code" if num_old_unsafe_lines == num_new_unsafe_lines else "the new code has more unsafe lines than the original code"}, so your modification failed. ({num_new_unsafe_lines} new vs {num_old_unsafe_lines} old unsafe lines)

If you must preserve the same rough strategy as the original task description, do you think that it is possible to update the task description to actually make the code safer (less lines of unsafe code)? The original task description's core strategy must be preserved, only the fine details should be changed.
If you don't think it is possible to make the code safer using a similar strategy, return "bad: " plus your reasoning. Reasoning should be concise.
If you think it is possible, return "good: " plus a new task description that will modify the original code to generate code that will produce the expected output. Do not explain any reasoning.
{get_task_modification_requirements(original_task_description)}
"""

    return call_openai_api(prompt)
