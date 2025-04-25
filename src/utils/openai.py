import json
from dotenv import load_dotenv
import openai
import os
from pydantic import BaseModel

from utils.misc import apply_changes
from config import CARGO_PATH

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

class ReplacementListWithCargo(BaseModel):
    replacements: list[Replacement]
    cargo_replacements: list[Replacement]


def call_openai_api_for_patch(prompt):
    completion = client.beta.chat.completions.parse(
        model="gpt-4o",
        messages=[
            {"role": "user", "content": prompt},
        ],
        response_format=(ReplacementListWithCargo if CARGO_PATH else ReplacementList),
    )

    return completion.choices[0].message.content

def get_task_modification_requirements(original_task_description):
    requirements = f"""For the new task description, you must follow these guidelines:
- You must preserve the core strategy of the original task description: <{original_task_description}>, with the ultimate goal of modifying the code to reduce the number of unsafe lines
- This new task description should work where the current one (and the original one) did not
- Try to keep the new task description as isolated as possible, so it only affects the code in a few specific areas (if possible)
- Include specific details about what to change, especially to avoid making the same problem you just made.
- Do not explain any reasoning. Just return the new task description."""
    if not CARGO_PATH:
        requirements += "\n- You are only modifying the code, so don't try anything that would require adding new packages. You can't edit the Cargo.toml file."
    return requirements

def get_build_text(task_description, original_code, replacements, build_output):
    return f"""You are a software engineering assistant. You were given some code and a task description on how to modify it.

Here was your task description:
{task_description}

Here was the original code:
{original_code}

You generated the following replacements file:
{replacements}

The output from compiling the code with the new replacements was:
{build_output}"""

def generate_code(task_description, current_code, current_toml, generation_attempt, logger, previous_generation=None, previous_output=None, strategy_prompt=None):
    cargo_pre_instructions = "\nHere is the Cargo.toml file:\n" + current_toml if current_toml else ""
    cargo_format_instructions = """    ],
    "cargo_replacements": [
        {{
            "original": "[dependencies]\nserde = \"1.0\"\nanyhow = \"1.0\"",
            "new": "[dependencies]\nserde = \"1.0\"\nanyhow = \"1.0\"\nregex = \"1.10\""
        }}
    ]"""

    if previous_generation:
        data = json.loads(previous_generation)
        pretty = json.dumps(data, indent=4)
        prompt_start = f"""{get_build_text(strategy_prompt, current_code, pretty, previous_output)}

{task_description}
"""
    else:
        prompt_start = f"""
You are a software engineering assistant. You are given some code and a task description on how to modify it.
{current_code}

Here is the task description:
{task_description}

Instead of providing new code, provide a json object that represent replacements made to the code. "original" is the original string (must be long enough to be unique in the code), and "new" is the new string which replaces the original."""
    
    prompt = f"""
{prompt_start}

{"All code replacements must be in the 'replacements' list, while any changes to the Cargo.toml file must be in the 'cargo_replacements' list." if CARGO_PATH else ""} {cargo_pre_instructions}

Here is an example of a set of replacements:

{{
    "replacements": [
        {{
           "original": "fn simple() -> i32 {{\n    a + b\n}}",
            "new": "fn simple() -> i32 {{\n    a - b\n}}",
        }},
        {{
            "original": "impl RxQueueRegisters for E1000RxQueueRegisters {{\n    fn set_rdbal(&mut self, value: u32) {{\n        self.0.rx_regs.rdbal.write(value);\n        debug!(\"Wrote {{}}\", value);\n    }}\n}}",
            "new": "impl RxQueueRegisters for E1000RxQueueRegisters {{\n    fn set_rdbal(&mut self, value: u32) {{\n        self.0.rx_regs.rdbal.write(value);\n        debug!(\"Wrote {{}}\", value);\n    }}\n}}"

        }},
        {{
            "original": "use std::collections::HashMap;\nuse std::collections::BTreeMap;",
            "new": "use std::collections::HashMap;",
        }},
    {"    ]" if not CARGO_PATH else cargo_format_instructions}
}}

Ensure:
- There are several unique lines of context in each replacement, so an exact string match can easily be found.
- The replacements should be in the order they appear in the code.
- Newlines should be preserved.
- Make absolutely sure you don't leave any dangling delimiters. Preserve the net delimiter count from the original to the new (if there's one extra {{ in original, there should be one extra {{ in new, etc.)
"""
    logger.log_verbose(f"<<<Prompt:\n{prompt}>>>{generation_attempt}")
    result = call_openai_api_for_patch(prompt)
    logger.log_generation_attempt(result, generation_attempt)
    result_json = json.loads(result)
    new_code = apply_changes(current_code, result_json["replacements"])
    if CARGO_PATH:
        new_toml = apply_changes(current_toml, result_json["cargo_replacements"])
    else:
        new_toml = None
    return result, new_code, new_toml


def generate_code_generation_failure_analysis(task_description, current_code, num_attempts, original_task_description):
    prompt = f"""
You are a software engineering assistant. You were given some code and a task description on how to modify it.

Here was your task description:
{task_description}

Here was the code you generated:
{current_code}

Using this information, you tried {num_attempts} times to generate code in a patch format that would modify the original code to generate code that would produce the expected output. All attempts failed.
Based on this information, modify the task description to make it easier to generate code that will produce the expected output, maintaining the original strategy.
{get_task_modification_requirements(original_task_description)}
"""

    return call_openai_api(prompt)


def generate_build_analysis(task_description, new_code, build_output, original_task_description, original_code, replacements):

    prompt = f"""
{get_build_text(task_description, original_code, replacements, build_output)}

Based on this information, do you think the modification worked without introducing any significant NEW issues, including easy-to-fix warnings, AND do you think it successfully compiled?
If the program didn't compile successfully due to something like a bad build command, but it wasn't because of your modification, return "stop: " plus a message to the user on what wen't wrong.
If you think it DID work, return "good" and your explanation. 
If you think it didn't work, return "bad: " plus a description explaining what went wrong, and what needs to be fixed about the replacements file. Do not return anything else such as example code. Be very specific on what needs to be fixed. Do not include placeholders.The description + what needs to be fixed should be concise (if it can be). Make sure to include the "bad: " prefix.
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
