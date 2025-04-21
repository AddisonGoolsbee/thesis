import json


def count_unsafe(rust_code: str, debug: bool = False) -> tuple[int, int]:
    def remove_comments(code: str) -> str:
        """Remove all comments from the code."""
        lines = code.split("\n")
        result = []
        in_multiline = False

        for line in lines:
            # Handle multi-line comments
            if "/*" in line:
                in_multiline = True
                line = line.split("/*")[0]
            if "*/" in line:
                in_multiline = False
                line = line.split("*/")[1]
            if in_multiline:
                continue

            # Handle single-line comments
            if "//" in line:
                line = line.split("//")[0]

            result.append(line)

        return "\n".join(result)

    # Remove all comments first
    rust_code = remove_comments(rust_code)

    lines = rust_code.split("\n")
    num_unsafe_blocks = 0
    num_unsafe_lines = 0
    in_unsafe_block = False
    found_unsafe = False
    bracket_depth = 0

    def is_code_line(line: str) -> bool:
        """Check if a line contains actual code (not just brackets/whitespace)."""
        # Strip whitespace and check if line is empty
        stripped = line.strip()
        if not stripped:
            return False

        # Check if line only contains brackets, parentheses, commas, etc.
        only_symbols = all(c in "{}()[],;" for c in stripped)
        return not only_symbols

    def count_code_in_line(line: str) -> bool:
        """Count if there's code in a line, even if it has braces."""
        # Remove braces to check remaining content
        cleaned = line.replace("{", "").replace("}", "").strip()
        return bool(cleaned) and not all(c in "()[],;" for c in cleaned)

    for i, line in enumerate(lines):
        # Count opening and closing braces to track nesting
        if in_unsafe_block:
            bracket_depth += line.count("{")
            bracket_depth -= line.count("}")

        # Check for start of unsafe block - only if we're not already in an unsafe block
        if "unsafe" in line and not in_unsafe_block:
            found_unsafe = True
            # Count the unsafe line itself
            if count_code_in_line(line.replace("unsafe", "").strip()):
                if debug:
                    print(f"Unsafe line {i+1}: {line}")
                num_unsafe_lines += 1

            if "{" in line:
                in_unsafe_block = True
                num_unsafe_blocks += 1
                found_unsafe = False
                bracket_depth += line.count("{")
            # Check for additional code on same line as opening brace

        # Check if opening brace is on next line after unsafe - only if we're not already in an unsafe block
        elif found_unsafe and "{" in line and not in_unsafe_block:
            in_unsafe_block = True
            num_unsafe_blocks += 1
            found_unsafe = False
            bracket_depth += line.count("{")
            # Check for code on same line as opening brace
            if count_code_in_line(line):
                if debug:
                    print(f"Unsafe line {i+1}: {line}")
                num_unsafe_lines += 1
        # Check for end of unsafe block - only if we're at the outermost level
        elif in_unsafe_block and "}" in line and bracket_depth == 0:
            # Check for code on same line as closing brace
            if count_code_in_line(line):
                if debug:
                    print(f"Unsafe line {i+1}: {line}")
                num_unsafe_lines += 1
            in_unsafe_block = False
        # Count code lines inside unsafe block
        elif in_unsafe_block and is_code_line(line):
            if debug:
                print(f"Unsafe line {i+1}: {line}")
            num_unsafe_lines += 1

    return num_unsafe_lines, num_unsafe_blocks


def apply_changes(current_code: str, changes: list) -> str:
    def normalize_whitespace(code: str) -> str:
        # Remove all whitespace including newlines
        return "".join(code.split())

    def find_normalized_substring(haystack: str, needle: str) -> tuple[int, int]:
        """Find the start and end positions of a normalized substring in the original string."""
        normalized_haystack = normalize_whitespace(haystack)
        normalized_needle = normalize_whitespace(needle)

        if normalized_needle not in normalized_haystack:
            return -1, -1

        # Find position in normalized string
        norm_pos = normalized_haystack.find(normalized_needle)

        # Convert back to original string positions
        orig_start = 0
        norm_count = 0

        # Find the start position
        for i, c in enumerate(haystack):
            if not c.isspace():
                if norm_count == norm_pos:
                    orig_start = i
                    break
                norm_count += 1

        # Find the end position
        orig_end = orig_start
        norm_count = norm_pos
        for i in range(orig_start, len(haystack)):
            if not haystack[i].isspace():
                norm_count += 1
                if norm_count == norm_pos + len(normalized_needle):
                    orig_end = i + 1
                    break

        return orig_start, orig_end

    for replacement in changes:
        start_pos, end_pos = find_normalized_substring(current_code, replacement["original"])

        if start_pos == -1:
            raise ValueError(
                f"Replacement string not found in code (after whitespace normalization): {replacement['original']}"
            )

        # Replace the actual text with the new text
        current_code = current_code[:start_pos] + replacement["new"] + current_code[end_pos:]

    return current_code


if __name__ == "__main__":
    TARGET = "apply_changes"

    match TARGET:
        case "count_unsafe":
            test_files = [
                "src/tests/count_unsafe/test1.txt",
                "src/tests/count_unsafe/test2.txt",
                "src/tests/count_unsafe/test3.txt",
                "src/tests/count_unsafe/test4.txt",
                "src/examples/quicksort/src/main.rs",
                "src/log/run004/strategy001/code001.rs",
            ]

            for test_file in test_files:
                print(f"\nTesting {test_file}:")
                try:
                    with open(test_file, "r") as f:
                        code = f.read()
                        line_count, block_count = count_unsafe(code, debug=True)
                        print(f"Found {block_count} unsafe blocks")
                        print(f"Total lines of code inside unsafe blocks: {line_count}")
                except FileNotFoundError:
                    print(f"Error: Could not find file {test_file}")
                except Exception as e:
                    print(f"Error processing {test_file}: {str(e)}")
            pass
        case "apply_changes":
            print("Testing with tests/apply_changes/test1.rs:")
            with open("src/tests/apply_changes/test1.rs", "r") as f:
                test_code = f.read()
            with open("src/tests/apply_changes/test1.json", "r") as f:
                changes = f.read()
            test_changes = json.loads(open("src/tests/apply_changes/test1.json", "r").read())
            test_result = apply_changes(test_code, changes)
            with open("src/tests/apply_changes/test1_result.rs", "w") as f:
                f.write(test_result)
        case _:
            raise ValueError(f"Invalid target: {TARGET}")
