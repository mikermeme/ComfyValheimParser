# Comfy Valheim Parser

Extract and catalog every item stored inside containers in your Valheim world saves — treasure chests, player tombstones, barrels, and more — into a single, searchable CSV file.

This toolset also includes a binary parser for `.rewind` files created by the [Rewind](https://valheim.thunderstore.io/package/Smoothbrain/Rewind/) mod, allowing you to inspect and export saved builds as structured JSON.

---

## Table of Contents

- [Features](#features)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Usage](#usage)
  - [Pipeline 1: World Save (.db) → Inventory CSV](#pipeline-1-world-save-db--inventory-csv)
  - [Pipeline 2: Rewind File (.rewind) → JSON](#pipeline-2-rewind-file-rewind--json)
- [File Reference](#file-reference)
- [Output Formats](#output-formats)
- [How It Works](#how-it-works)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)

---

## Features

- **Extract all container inventories** from Valheim `.db` world saves into a flat CSV
- **Memory-efficient streaming** — handles massive world files (10GB+) without loading everything into RAM
- **Parse `.rewind` mod files** — decode binary Rewind exports into human-readable JSON
- **Name resolution** — translates internal prefab hash codes into readable item/object names using `prefabs.csv` and `rewind.hexpat`
- **Zero external Python dependencies** — uses only the Python standard library

---

## Prerequisites

| Requirement | Version | Needed For | Install Command (Ubuntu/Debian) |
|-------------|---------|------------|--------------------------------|
| **Python 3** | 3.8+ | All scripts | Pre-installed on most Linux distros |
| **Java (JRE)** | 24+ | Parsing `.db` files only | `sudo apt install openjdk-25-jre-headless` |
| **Git** | Any | Cloning the repo | `sudo apt install git` |

> **Note:** Java is only required if you are parsing `.db` world save files directly. If you already have a `.json` export (from `valheim-save-tools`), or are only working with `.rewind` files, Java is not needed.
> 
> **Important:** The bundled `valheim-save-tools.jar` requires **Java 24 or newer** (compiled with class file version 68.0). Ubuntu 24.04's `default-jre` package installs Java 21, which will result in an `UnsupportedClassVersionError`. You must install a newer JRE, such as `openjdk-25-jre-headless`.

---

## Quick Start

```bash
# Clone the repository
git clone https://github.com/mikermeme/ComfyValheimParser.git
cd ComfyValheimParser

# Install Java (Java 24+ required for valheim-save-tools.jar)
sudo apt update && sudo apt install -y openjdk-25-jre-headless

# Extract items from a world save
python3 parseItems.py test_data/myworld.db

# Parse a Rewind mod file
python3 parseRewind.py test_data/myworld.rewind prefabs.csv output.json
```

---

## Original Author's Quick Guide

**parseRewind** turns rewind files into json.

Download all the files and put them in the same directory.
`parseRewind.py` expects `rewind.hexpat` in there to un-hashcode the ZDOvar names.

```bash
python parseRewind.py Your_Rewind_file
```

**parseItems** takes `.db` world saves or the `.json` output from either `valheim-save-tools` or `parseRewind`. It will call `valheim-save-tools` and make a temporary json if you point it at a world file.

```bash
python parseItems.py Your_World_Save.db
```
or
```bash
python parseItems.py Your_Parsed_World_Save.json
```
or
```bash
python parseItems.py Your_Parsed_Rewind.json
```

---

## Usage

### Pipeline 1: World Save (.db) → Inventory CSV

The main exporter reads a Valheim `.db` world save file, converts it to JSON using [valheim-save-tools](https://github.com/Kakoen/valheim-save-tools), then streams through all game objects to find containers and extract their inventories.

```bash
# Basic usage — output defaults to <input_name>_items.csv
python3 parseItems.py /path/to/test_data/myworld.db

# Specify a custom output path
python3 parseItems.py /path/to/test_data/myworld.db -o my_inventory.csv

# If valheim-save-tools.jar is in a different location
python3 parseItems.py /path/to/test_data/myworld.db --jar /path/to/valheim-save-tools.jar

# Keep the intermediate JSON file (normally auto-deleted)
python3 parseItems.py /path/to/test_data/myworld.db --keep-json
```

You can also skip the `.db` → JSON conversion by providing a pre-exported JSON file directly:

```bash
python3 parseItems.py /path/to/myworld.json
```

**Command-line arguments:**

| Argument | Description | Default |
|----------|-------------|---------|
| `input` | Path to `.db` world save or `.json` export | *(required)* |
| `-o`, `--output` | Output CSV file path | `<input_name>_items.csv` |
| `--jar` | Path to `valheim-save-tools.jar` | `valheim-save-tools.jar` (current dir) |
| `--keep-json` | Retain the intermediate JSON after conversion | Deletes it |

### Pipeline 2: Rewind File (.rewind) → JSON

The rewind dump script directly reads the binary `.rewind` format created by the [Rewind mod](https://valheim.thunderstore.io/package/Smoothbrain/Rewind/) and outputs structured JSON containing all ZDO (Zone Data Object) records.

```bash
python3 parseRewind.py <rewind_file> <prefabs_csv> <output_json>
```

**Example:**

```bash
# Parse a castle build export
python3 parseRewind.py test_data/castle.rewind prefabs.csv castle_output.json
```

**Positional arguments:**

| Position | Description |
|----------|-------------|
| 1 | Path to the `.rewind` binary file |
| 2 | Path to `prefabs.csv` (prefab hash → name lookup table) |
| 3 | Output JSON file path |

The script will also look for `rewind.hexpat` in the same directory as the script for additional ZDO variable name resolution.

---

## File Reference

### Scripts

| File | Description |
|------|-------------|
| `parseItems.py` | Main tool — extracts container inventories from `.db`/`.json` into CSV |
| `parseRewind.py` | Parses `.rewind` binary files into JSON with full name resolution |
| `rewind_dump - workingish.py` | Earlier version of the rewind parser (superseded, kept for reference) |

### Data & Reference Files

| File | Description |
|------|-------------|
| `prefabs.csv` | Lookup table: signed prefab hash → human-readable prefab name (~3,500 entries) |
| `rewind.hexpat` | ImHex pattern file with enum definitions for ZDO variable and prefab hashes (~20,000 lines) |
| `valheim-save-tools.jar` | Java CLI utility from [Kakoen/valheim-save-tools](https://github.com/Kakoen/valheim-save-tools) for `.db` → `.json` conversion |

### Sample Data

| File | Description |
|------|-------------|
| `test_data/myworld.db` | Sample Valheim world save file |
| `test_data/myworld.rewind` | Small sample `.rewind` file |
| `test_data/castle.rewind` | Larger sample `.rewind` file (~2.1 MB) |
| `test_data/myworld_items.csv` | Pre-generated output from running the exporter on `test_data/myworld.db` |

### Other

| File | Description |
|------|-------------|
| `Rewind.dll` | The Rewind mod DLL (reference only — not used by scripts) |
| `Rewind README.md` | Documentation for the Rewind mod's in-game commands |

---

## Output Formats

### Inventory CSV Columns

The CSV produced by `parseItems.py` contains one row per item per container:

| Column | Description |
|--------|-------------|
| `container_prefab` | Numeric prefab hash of the container |
| `container_prefab_name` | Human-readable name (e.g., `TreasureChest_meadows`) |
| `container_x/y/z` | World coordinates of the container |
| `container_sector_x/y` | World sector the container is in |
| `container_creator_id` | Steam ID of the player who placed the container |
| `container_custom_name` | Any custom name/tag on the container |
| `item_prefab` | Item type (e.g., `SwordIron`, `ArrowFlint`) |
| `item_stack` | Stack count |
| `item_durability` | Current durability |
| `item_grid_x/y` | Position in the container's inventory grid |
| `item_quality` | Upgrade level / quality tier |
| `item_variant` | Visual variant index |
| `item_crafter_id` | Steam ID of the player who crafted the item |
| `item_crafter_name` | Display name of the crafter |
| `item_custom_data` | Serialized mod data (e.g., Epic Loot enchantments) |

### Rewind JSON Structure

The JSON produced by the rewind dump script follows the `valheim-save-tools` schema:

```json
{
  "type": "DB",
  "zdoList": {
    "zdos": [
      {
        "userID": 76561198012345678,
        "zdoID": 12345,
        "persistent": true,
        "prefabHash": -1443983522,
        "prefabName": "piece_chest",
        "sector": { "x": 0, "y": 0 },
        "position": { "x": 0.0, "y": 60.0, "z": -2.0 },
        "rotation": { "x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0 },
        "floats": { "health": 100.0 },
        "ints": { "addedDefaultItems": 1 },
        "longs": { "creator": -484064227 },
        "strings": { "items": "<base64-encoded inventory blob>" }
      }
    ]
  }
}
```

---

## How It Works

### Valheim Save Structure

Valheim stores its world state as a collection of **ZDOs** (Zone Data Objects). Each ZDO represents a game object — a tree, a chest, a monster, a building piece, etc. Every ZDO has:

- A **prefab hash** identifying what type of object it is
- A **position** and **rotation** in the world
- **Typed property maps** (floats, ints, longs, strings, bytes) containing the object's state

Containers (chests, barrels, tombstones) store their inventory as a **base64-encoded binary blob** inside a string property keyed by the hash of `"items"`. This blob contains a serialized array of item records with fields like prefab name, stack size, durability, grid position, crafter info, and mod-specific custom data.

### What The Exporter Does

1. **Converts** `.db` to JSON via `valheim-save-tools.jar` (or accepts pre-exported JSON)
2. **Streams** through ZDOs using a memory-efficient line-by-line parser for large files
3. **Filters** for ZDOs that contain an `"items"` string property
4. **Decodes** the base64 inventory blob using C#/.NET binary serialization conventions (7-bit encoded integers, little-endian structs)
5. **Writes** one CSV row per item, enriched with container metadata

### What The Rewind Parser Does

1. **Reads** the `.rewind` binary file header (magic number, ZDO count, world offset)
2. **Iterates** through each ZDO record, parsing the fixed-size header followed by variable-length property arrays
3. **Resolves** hash integers to human-readable names using `rewind.hexpat` enums and `prefabs.csv`
4. **Outputs** JSON matching the `valheim-save-tools` schema for compatibility with other tools

For detailed documentation of the `.rewind` binary format, see [docs/binary-format.md](docs/binary-format.md).

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `Error: 'java' is not installed` | Install Java 24+: `sudo apt install openjdk-25-jre-headless` |
| `UnsupportedClassVersionError` | Java version is too old. Ensure you have Java 24+ installed (e.g. `openjdk-25-jre-headless` on Ubuntu 24.04). |
| `Error: 'valheim-save-tools.jar' tool was not found` | Download from [valheim-save-tools releases](https://github.com/Kakoen/valheim-save-tools/releases) and place in the project directory, or specify path with `--jar` |
| `python: command not found` | Use `python3` instead, or run `sudo apt install python-is-python3` |
| Out of memory on large worlds | The exporter auto-detects pretty-printed JSON and streams line-by-line. If you still run out of RAM, ensure `valheim-save-tools` is producing pretty-printed (indented) output. |
| Missing prefab names in output | Make sure `prefabs.csv` and/or `rewind.hexpat` are in the working directory. Unresolved names will appear as numeric hashes. |

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, coding conventions, and how to submit changes.

---

## License

*No license has been specified yet. Please contact the repository owner for usage terms.*

---

## Credits

- **[mikermeme](https://github.com/mikermeme)** — Original author
- **[Kakoen/valheim-save-tools](https://github.com/Kakoen/valheim-save-tools)** — Java utility for `.db` → JSON conversion
- **[Rewind mod](https://valheim.thunderstore.io/package/Smoothbrain/Rewind/)** — The Valheim mod that creates `.rewind` save files
