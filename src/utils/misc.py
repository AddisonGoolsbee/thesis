def get_unsafe_lines(rust_code: str) -> tuple[int, int]:
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
    unsafe_count = 0
    unsafe_lines = 0
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
        bracket_depth += line.count("{")
        bracket_depth -= line.count("}")

        # Check for start of unsafe block - only if we're not already in an unsafe block
        if "unsafe" in line and not in_unsafe_block:
            found_unsafe = True
            # Count the unsafe line itself
            if count_code_in_line(line):
                print(f"Unsafe line {i+1}: {line}")
                unsafe_lines += 1
            # Check if opening brace is on same line
            if "{" in line:
                in_unsafe_block = True
                unsafe_count += 1
                found_unsafe = False
                # Check for additional code on same line as opening brace
                if count_code_in_line(line.replace("unsafe", "").strip()):
                    print(f"Unsafe line {i+1}: {line}")
                    unsafe_lines += 1
        # Check if opening brace is on next line after unsafe - only if we're not already in an unsafe block
        elif found_unsafe and "{" in line and not in_unsafe_block:
            in_unsafe_block = True
            unsafe_count += 1
            found_unsafe = False
            # Check for code on same line as opening brace
            if count_code_in_line(line):
                print(f"Unsafe line {i+1}: {line}")
                unsafe_lines += 1
        # Check for end of unsafe block - only if we're at the outermost level
        elif in_unsafe_block and "}" in line and bracket_depth == 0:
            # Check for code on same line as closing brace
            if count_code_in_line(line):
                print(f"Unsafe line {i+1}: {line}")
                unsafe_lines += 1
            in_unsafe_block = False
        # Count code lines inside unsafe block
        elif in_unsafe_block and is_code_line(line):
            print(f"Unsafe line {i+1}: {line}")
            unsafe_lines += 1

    return unsafe_count, unsafe_lines

if __name__ == "__main__":
    test_files = ["src/tests/test1.txt", "src/tests/test2.txt", "src/tests/test3.txt", "src/tests/test4.txt"]

    for test_file in test_files:
        print(f"\nTesting {test_file}:")
        try:
            with open(test_file, "r") as f:
                code = f.read()
                block_count, line_count = get_unsafe_lines(code)
                print(f"Found {block_count} unsafe blocks")
                print(f"Total lines of code inside unsafe blocks: {line_count}")
        except FileNotFoundError:
            print(f"Error: Could not find file {test_file}")
        except Exception as e:
            print(f"Error processing {test_file}: {str(e)}")
