import json
from dotenv import load_dotenv
import openai
import os
from pydantic import BaseModel

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


def apply_changes(current_code: str, changes: str) -> str:
    changes = json.loads(changes)
    for replacement in changes["replacements"]:
        if replacement["original"] not in current_code:
            raise ValueError(f"Replacement string not found in code: {replacement['original']}")
        current_code = current_code.replace(replacement["original"], replacement["new"])

    return current_code


def generate_code(task_description, current_code):

    prompt = f"""
You are a software engineering assistant. You are given some code and a task description on how to modify it.
{current_code}

Here is the task description:
{task_description}

Instead of providing new code, provide a set of tuples that represent replacements made to the code. The first value is the original string, and the second value is the new string.

Here is an example of a set of replacements:

[
    ("def simple():\n    return a + b", "def simple():\n    return a - b"),
    ("impl RxQueueRegisters for E1000RxQueueRegisters {{\n    fn set_rdbal(&mut self, value: u32) {{\n        self.0.rx_regs.rdbal.write(value); ", "impl RxQueueRegisters for E1000RxQueueRegisters {{\n    fn set_rdbal(&mut self, value: u32) {{\n        self.0.rx_regs.rdbal.write(value); \n    debug!("Wrote {{}}, value);"),
    ("use std::collections::HashMap;\nuse std::collections::BTreeMap;", "use std::collections::HashMap;"), // this would remove the BTreeMap import
]

Ensure:
- There should be several lines of context that do not get changed in each replacement tuple, so an exact string match can easily be found.
- The replacements should be in the order they appear in the code.

Only return the list of replacements, do not add comments or labels
"""
    result = call_openai_api_for_patch(prompt)
    new_code = apply_changes(current_code, result)
    return new_code, result


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
