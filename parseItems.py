import argparse
import base64
import csv
import json
import mmap
import os
import shutil
import struct
import subprocess
import sys
from io import BytesIO
from pathlib import Path

# --- VALHEIM STABLE HASHES & UTILITIES ---

def get_stable_hash_code(s: str) -> int:
    """Simulates Valheim's 32-bit signed integer GetStableHashCode algorithm."""
    hash_val = 5381
    for char in s:
        hash_val = ((hash_val << 5) + hash_val) ^ ord(char)
        hash_val = (hash_val & 0xFFFFFFFF)
    if hash_val >= 0x80000000:
        hash_val -= 0x100000000
    return hash_val

# Pre-calculate common property hashes in case names are unresolved in the JSON
HASH_ITEMS = str(get_stable_hash_code("items"))          # '179721187'
HASH_CREATOR = str(get_stable_hash_code("creator"))      # '-374753447'
HASH_HEALTH = str(get_stable_hash_code("health"))        # '1581283705'
HASH_TAG = str(get_stable_hash_code("tag"))              # '193421815'
HASH_TEXT = str(get_stable_hash_code("text"))            # '2087956376'
HASH_NAME = str(get_stable_hash_code("name"))            # '2087876002'
HASH_CUSTOM_NAME = str(get_stable_hash_code("custom_name")) # '-250281458'


def get_zdo_value(zdo, category, field_name, hash_str):
    """Retrieves a value from a ZDO dictionary, supporting both nested

    ByName structures (valheim-save-tools) and flat structures (Rewind),
    as well as resolved/unresolved stable hashes.
    """
    # 1. Try nested ByName structure (e.g. stringsByName)
    by_name = zdo.get(f"{category}ByName")
    if by_name and field_name in by_name:
        return by_name[field_name]
    
    # 2. Try flat Category structure (e.g. strings)
    normal = zdo.get(category)
    if normal:
        # Rewind uses direct names in 'strings', 'longs', etc.
        if field_name in normal:
            return normal[field_name]
        # valheim-save-tools unresolved strings uses hash strings (e.g. '179721187')
        if hash_str in normal:
            return normal[hash_str]
        # Fallback for integer hash keys if serialized directly
        try:
            hash_int = int(hash_str)
            if hash_int in normal:
                return normal[hash_int]
        except ValueError:
            pass
            
    return None


# --- BINARY INVENTORY BLOB PARSERS ---

def read_7bit_int(f):
    result = 0
    shift = 0
    while True:
        b = f.read(1)
        if not b:
            raise EOFError("Unexpected end of file while reading 7-bit encoded integer")
        b = b[0]
        result |= (b & 0x7F) << shift
        if (b & 0x80) == 0:
            return result
        shift += 7


def read_string(f):
    length = read_7bit_int(f)
    if length == 0:
        return ""
    return f.read(length).decode("utf-8", errors="replace")


def read_bool(f):
    return struct.unpack("<?", f.read(1))[0]


def read_int(f):
    return struct.unpack("<i", f.read(4))[0]


def read_long(f):
    return struct.unpack("<q", f.read(8))[0]


def read_float(f):
    return struct.unpack("<f", f.read(4))[0]


def read_vector2i(f):
    return (read_int(f), read_int(f))


def parse_inventory(items_field):
    """Parses base64-encoded inventory blob."""
    try:
        data = base64.b64decode(items_field)
    except Exception:
        return []

    f = BytesIO(data)
    try:
        version = read_int(f)
        item_count = read_int(f)
    except (EOFError, struct.error):
        return []

    items = []
    for _ in range(item_count):
        try:
            prefab = read_string(f)
            stack = read_int(f)
            durability = read_float(f)
            x, y = read_vector2i(f)
            equipped = read_bool(f)
            quality = read_int(f)
            variant = read_int(f)
            crafter_id = read_long(f)
            crafter_name = read_string(f)
            custom_count = read_int(f)

            custom_data = {}
            for _ in range(custom_count):
                key = read_string(f)
                value = read_string(f)
                custom_data[key] = value

            world_level = read_int(f)
            picked_up = read_bool(f)

            items.append({
                "prefab": prefab,
                "stack": stack,
                "durability": durability,
                "x": x,
                "y": y,
                "equipped": equipped,
                "quality": quality,
                "variant": variant,
                "crafter_id": crafter_id,
                "crafter_name": crafter_name,
                "world_level": world_level,
                "picked_up": picked_up,
                "custom_data_count": custom_count,
                "custom_data": custom_data,
            })
        except (EOFError, struct.error):
            break

    return items


# --- MEMORY-MAPPED (MMAP) SECTOR EXTRACTORS ---

def find_all_offsets_bytes(mm, pattern):
    """Locates all occurrences of a byte pattern inside the memory map."""
    offsets = []
    pos = mm.find(pattern)
    while pos != -1:
        offsets.append(pos)
        pos = mm.find(pattern, pos + len(pattern))
    return offsets


def find_zdo_start_bytes(mm, items_pos):
    """Traverses backwards from the matched inventory key to find the opening

    brace '{' of the ZDO object. Tracks string literals and brace depth to 
    handle nesting dynamically.
    """
    pos = items_pos
    parent_braces_to_find = 2  # 1 for 'strings'/'stringsByName' block, 1 for ZDO
    state = b"normal"
    brace_depth = 0
    
    while pos > 0:
        pos -= 1
        char = mm[pos:pos+1]
        
        # Track string boundaries
        if char == b'"':
            backslash_count = 0
            temp_pos = pos - 1
            while temp_pos >= 0 and mm[temp_pos:temp_pos+1] == b'\\':
                backslash_count += 1
                temp_pos -= 1
            if backslash_count % 2 == 0:
                state = b"string" if state == b"normal" else b"normal"
                    
        if state == b"normal":
            if char == b'}':
                brace_depth += 1
            elif char == b'{':
                brace_depth -= 1
                if brace_depth == -1:
                    parent_braces_to_find -= 1
                    if parent_braces_to_find == 0:
                        return pos  # Found the opening brace of the ZDO
                    brace_depth = 0
    return None


def find_base64_end_bytes(mm, items_pos):
    """Finds the ending quote of the Base64 value after the key name

    to skip string scanning completely during forward parsing.
    """
    # Locate opening quote of base64
    pos = mm.find(b'"', items_pos + len(b'"items"'))
    if pos == -1:
        return None
    
    mm_len = len(mm)
    while pos < mm_len - 1:
        pos += 1
        char = mm[pos:pos+1]
        if char == b'"':
            backslash_count = 0
            temp_pos = pos - 1
            while temp_pos >= 0 and mm[temp_pos:temp_pos+1] == b'\\':
                backslash_count += 1
                temp_pos -= 1
            if backslash_count % 2 == 0:
                return pos  # Closing quote of Base64 value
    return None


def find_zdo_end_bytes(mm, start_pos):
    """Scans forward from the end of the base64 value to locate the closing

    brace '}' of the ZDO object.
    """
    parent_braces_to_find = 2  # 1 to close strings/stringsByName, 1 to close ZDO
    brace_depth = 0
    state = b"normal"
    pos = start_pos
    mm_len = len(mm)
    
    while pos < mm_len:
        char = mm[pos:pos+1]
        if state == b"normal":
            if char == b'"':
                state = b"string"
            elif char == b'{':
                brace_depth += 1
            elif char == b'}':
                brace_depth -= 1
                if brace_depth == -1:
                    parent_braces_to_find -= 1
                    if parent_braces_to_find == 0:
                        return pos
                    brace_depth = 0
        elif state == b"string":
            if char == b'"':
                state = b"normal"
            elif char == b'\\':
                pos += 1  # Skip escaped char
        pos += 1
    return None


def iterate_zdos(file_path: Path):
    """Memory-efficient parser that maps the JSON file on disk (mmap)

    and isolates only the raw ZDO byte segments that contain container keys.
    """
    print("-> Indexing JSON file using memory mapping (mmap)...")
    
    with open(file_path, "rb") as f:
        f.seek(0, os.SEEK_END)
        size = f.tell()
        f.seek(0)
        
        if size == 0:
            print("-> Warning: The JSON file is empty.")
            return
            
        with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
            # Locate all occurrences of the inventory keys
            offsets = []
            offsets.extend(find_all_offsets_bytes(mm, b'"items"'))
            offsets.extend(find_all_offsets_bytes(mm, b'"179721187"'))
            
            # Deduplicate and sort offsets from start to end of the file
            all_offsets = sorted(list(set(offsets)))
            print(f"-> Found {len(all_offsets)} candidate inventory references.")
            
            success_count = 0
            for offset in all_offsets:
                start_pos = find_zdo_start_bytes(mm, offset)
                if start_pos is None:
                    continue
                    
                b64_end_pos = find_base64_end_bytes(mm, offset)
                if b64_end_pos is None:
                    continue
                    
                end_pos = find_zdo_end_bytes(mm, b64_end_pos + 1)
                if end_pos is None:
                    continue
                    
                # Extract and decode the single isolated ZDO block
                zdo_bytes = mm[start_pos : end_pos + 1]
                zdo_str = zdo_bytes.decode("utf-8", errors="replace")
                
                try:
                    zdo = json.loads(zdo_str)
                    success_count += 1
                    yield zdo
                except Exception:
                    pass
            
            print(f"-> Successfully extracted and parsed {success_count} container ZDOs.")


def iterate_all_zdos(file_path: Path):
    """Memory-efficient iterator that yields every ZDO from a JSON file.

    Uses mmap to stream through the file without loading it into memory.
    Handles files of any size (10GB+) by parsing one ZDO at a time.
    Locates the "zdos" or "zdoList" array and iterates through its elements by
    tracking brace depth and string boundaries.
    """
    print("-> Scanning JSON for all ZDO objects (mmap)...")

    with open(file_path, "rb") as f:
        f.seek(0, os.SEEK_END)
        size = f.tell()
        f.seek(0)

        if size == 0:
            print("-> Warning: The JSON file is empty.")
            return

        with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
            # 1. Find the "zdos" array key or "zdoList" array key
            zdos_key = mm.find(b'"zdos"')
            if zdos_key == -1:
                zdos_key = mm.find(b'"zdoList"')
                if zdos_key == -1:
                    print("-> Warning: No 'zdos' or 'zdoList' array found in JSON.")
                    return

            array_start = mm.find(b'[', zdos_key)
            if array_start == -1:
                return

            # 2. Iterate through array elements
            pos = array_start + 1
            zdo_count = 0

            while pos < size:
                # Skip whitespace and commas
                while pos < size and mm[pos:pos+1] in (b' ', b'\n', b'\r', b'\t', b','):
                    pos += 1

                if pos >= size or mm[pos:pos+1] == b']':
                    break  # End of zdos array

                if mm[pos:pos+1] != b'{':
                    pos += 1
                    continue

                # 3. Found start of a ZDO object — scan for its closing brace
                obj_start = pos
                depth = 0
                in_string = False

                while pos < size:
                    char = mm[pos:pos+1]
                    if in_string:
                        if char == b'\\':
                            pos += 1  # Skip escaped character
                        elif char == b'"':
                            in_string = False
                    else:
                        if char == b'"':
                            in_string = True
                        elif char == b'{':
                            depth += 1
                        elif char == b'}':
                            depth -= 1
                            if depth == 0:
                                # 4. Complete ZDO — extract, parse, yield
                                zdo_bytes = mm[obj_start:pos+1]
                                try:
                                    zdo = json.loads(zdo_bytes.decode("utf-8", errors="replace"))
                                    zdo_count += 1
                                    yield zdo
                                except json.JSONDecodeError:
                                    pass  # Skip malformed ZDO blocks
                                pos += 1
                                break
                    pos += 1

            print(f"-> Iterated {zdo_count} ZDOs for prefab export.")


def get_merged_properties(zdo, flat_key, by_name_key):
    """Merges two dictionaries (flat property map and ByName map) from a ZDO."""
    res = {}
    flat_val = zdo.get(flat_key)
    if isinstance(flat_val, dict):
        res.update(flat_val)
    by_name_val = zdo.get(by_name_key)
    if isinstance(by_name_val, dict):
        res.update(by_name_val)
    return res


def serialize_property_map(prop_dict: dict) -> str:
    """Serializes a property map dictionary into a semicolon-separated string.
    
    Simple values are serialized as key=value.
    Complex values (like vec3/quat dictionaries) are serialized as key={"x":1,"y":2,"z":3}
    without unnecessary spacing.
    """
    parts = []
    for k, v in prop_dict.items():
        if isinstance(v, dict):
            v_str = json.dumps(v, separators=(',', ':'))
        else:
            v_str = str(v)
        parts.append(f"{k}={v_str}")
    return "; ".join(parts)


def write_prefabs_csv(json_path: Path, output_csv: Path):
    """Generates the prefabs CSV file from the JSON file by streaming ZDOs."""
    print("-> Streaming JSON and processing all prefab objects...")
    
    csv_headers = [
        "prefab_hash",
        "prefab_name",
        "position_x",
        "position_y",
        "position_z",
        "rotation_x",
        "rotation_y",
        "rotation_z",
        "rotation_w",
        "sector_x",
        "sector_y",
        "user_id",
        "zdo_id",
        "persistent",
        "type",
        "distant",
        "owner_revision",
        "data_revision",
        "user_key",
        "time_created",
        "floats",
        "vec3s",
        "quats",
        "ints",
        "longs",
        "strings",
        "bytes"
    ]

    total_zdos = 0

    with open(output_csv, "w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=csv_headers)
        writer.writeheader()

        for zdo in iterate_all_zdos(json_path):
            total_zdos += 1

            prefab_hash = zdo.get("prefabHash")
            if prefab_hash is None:
                prefab_hash = zdo.get("prefab")
            
            prefab_name = zdo.get("prefabName")
            if not prefab_name and prefab_hash is not None:
                prefab_name = str(prefab_hash)
            
            pos = zdo.get("position") or {}
            rot = zdo.get("rotation") or {}
            sec = zdo.get("sector") or {}

            # Property maps normalization and serialization
            floats_map = get_merged_properties(zdo, "floats", "floatsByName")
            
            # vec3s: check vec3s, vector3s, vector3sByName
            vec3s_map = {}
            for k in ("vec3s", "vector3s"):
                val = zdo.get(k)
                if isinstance(val, dict):
                    vec3s_map.update(val)
            val_by_name = zdo.get("vector3sByName")
            if isinstance(val_by_name, dict):
                vec3s_map.update(val_by_name)

            quats_map = get_merged_properties(zdo, "quats", "quatsByName")
            ints_map = get_merged_properties(zdo, "ints", "intsByName")
            longs_map = get_merged_properties(zdo, "longs", "longsByName")
            strings_map = get_merged_properties(zdo, "strings", "stringsByName")
            
            # bytes: check bytes, byteArrays, byteArraysByName
            bytes_map = {}
            for k in ("bytes", "byteArrays"):
                val = zdo.get(k)
                if isinstance(val, dict):
                    bytes_map.update(val)
            val_by_name = zdo.get("byteArraysByName")
            if isinstance(val_by_name, dict):
                bytes_map.update(val_by_name)

            # Handle persistent and distant conversions to lowercase strings
            persistent_val = zdo.get("persistent")
            if persistent_val is True:
                persistent_str = "true"
            elif persistent_val is False:
                persistent_str = "false"
            else:
                persistent_str = str(persistent_val) if persistent_val is not None else ""

            distant_val = zdo.get("distant")
            if distant_val is True:
                distant_str = "true"
            elif distant_val is False:
                distant_str = "false"
            else:
                distant_str = str(distant_val) if distant_val is not None else ""

            writer.writerow({
                "prefab_hash": prefab_hash if prefab_hash is not None else "",
                "prefab_name": prefab_name if prefab_name is not None else "",
                "position_x": pos.get("x", ""),
                "position_y": pos.get("y", ""),
                "position_z": pos.get("z", ""),
                "rotation_x": rot.get("x", ""),
                "rotation_y": rot.get("y", ""),
                "rotation_z": rot.get("z", ""),
                "rotation_w": rot.get("w", ""),
                "sector_x": sec.get("x", ""),
                "sector_y": sec.get("y", ""),
                "user_id": zdo.get("userID", ""),
                "zdo_id": zdo.get("zdoID", ""),
                "persistent": persistent_str,
                "type": zdo.get("type", ""),
                "distant": distant_str,
                "owner_revision": zdo.get("ownerRevision", ""),
                "data_revision": zdo.get("dataRevision", ""),
                "user_key": zdo.get("userKey", ""),
                "time_created": zdo.get("timeCreated", ""),
                "floats": serialize_property_map(floats_map),
                "vec3s": serialize_property_map(vec3s_map),
                "quats": serialize_property_map(quats_map),
                "ints": serialize_property_map(ints_map),
                "longs": serialize_property_map(longs_map),
                "strings": serialize_property_map(strings_map),
                "bytes": serialize_property_map(bytes_map)
            })

    print(f"-> Cataloged {total_zdos} prefabs / ZDOs!")
    print(f"-> Prefabs table saved to: '{output_csv}'")


# --- MAIN PIPELINE EXECUTIVE ---

def main():
    parser = argparse.ArgumentParser(
        description="Extract and catalog all items inside Valheim save/Rewind containers into a single CSV."
    )
    parser.add_argument(
        "input", 
        help="Path to the Valheim world save (.db), valheim-save-tools export (.json), or Rewind export (.json)"
    )
    parser.add_argument(
        "-o", "--output", 
        help="Output CSV path. Defaults to <input_name>_items.csv"
    )
    parser.add_argument(
        "--prefabs-output",
        help="Output CSV path for prefabs. Defaults to <input_name>_prefabs.csv"
    )
    parser.add_argument(
        "--jar", 
        default="valheim-save-tools.jar",
        help="Path to the 'valheim-save-tools.jar' CLI utility. Defaults to search in current directory."
    )
    parser.add_argument(
        "--keep-json", 
        action="store_true",
        help="If converting a .db or .rewind, keep the intermediate generated .json file."
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input file '{input_path}' does not exist.", file=sys.stderr)
        sys.exit(1)

    json_path = None
    is_temp_json = False

    # 1. Process World Save .db file or .rewind file if provided
    if input_path.suffix.lower() == ".db":
        if not shutil.which("java"):
            print("Error: 'java' is not installed or not in system PATH. Required to parse .db archives.", file=sys.stderr)
            sys.exit(1)

        jar_path = Path(args.jar)
        if not jar_path.exists():
            print(f"Error: '{jar_path}' tool was not found.", file=sys.stderr)
            print("Please download it from: https://github.com/Kakoen/valheim-save-tools/releases", file=sys.stderr)
            print("and place it in this folder, or specify its location with --jar <path>.", file=sys.stderr)
            sys.exit(1)

        temp_json_path = input_path.with_suffix(".json")
        print(f"-> Converting '{input_path.name}' to raw objects JSON via valheim-save-tools...")
        cmd = ["java", "-jar", str(jar_path), str(input_path), str(temp_json_path)]
        
        try:
            subprocess.run(cmd, check=True)
            print("-> Successfully generated intermediate JSON.")
            json_path = temp_json_path
            is_temp_json = True
        except subprocess.CalledProcessError as e:
            print(f"Error: Failed converting .db file: {e}", file=sys.stderr)
            sys.exit(1)
    elif input_path.suffix.lower() == ".rewind":
        script_dir = Path(__file__).resolve().parent
        rewind_script = script_dir / "parseRewind.py"
        if not rewind_script.exists():
            print(f"Error: '{rewind_script}' not found.", file=sys.stderr)
            sys.exit(1)

        temp_json_path = input_path.with_suffix(".json")
        print(f"-> Converting '{input_path.name}' to JSON via parseRewind.py...")
        cmd = [sys.executable, str(rewind_script), str(input_path)]
        
        try:
            subprocess.run(cmd, check=True)
            print("-> Successfully generated intermediate JSON.")
            json_path = temp_json_path
            is_temp_json = True
        except subprocess.CalledProcessError as e:
            print(f"Error: Failed converting .rewind file: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        json_path = input_path

    # Determine Output Names
    output_csv = Path(args.output) if args.output else input_path.with_name(f"{input_path.stem}_items.csv")
    output_prefabs_csv = Path(args.prefabs_output) if args.prefabs_output else input_path.with_name(f"{input_path.stem}_prefabs.csv")

    try:
        # 2. Extract and Catalog Prefabs (ZDOs)
        write_prefabs_csv(json_path, output_prefabs_csv)

        # 3. Extract and Catalog Items from Containers
        print("-> Streaming JSON and processing container objects...")
        
        csv_headers = [
            "container_prefab",
            "container_prefab_name",
            "container_x",
            "container_y",
            "container_z",
            "container_sector_x",
            "container_sector_y",
            "container_creator_id",
            "container_custom_name",
            "item_prefab",
            "item_stack",
            "item_durability",
            "item_grid_x",
            "item_grid_y",
            "item_quality",
            "item_variant",
            "item_crafter_id",
            "item_crafter_name",
            "item_custom_data"
        ]

        total_containers = 0
        total_items = 0

        with open(output_csv, "w", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=csv_headers)
            writer.writeheader()

            for zdo in iterate_zdos(json_path):
                # Search for the base64 items data blob in both resolved and unresolved ZDO fields
                items_blob = get_zdo_value(zdo, "strings", "items", HASH_ITEMS)
                if not items_blob:
                    continue

                parsed_items = parse_inventory(items_blob)
                if not parsed_items:
                    continue

                total_containers += 1
                total_items += len(parsed_items)

                # Extract container attributes (maps both 'prefab' and 'prefabHash')
                prefab_id = zdo.get("prefab") or zdo.get("prefabHash") or ""
                pos = zdo.get("position") or {}
                sec = zdo.get("sector") or {}
                creator = get_zdo_value(zdo, "longs", "creator", HASH_CREATOR)
                
                # Extract any custom tags/names given to the container (such as via chest labels)
                custom_name = (
                    get_zdo_value(zdo, "strings", "tag", HASH_TAG) or
                    get_zdo_value(zdo, "strings", "text", HASH_TEXT) or
                    get_zdo_value(zdo, "strings", "name", HASH_NAME) or
                    get_zdo_value(zdo, "strings", "custom_name", HASH_CUSTOM_NAME) or
                    ""
                )

                # Write item rows
                for item in parsed_items:
                    # Flatten any custom item components (such as epic loot stats or engravings)
                    flat_custom_data = "; ".join(f"{k}={v}" for k, v in item["custom_data"].items())

                    writer.writerow({
                        "container_prefab": prefab_id,
                        "container_prefab_name": zdo.get("prefabName", ""),
                        "container_x": pos.get("x", ""),
                        "container_y": pos.get("y", ""),
                        "container_z": pos.get("z", ""),
                        "container_sector_x": sec.get("x", ""),
                        "container_sector_y": sec.get("y", ""),
                        "container_creator_id": creator if creator is not None else "",
                        "container_custom_name": custom_name,
                        "item_prefab": item["prefab"],
                        "item_stack": item["stack"],
                        "item_durability": item["durability"],
                        "item_grid_x": item["x"],
                        "item_grid_y": item["y"],
                        "item_quality": item["quality"],
                        "item_variant": item["variant"],
                        "item_crafter_id": item["crafter_id"],
                        "item_crafter_name": item["crafter_name"],
                        "item_custom_data": flat_custom_data
                    })

        print(f"-> Cataloged {total_items} items across {total_containers} containers!")
        print(f"-> Master table saved to: '{output_csv}'")

    finally:
        # Cleanup temporary JSON if we generated it from a .db file
        if is_temp_json and json_path and json_path.exists() and not args.keep_json:
            os.remove(json_path)
            print("-> Cleaned up temporary JSON file.")

if __name__ == "__main__":
    main()