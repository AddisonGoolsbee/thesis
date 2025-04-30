# Reoxidizer: An Autonomous Rust Idiomizer using Recursive LLMs

This recursive coding agent was created to be modular, but was specifically tuned for the e1000 driver of [TheseusOS](https://github.com/theseus-os/Theseus)

## Setup

_Note that this has only been tested on Mac (Apple Silicon)_

- Set up a python virtual environment:

  - `python3 -m venv .venv`
  - `source .venv/bin/activate`
  - `pip install -r requirements.txt`

- Make a `.env` file in the root directory with the environment variable `OPENAI_API_KEY` set to your OpenAI API key
- Find a rust file (it can be standalone or it can be part of a larger project). Go to `main.py` and replace the following constants:
  - `CODE_PATH`: path to the rust file
  - `BUILD_CMD`: command to compile (but not run) the file/project
  - `BASIC_TEST_CMD`: command to run the compiled program
  - `BASIC_TEST_EXPECTED_OUTPUT`: a line or several that you expect to be printed to stdout upon running the compiled program (the 'basic unit test')
  - `BASIC_TEST_TIMEOUT`: the time in seconds to wait before killing the compiled program if the expected output is not printed

### Running with the Theseus e1000

- If you want to run this on the e1000, you'll need to add the following line to the Theseus code base: go to `kernel/e1000/src/lib.rs`, and right after the `let interrupt_num` block, around line 162, add the line `rust e1000_pci_dev.pci_enable_intx(true);`. This is to make ping work, which will be our basic unit test

set `TARGET = "theseus"` at the top of `main.py` for all of the environment variables to be set

## Usage

When you run the rust betterifier program after setup, it will begin with your original rust file and a prompt for how to modify the code. Each modification goal is called a "goal", and the program may try tens of different ways of forming a prompt before it gives up on a goal. Each prompt formulation of that goal is called an "attempt". Every time you run the rust betterifier, that is a "run".

The `log/` folder contains logs of each run, and for each goal within each run, and all attempts to reach that goal. Make sure to delete the folder if you want to work with a new piece of code

Once the rust betterifier has it's goal, it begins the evaluation loop. The evaluation loop is a series of checks that all must be passed for a modification to be deemed successful. On each attempt at passing all the checks, a patch file is generated given a prompt on how to improve the code. The evaluation loop steps are as follows:

1. The patch file (a JSON list of string replacements) is valid (5 attempts max)
2. The project with these patches applied to the target file can compile successfully
3. The project can run successfully (it passes a basic unit test)
    a. Note that from this, we don't know if the project maintained all its functionality, just that it maintained the most basic functionality
4. ...more to come!

When the run ends, the rust file you're modifying will revert to its original state. You can look at the `log/` folder to find the most recent improved version

## File Structure

- `main.py`: entry point. Controls the evaluation loop as well as the constants. Uses all the other files
- `io.py`: handles printing to the terminal and running programs
- `logger.py`: handles the tracking of attempts, goals, and runs
- `openai.py`: handles interaction with OpenAI and includes all prompts. Also manages patch applying

## Relevant Documents

- [Thesis Proposal](documents/proposal.pdf)
