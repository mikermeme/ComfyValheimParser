# Contributing to ComfyValheimParser

Thanks for your interest in contributing! This document covers how to set up your development environment, the project's conventions, and how to submit changes.

---

## Table of Contents

- [Development Setup](#development-setup)
- [Project Structure](#project-structure)
- [Coding Conventions](#coding-conventions)
- [Making Changes](#making-changes)
- [Testing Your Changes](#testing-your-changes)
- [Submitting Changes](#submitting-changes)
- [Areas Where Help Is Wanted](#areas-where-help-is-wanted)

---

## Development Setup

### System Requirements

| Tool | Version | Install (Ubuntu/Debian) |
|------|---------|------------------------|
| Python | 3.8+ | Usually pre-installed; or `sudo apt install python3` |
| Java JRE | 24+ | `sudo apt install openjdk-25-jre-headless` (Required for valheim-save-tools.jar) |
| Git | Any | `sudo apt install git` |

### Getting Started

```bash
# 1. Fork and clone the repository
git clone https://github.com/<your-username>/ComfyValheimParser.git
cd ComfyValheimParser

# 2. Install system dependencies (Ubuntu/Debian)
sudo apt update
sudo apt install -y openjdk-25-jre-headless python-is-python3

# 3. Verify your environment
python3 --version   # Should be 3.8+
java -version       # Should be 24+

# 4. Test the scripts with the included sample data
python3 parseItems.py test_data/myworld.db -o test_output.csv
python3 parseRewind.py test_data/myworld.rewind prefabs.csv test_output.json
```

### No Virtual Environment Needed

All scripts use only Python standard library modules — there are no third-party dependencies to install. No `pip install`, `venv`, or `requirements.txt` is needed for core functionality.

---

## Project Structure

```
ComfyValheimParser/
├── README.md                              # Project overview and usage guide
├── CONTRIBUTING.md                        # This file
├── docs/
│   └── binary-format.md                   # .rewind binary format documentation
│
├── parseItems.py          # Main tool: .db/.json → inventory CSV
├── parseRewind.py         # Rewind parser: .rewind → JSON (current)
├── rewind_dump - workingish.py            # Rewind parser: earlier version (reference)
│
├── prefabs.csv                            # Prefab hash → name lookup table
├── rewind.hexpat                          # ImHex pattern file with enum definitions
├── valheim-save-tools.jar                 # Java tool for .db → .json conversion
│
├── test_data/myworld.db                             # Sample world save
├── test_data/myworld.rewind                         # Sample rewind file (small)
├── test_data/castle.rewind                          # Sample rewind file (large)
├── test_data/myworld_items.csv                      # Sample output
│
├── Rewind.dll                             # Rewind mod DLL (reference only)
└── Rewind README.md                       # Rewind mod in-game command docs
```

---

## Coding Conventions

### Python Style

- **Python 3.8+** compatibility — avoid features added in 3.9+ (like `dict | dict` union syntax or `str.removeprefix()`).
- Follow [PEP 8](https://peps.python.org/pep-0008/) for general formatting:
  - 4-space indentation
  - `snake_case` for functions and variables
  - `UPPER_SNAKE_CASE` for module-level constants
- Use **type hints** for function signatures where practical.
- Include **docstrings** for all public functions explaining what they do, their parameters, and return values.
- Add **inline comments** for non-obvious logic, especially binary parsing operations where byte offsets and data formats matter.

### Binary Parsing

When working with binary file parsing:

- Always use **little-endian** byte order (Valheim/Unity convention), specified as `<` in `struct` format strings.
- Use the `Reader` class pattern for sequential binary reads — it keeps the code readable and tracks file position automatically.
- Document the **byte offset and size** of each field when adding new binary format support.
- Handle **hash ↔ name resolution** consistently: store both the raw hash and the resolved name when available.

### Error Handling

- Use `try/except` around binary parsing operations — save files can be corrupted or from unexpected game versions.
- Print user-friendly error messages to `stderr` (via `print(..., file=sys.stderr)`).
- Exit with non-zero status codes on fatal errors (`sys.exit(1)`).
- Silently skip malformed ZDO blocks during streaming to avoid one bad record aborting the entire export.

---

## Making Changes

### Branching

1. Create a feature branch from `main`:
   ```bash
   git checkout -b feature/my-improvement
   ```
2. Make your changes with clear, focused commits.
3. Push to your fork and open a Pull Request.

### Commit Messages

Use clear, descriptive commit messages:

```
Add support for parsing player inventory ZDOs

Parse ZDOs with prefab type "Player" to extract equipped items
and backpack contents in addition to container inventories.
```

---

## Testing Your Changes

### Using Sample Data

The repo includes sample files you can use to test your changes:

```bash
# Test the main exporter
python3 parseItems.py test_data/myworld.db -o test_output.csv
diff test_data/myworld_items.csv test_output.csv  # Should match

# Test the rewind parser
python3 parseRewind.py test_data/myworld.rewind prefabs.csv test_rewind.json
python3 parseRewind.py test_data/castle.rewind prefabs.csv test_castle.json

# Quick sanity check: count output records
wc -l test_output.csv              # Should be 31 lines (30 items + header)
python3 -c "import json; d=json.load(open('test_rewind.json')); print(len(d['zdoList']['zdos']), 'ZDOs')"
```

### Using Your Own Data

If you have access to a Valheim dedicated server or local world saves:

- **Linux server saves**: `~/.config/unity3d/IronGate/Valheim/worlds_local/`
- **Windows saves**: `%APPDATA%\..\LocalLow\IronGate\Valheim\worlds_local\`
- **Rewind mod exports**: Wherever your server's Rewind mod is configured to save

Copy your `.db` or `.rewind` files into the project directory and test against them.

### What To Verify

Before submitting a PR, check that:

- [ ] The main exporter produces valid CSV when run against `test_data/myworld.db`
- [ ] The rewind parser produces valid JSON when run against both `.rewind` sample files
- [ ] No Python warnings or unhandled exceptions during execution
- [ ] New code follows the project's style conventions (see above)
- [ ] Any new functionality is documented (docstrings, README updates, etc.)

---

## Submitting Changes

1. **Fork** the repository on GitHub
2. **Create a branch** for your changes
3. **Test** your changes against the included sample data
4. **Push** your branch to your fork
5. **Open a Pull Request** against `main` with:
   - A clear description of what you changed and why
   - Any relevant testing you performed
   - Screenshots or sample output if applicable

---

## Areas Where Help Is Wanted

Here are some areas where contributions would be especially valuable:

### Features
- **Player inventory parsing** — extract equipped items and backpack contents from Player ZDOs
- **Item name resolution** — map item prefab strings (e.g., `SwordIron`) to display names using game localization data
- **Filtering/search** — add CLI options to filter output by item type, container type, or world region
- **JSON output** — add an optional `--format json` output mode alongside CSV

### Code Quality
- **File naming cleanup** — rename scripts to remove spaces (e.g., `parseRewind.py` → `rewind_dump.py`)
- **Consolidation** — merge the "workingish" parser into the "fully working" one or remove it
- **Unit tests** — add pytest-based tests for the binary parsers and hash functions
- **Type hints** — add comprehensive type annotations

### Documentation
- **Expand binary format docs** — document additional ZDO property types and Valheim-specific conventions
- **Add usage examples** — real-world use cases and workflows
- **Add a changelog** — track changes across versions
