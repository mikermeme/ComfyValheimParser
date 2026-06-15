import csv
import json
import struct
import sys
import os
import re
import base64

ITEMS_HASH = 3356102854

class Reader:
    def __init__(self, fp):
        self.fp = fp

    def read(self, n):
        return self.fp.read(n)

    def skip(self, n):
        self.fp.seek(n, 1)

    def u8(self):
        return struct.unpack("<B", self.read(1))[0]

    def s8(self):
        return struct.unpack("<b", self.read(1))[0]

    def u16(self):
        return struct.unpack("<H", self.read(2))[0]

    def u32(self):
        return struct.unpack("<I", self.read(4))[0]

    def s32(self):
        return struct.unpack("<i", self.read(4))[0]

    def u64(self):
        return struct.unpack("<Q", self.read(8))[0]

    def s64(self):
        return struct.unpack("<q", self.read(8))[0]

    def f32(self):
        return struct.unpack("<f", self.read(4))[0]

    def tell(self):
        return self.fp.tell()


def read_leb128(r):
    value = 0
    shift = 0
    while True:
        b = r.u8()
        value |= (b & 0x7F) << shift
        if not (b & 0x80):
            break
        shift += 7
    return value


def u32_to_signed(v):
    return struct.unpack("<i", struct.pack("<I", v))[0]


def strip_comments(text):
    # Strip multi-line comments
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
    # Strip single-line comments
    text = re.sub(r'//.*', '', text)
    return text


def load_hexpat_mappings(hexpat_file):
    """
    Parses enums from rewind.hexpat to resolve ZDO variables and Prefabs.
    Resolves signed 32-bit hashes matching standard Valheim save files.
    """
    zdo_vars = {}
    prefabs = {}
    
    if not os.path.exists(hexpat_file):
        return zdo_vars, prefabs

    try:
        with open(hexpat_file, "r", encoding="utf-8") as f:
            content = strip_comments(f.read())
            
        enum_blocks = re.findall(r'enum\s+(\w+)\s*:\s*\w+\s*\{([^}]+)\}', content)
        for enum_name, enum_body in enum_blocks:
            for line in enum_body.split('\n'):
                line = line.strip()
                if not line:
                    continue
                match = re.match(r'(\w+)\s*=\s*(0x[0-9a-fA-F]+|\d+)', line)
                if match:
                    var_name = match.group(1)
                    var_val_str = match.group(2)
                    var_val = int(var_val_str, 16) if var_val_str.startswith('0x') else int(var_val_str, 10)
                    signed_val = u32_to_signed(var_val)
                    
                    if enum_name == "ZDOVar":
                        # Prefer names without 's_' prefix if we have duplicates (e.g. s_items vs items)
                        existing = zdo_vars.get(signed_val)
                        if not existing or (existing.startswith('s_') and not var_name.startswith('s_')):
                            zdo_vars[signed_val] = var_name
                    elif enum_name == "Prefab":
                        prefabs[signed_val] = var_name
        print(f"Loaded {len(zdo_vars)} variables and {len(prefabs)} prefabs from {hexpat_file}")
    except Exception as e:
        print(f"Warning: Failed to load hexpat enums: {e}")
        
    return zdo_vars, prefabs


def load_prefabs(csv_file):
    prefabs = {}
    if not os.path.exists(csv_file):
        return prefabs
    with open(csv_file, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                signed = int(row["prefab_hash_signed"])
                prefabs[signed] = row["prefab_name"]
            except Exception:
                pass
    return prefabs


def read_vector3(r):
    return {"x": r.f32(), "y": r.f32(), "z": r.f32()}


def read_quaternion(r):
    return {"x": r.f32(), "y": r.f32(), "z": r.f32(), "w": r.f32()}


def read_vector2i(r):
    return {"x": r.s32(), "y": r.s32()}


def read_string_entry(r):
    var_hash = r.u32()
    length = read_leb128(r)
    raw = r.read(length)
    try:
        value = raw.decode("utf-8")
    except:
        value = raw.decode("utf-8", errors="replace")
    return var_hash, value


def dump_rewind(rewind_file, prefab_csv, output_json, hexpat_file="rewind.hexpat"):
    # Resolve enums from hexpat if available
    zdo_vars, hexpat_prefabs = load_hexpat_mappings(hexpat_file)

    # Resolve enums from CSV prefabs and merge
    prefab_map = hexpat_prefabs.copy()
    csv_prefabs = load_prefabs(prefab_csv)
    prefab_map.update(csv_prefabs)

    results = []

    with open(rewind_file, "rb") as f:
        r = Reader(f)

        header = {
            "magic": r.u32(),
            "count": r.u32(),
            "offset": read_vector3(r)
        }

        print("ZDO count:", header["count"])

        for index in range(header["count"]):
            zdo = {}
            current_offset = r.tell()

            try:
                zdo["userID"] = r.u64()
                zdo["zdoID"] = r.u32()

                r.skip(6)

                zdo["ownerRevision"] = r.u16()
                zdo["dataRevision"] = r.u32()
                zdo["persistent"] = bool(r.u8())

                zdo["userKey"] = r.s64()
                zdo["timeCreated"] = r.s64()
                zdo["zero"] = r.u32()

                zdo["type"] = r.s8()
                zdo["distant"] = bool(r.u8())

                prefab_u32 = r.u32()
                prefab_signed = u32_to_signed(prefab_u32)

                zdo["prefabHash"] = prefab_signed
                zdo["prefabName"] = prefab_map.get(prefab_signed, str(prefab_signed))

                zdo["sector"] = read_vector2i(r)
                zdo["position"] = read_vector3(r)
                zdo["rotation"] = read_quaternion(r)

                floats = {}
                vec3s = {}
                quats = {}
                ints = {}
                longs = {}
                strings = {}
                bytes_dict = {}

                # 1. Floats
                count = r.u8()
                for _ in range(count):
                    h = r.u32()
                    v = r.f32()
                    key_signed = u32_to_signed(h)
                    key_str = zdo_vars.get(key_signed, str(key_signed))
                    floats[key_str] = v

                # 2. Vec3s
                count = r.u8()
                for _ in range(count):
                    h = r.u32()
                    v = read_vector3(r)
                    key_signed = u32_to_signed(h)
                    key_str = zdo_vars.get(key_signed, str(key_signed))
                    vec3s[key_str] = v
                    # Legacy compatibility fallback for scripts expecting it inside strings
                    strings[f"vec3:{key_signed}"] = v

                # 3. Quats
                count = r.u8()
                for _ in range(count):
                    h = r.u32()
                    v = read_quaternion(r)
                    key_signed = u32_to_signed(h)
                    key_str = zdo_vars.get(key_signed, str(key_signed))
                    quats[key_str] = v
                    # Legacy compatibility fallback for scripts expecting it inside strings
                    strings[f"quat:{key_signed}"] = v

                # 4. Ints
                count = r.u8()
                for _ in range(count):
                    h = r.u32()
                    v = r.s32()  # Read as signed 32-bit int
                    key_signed = u32_to_signed(h)
                    key_str = zdo_vars.get(key_signed, str(key_signed))
                    ints[key_str] = v

                # 5. Longs
                count = r.u8()
                for _ in range(count):
                    h = r.u32()
                    v = r.s64()  # Read as signed 64-bit int
                    key_signed = u32_to_signed(h)
                    key_str = zdo_vars.get(key_signed, str(key_signed))
                    longs[key_str] = v

                # 6. Strings
                count = r.u8()
                for _ in range(count):
                    h, v = read_string_entry(r)
                    key_signed = u32_to_signed(h)
                    key_str = zdo_vars.get(key_signed, str(key_signed))
                    strings[key_str] = v

                # 7. Bytes (Consumed to prevent parser desync)
                byte_count = r.u8()
                for _ in range(byte_count):
                    h = r.u32()
                    length = r.u32()
                    v = r.read(length)
                    key_signed = u32_to_signed(h)
                    key_str = zdo_vars.get(key_signed, str(key_signed))
                    # Serialize as Base64 to match standard JSON serialization
                    bytes_dict[key_str] = base64.b64encode(v).decode('utf-8')

                zdo["floats"] = floats
                zdo["vec3s"] = vec3s
                zdo["quats"] = quats
                zdo["ints"] = ints
                zdo["longs"] = longs
                zdo["strings"] = strings
                if bytes_dict:
                    zdo["bytes"] = bytes_dict

                results.append(zdo)

            except Exception as e:
                print(f"Error parsing ZDO index {index} at offset {hex(current_offset)}: {e}")
                raise e

    # Format output to perfectly match standard valheim-save-tools schema
    output_data = {
        "type": "DB",
        "zdoList": {
            "zdos": results
        }
    }

    with open(output_json, "w", encoding="utf-8") as out:
        json.dump(output_data, out, indent=2, ensure_ascii=False)

    print(f"Parsed {len(results)} ZDOs successfully.")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python rewind_dump.py world.rewind prefabs.csv output.json")
        sys.exit(1)

    # Looks for rewind.hexpat in the folder where the dump script lives
    script_dir = os.path.dirname(os.path.abspath(__file__))
    hexpat_path = os.path.join(script_dir, "rewind.hexpat")
    if not os.path.exists(hexpat_path):
        hexpat_path = "rewind.hexpat"

    dump_rewind(
        sys.argv[1],
        sys.argv[2],
        sys.argv[3],
        hexpat_file=hexpat_path
    )