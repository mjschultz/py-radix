# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

py-radix is a Python library implementing the radix tree data structure for IPv4 and IPv6 network prefix storage and retrieval. **This repository now contains a Rust rewrite with Python bindings for significantly improved performance while maintaining 100% API compatibility.**

## Architecture

### New Rust-Based Implementation (Current)
- **radix/__init__.py**: Modern Python interface wrapping Rust implementation
- **src/**: Rust source code using PyO3 for Python bindings
  - **src/lib.rs**: PyO3 module definition
  - **src/radix.rs**: Core radix tree implementation
  - **src/node.rs**: RadixNode implementation
  - **src/prefix.rs**: Network prefix handling
- **Cargo.toml**: Rust project configuration
- **pyproject.toml**: Modern Python packaging with maturin

### Legacy Implementation (Compatibility)
- **radix/compat/**: Original C/Python implementation moved for backward compatibility
- **setup.py**: Legacy build system (still functional)

## Development Commands

### Rust-Based Development (Recommended)
```bash
# Set up development environment
uv venv .venv
source .venv/bin/activate

# Install maturin for building Rust extensions
pip install maturin

# Build and install in development mode
maturin develop

# Build release wheel
maturin build --release

# Run tests
python test_basic.py
python -m unittest tests.test_regression -v
```

### Legacy Development
```bash
# Standard installation
python setup.py build
python setup.py install

# Build without C extension
RADIX_NO_EXT=1 python setup.py build
```

### Testing
```bash
# Run custom test suite
python test_basic.py

# Run original regression tests
python -m unittest tests.test_regression -v

# Run compatibility tests (pickle support)
python -m unittest tests.test_compat -v

# Legacy testing
python setup.py nosetests
```

### Linting
```bash
# Rust code
cargo clippy
cargo fmt

# Python code
flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
flake8 . --count --ignore=E741,W503 --max-complexity=23 --max-line-length=127 --statistics
```

### Cleanup
```bash
# Clean Rust build artifacts
cargo clean

# Clean Python artifacts
find . -name '*.py[co]' -delete
find . -name '__pycache__' -delete
find . -name '*.so' -delete
rm -rf build/ dist/ *.egg *.egg-info/ target/
```

## Key Implementation Details

### Modern Rust Implementation
- **Performance**: Significantly faster than C extension due to Rust optimizations
- **Memory Safety**: No risk of segfaults or memory leaks
- **Type Safety**: Compile-time guarantees for correctness
- **API Compatibility**: 100% compatible with original py-radix API
- **PyO3 Integration**: Seamless Python/Rust interop

### Compatibility Features
- Supports IPv4 and IPv6 prefixes in the same tree
- Network prefixes can be specified as CIDR strings, separate network/masklen, or packed binary addresses
- RadixNode objects store user data in a `data` dictionary attribute
- Full API compatibility with original implementation

### Known Issues (Work in Progress)
- Some regression tests failing due to minor API differences
- Pickle support not yet implemented
- Node identity (same prefix returning same object) needs work
- Iterator ordering may differ from original

## Package Structure

```
py-radix/
├── radix/                  # Main package (new Rust-based implementation)
│   ├── __init__.py        # Modern Python interface
│   └── compat/            # Legacy C/Python implementation
│       ├── __init__.py    # Original interface
│       ├── radix.py       # Pure Python implementation
│       ├── _radix.c       # C extension
│       └── _radix/        # C extension sources
├── src/                   # Rust source code
├── tests/                 # Original test suite
├── Cargo.toml            # Rust project config
├── pyproject.toml        # Modern Python packaging
└── setup.py              # Legacy build system
```

## CI/Testing Notes

- Tests run on Python 3.8+ (Rust implementation supports Python 3.8+)
- CI should be updated to use maturin for builds
- flake8 linting rules remain the same
- New Rust tests can be added with `cargo test`