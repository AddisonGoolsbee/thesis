TARGET = "rfk"

if TARGET == "theseus":
    CODE_PATH = "/Users/addisongoolsbee/Desktop/Theseus/kernel/e1000/src/lib.rs"
    BUILD_CMD = "gmake iso -C ~/Desktop/Theseus/ net=user"
    BASIC_TEST_CMD = "python3 src/examples/theseus.py"
    BASIC_TEST_EXPECTED_OUTPUT = "2 packets transmitted, 2 packets num_received, 0.0% packet loss"
    BASIC_TEST_TIMEOUT = 15
elif TARGET == "rfk":
    CODE_PATH = "src/examples/rfk/src/main.rs"
    BUILD_CMD = "cargo +nightly test --manifest-path src/examples/rfk/Cargo.toml --test test --no-run"
    BASIC_TEST_CMD = "cargo +nightly test --manifest-path src/examples/rfk/Cargo.toml --test test"
    BASIC_TEST_EXPECTED_OUTPUT = "test result: ok. 3 passed;"
    BASIC_TEST_TIMEOUT = 15
else:
    CODE_PATH = "temp.rs"
    BUILD_CMD = f"rustc ./temp.rs -o prog"
    BASIC_TEST_CMD = "./prog"
    BASIC_TEST_EXPECTED_OUTPUT = "This is a simple Rust program."
    BASIC_TEST_TIMEOUT = 3
