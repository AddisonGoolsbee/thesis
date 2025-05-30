TARGET = "quicksort"

CARGO_PATH = None
if TARGET == "theseus":
    CODE_PATH = "/Users/addisongoolsbee/Desktop/TheseusM/kernel/e1000_old/src/lib.rs"
    BUILD_CMD = "gmake iso -C ~/Desktop/TheseusM/ net=user"
    TEST_CMD = "python3 src/examples/theseus_e1000/theseus.py"
    TEST_EXPECTED_OUTPUT = "2 packets transmitted, 2 packets num_received, 0.0% packet loss"
    TEST_TIMEOUT = 15
elif TARGET == "rfk":
    CODE_PATH = "src/examples/rfk/src/main.rs"
    CARGO_PATH = "src/examples/rfk/Cargo.toml"
    BUILD_CMD = "cargo +nightly test --manifest-path src/examples/rfk/Cargo.toml --test test --no-run"
    TEST_CMD = "cargo +nightly test --manifest-path src/examples/rfk/Cargo.toml --test test"
    TEST_EXPECTED_OUTPUT = "test result: ok. 3 passed;"
    TEST_TIMEOUT = 15
elif TARGET == "quicksort":
    CODE_PATH = "src/examples/quicksort/src/main.rs"
    BUILD_CMD = "cargo build --manifest-path src/examples/quicksort/Cargo.toml"
    TEST_CMD = "./src/examples/quicksort/target/debug/quicksort"
    TEST_EXPECTED_OUTPUT = "[1, 2, 3, 4, 7, 9]"
    TEST_TIMEOUT = 15
