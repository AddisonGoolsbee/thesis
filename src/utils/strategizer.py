from enum import Enum, auto
from utils.openai import call_openai_api
from utils.logger import Logger


class StrategyStatus(Enum):
    SUCCESS = auto()
    FAILED_GENERATION = auto()
    CODE_SAFETY_DETERIORATED = auto()
    CODE_SAFETY_UNCHANGED = auto()
    FAILED_TOO_LONG = auto()


class Strategy:
    def __init__(self, prompt, result):
        self.prompt = prompt
        self.result = result


class Strategizer:
    def __init__(self, logger: Logger):
        self.logger = logger
        self.strategies: list[Strategy] = []

    def generate_strategy(self, current_code, current_toml):
        success_count = sum(1 for strategy in self.strategies if strategy.result == StrategyStatus.SUCCESS)
        if success_count != len(self.strategies):
            print("\n", self.get_failed_strategies())

        if current_toml:
            toml_message = f"Here is the current Cargo.toml file:\n{current_toml}"
        else:
            toml_message = ""

        prompt = f"""
You are a software engineering assistant. Your goal is to make a rust file safer, as defined by the number of unsafe lines in the code.

Here is the current code:
{current_code}

{toml_message}

{self.get_failed_strategies()}

You may not use other files in the same codebase unless you KNOW e.g. you've seen proof that that code exists.

Based on the current code, generate a description of a modification strategy that would make the code safer.
The strategy should be 1-2 sentences, and should only change an isolated amount of the code, instead of making sweeping changes.
{"You may not change the Cargo.toml file, so don't try to add any dependencies." if not current_toml else ""}
The strategy should be a single isolated strategy, such as "change this struct to use generic types to isolate the unsafe code (and its uses)" or "change this function to use the rust standard library instead of a c library (and everything that calls it)".
Make sure the strategy makes the code SAFER, not just more idiomatic/cleaner/faster. Make sure you include removing the "unsafe" keyword if it will no longer be needed.
Do not explain your reasoning. Just return the strategy.
"""
        strategy = call_openai_api(prompt)
        # strategy = "The current init_nic() function constructs an E1000Nic with placeholder values (zeros, None, empty vectors) and then gradually mutates it through multiple initialization calls, which breaks Rust's RAII principle by allowing partially-initialized state. To fix this, we need to redesign construction so that a fully valid E1000Nic is created in one step using a new() constructor. This means gathering all the required runtime information—such as PCI memory mappings, interrupt vectors, DMA regions, EEPROM presence, MAC address, and RX/TX descriptors—before instantiating the struct. Each field should be initialized with its real value, not a placeholder, and any setup that interacts with hardware (e.g., writing registers, allocating memory) should either happen before construction or be embedded into field-building helper functions. By doing this, we eliminate the risk of using the NIC in an invalid state, ensure safe construction logic, and align with idiomatic Rust by having E1000Nic::new(pci) return a fully working, ready-to-use network device."
        self.logger.log_strategy(strategy)
        return strategy

    def get_failed_strategies(self):
        success_count = sum(1 for strategy in self.strategies if strategy.result == StrategyStatus.SUCCESS)
        if success_count == len(self.strategies):
            return ""
        text = f"\nOut of the {len(self.strategies)} strategies you have tried so far, the following ones did not make the code safer:\n"
        for strategy in self.strategies:
            match strategy.result:
                case StrategyStatus.FAILED_TOO_LONG:
                    text += f"• This strategy took too long to generate a positive safety result, and thus timed out: {strategy.prompt}\n"
                case StrategyStatus.CODE_SAFETY_DETERIORATED:
                    text += f"• This strategy made the code less safe: {strategy.prompt}\n"
                case StrategyStatus.CODE_SAFETY_UNCHANGED:
                    text += f"• This strategy made no changes to the code safety: {strategy.prompt}\n"
                case _:
                    pass
        return text + "\nDo not repeat these strategies unless you have a good reason to do so.\n"

    def add_strategy(self, strategy_prompt, result, attempts, time_taken, initial_unsafe_lines):
        strategy = Strategy(strategy_prompt, result)
        self.strategies.append(strategy)

        log_message = ""
        match result:
            case StrategyStatus.SUCCESS:
                log_message = "code safety improved"
            case StrategyStatus.CODE_SAFETY_DETERIORATED:
                log_message = "code safety deteriorated"
            case StrategyStatus.CODE_SAFETY_UNCHANGED:
                log_message = "code safety unchanged"
            case StrategyStatus.FAILED_TOO_LONG:
                log_message = "failed to generate a successful implementation in time"
            case _:
                log_message = "unknown error"
        self.logger.log_strategy_result(f"Result: {log_message} in {attempts} attempt{'s' if attempts != 1 else ''} and {time_taken:.2f}s", initial_unsafe_lines)

    def should_quit(self):
        consecutive_failures = 0
        for strategy in reversed(self.strategies):
            if strategy.result != StrategyStatus.SUCCESS:
                consecutive_failures += 1
            else:
                break
        return consecutive_failures >= 10
