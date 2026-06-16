# `.rewind` Binary Format Specification

This document describes the binary file format used by the [Rewind](https://valheim.thunderstore.io/package/Smoothbrain/Rewind/) Valheim mod for saving and loading builds. The format stores serialized ZDO (Zone Data Object) records — Valheim's fundamental unit of world state.

This specification was reverse-engineered from the `rewind.hexpat` ImHex pattern file and the Python parsing scripts in this repository.

---

## Table of Contents

- [Overview](#overview)
- [Byte Order](#byte-order)
- [File Structure](#file-structure)
  - [File Header](#file-header)
  - [ZDO Record](#zdo-record)
  - [Property Arrays](#property-arrays)
- [Data Types](#data-types)
  - [Primitive Types](#primitive-types)
  - [Composite Types](#composite-types)
  - [LEB128 Encoding](#leb128-encoding)
- [Hash Resolution](#hash-resolution)
  - [Prefab Hashes](#prefab-hashes)
  - [ZDO Variable Hashes](#zdo-variable-hashes)
  - [Valheim's GetStableHashCode Algorithm](#valheims-getstablehashcode-algorithm)
- [Inventory Blob Format](#inventory-blob-format)
- [Reference Files](#reference-files)

---

## Overview

A `.rewind` file is a flat binary container holding a list of ZDO records. Each ZDO represents a game object in the Valheim world (a building piece, container, creature, terrain modification, etc.) and contains:

- **Identity**: who owns it, what prefab type it is
- **Spatial data**: position, rotation, and world sector
- **Properties**: typed key-value maps (floats, vectors, quaternions, ints, longs, strings, byte arrays)

The format uses **no compression** and has **no index/offset table** — records must be read sequentially from start to finish.

---

## Byte Order

All multi-byte values are stored in **little-endian** byte order, consistent with Unity/C# conventions on x86 platforms.

---

## File Structure

### File Header

The file begins with a fixed-size header:

| Offset | Size | Type | Field | Description |
|--------|------|------|-------|-------------|
| `0x00` | 4 | `u32` | `magic` | Magic number / format identifier. Observed value: `0x0000001D` (29) |
| `0x04` | 4 | `u32` | `count` | Total number of ZDO records in the file |
| `0x08` | 12 | `Vector3` | `offset` | World-space origin offset (x, y, z as 3× `float32`) |

**Total header size: 20 bytes**

The `offset` field stores the reference point used when the build was saved — typically the player position or pin position at save time. When loading a build, the Rewind mod uses this to calculate relative positions for relocation.

---

### ZDO Record

Each ZDO record immediately follows the header (or the previous ZDO). Records are variable-length due to the dynamic property arrays.

#### Fixed Header

| Offset (relative) | Size | Type | Field | Description |
|-------------------|------|------|-------|-------------|
| `+0` | 8 | `u64` | `userID` | Steam ID of the player who owns this ZDO |
| `+8` | 4 | `u32` | `zdoID` | Unique ZDO identifier within the world |
| `+12` | 6 | — | *(padding)* | 6 bytes of reserved/padding data (skipped) |
| `+18` | 2 | `u16` | `ownerRevision` | Version counter for ownership changes |
| `+20` | 4 | `u32` | `dataRevision` | Version counter for data changes |
| `+24` | 1 | `bool` | `persistent` | Whether this ZDO survives world saves |
| `+25` | 8 | `s64` | `userKey` | Secondary user identifier / session key |
| `+33` | 8 | `s64` | `timeCreated` | Creation timestamp (game ticks) |
| `+41` | 4 | `u32` | `zero` | Reserved field (always 0) |
| `+45` | 1 | `s8` | `type` | ZDO type category |
| `+46` | 1 | `bool` | `distant` | Whether this is a "distant" object (rendered at distance) |
| `+47` | 4 | `u32` | `prefab` | Prefab hash identifying the game object type |
| `+51` | 8 | `Vector2i` | `sector` | World sector coordinates (x, y as 2× `s32`) |
| `+59` | 12 | `Vector3` | `position` | World position (x, y, z as 3× `float32`) |
| `+71` | 16 | `Quaternion` | `rotation` | Rotation (x, y, z, w as 4× `float32`) |

**Fixed header size: 87 bytes**

#### Property Arrays

Immediately following the fixed header, seven property arrays are stored sequentially. Each array is prefixed by a `u8` count, followed by that many entries.

##### 1. Floats

```
u8          count
Entry[count]:
    u32     variableHash    // ZDOVar enum hash
    float   value           // 32-bit IEEE 754 float
```

Common float properties: `health`, `durability`, `fuel`, `stamina`

##### 2. Vector3s

```
u8          count
Entry[count]:
    u32     variableHash
    Vector3 value           // 3× float (x, y, z) = 12 bytes
```

Common Vector3 properties: `spawnPoint`, `hitDir`, `bodyVelocity`

##### 3. Quaternions

```
u8          count
Entry[count]:
    u32     variableHash
    Quaternion value        // 4× float (x, y, z, w) = 16 bytes
```

Common Quaternion properties: `tiltrot`, rotation overrides

##### 4. Integers

```
u8          count
Entry[count]:
    u32     variableHash
    s32     value           // Signed 32-bit integer
```

Common int properties: `level`, `quality`, `addedDefaultItems`, `state`

##### 5. Longs

```
u8          count
Entry[count]:
    u32     variableHash
    s64     value           // Signed 64-bit integer
```

Common long properties: `creator` (Steam ID), `crafterID`, `timeOfDeath`

##### 6. Strings

```
u8          count
Entry[count]:
    u32     variableHash
    LEB128  length          // String byte length (variable-size encoded)
    char[length] value      // UTF-8 encoded string
```

Common string properties: `items` (base64-encoded inventory blob), `tag`, `text`, `tamedName`

> **Important**: The `items` string property contains a base64-encoded binary blob that holds the full inventory of a container. See [Inventory Blob Format](#inventory-blob-format) for details on decoding it.

##### 7. Byte Arrays

```
u8          count
Entry[count]:
    u32     variableHash
    u32     length          // Byte array length (fixed 4-byte, NOT LEB128)
    byte[length] value      // Raw bytes
```

> **Note**: The byte array count and length fields are read but the data is typically opaque. The earlier "workingish" parser script did not consume the byte array data, which caused parser desynchronization on subsequent ZDOs. The "fully working" parser correctly reads and skips these bytes.

---

## Data Types

### Primitive Types

| Name | Size | Format (`struct`) | Description |
|------|------|-------------------|-------------|
| `u8` | 1 | `<B` | Unsigned 8-bit integer |
| `s8` | 1 | `<b` | Signed 8-bit integer |
| `u16` | 2 | `<H` | Unsigned 16-bit integer |
| `u32` | 4 | `<I` | Unsigned 32-bit integer |
| `s32` | 4 | `<i` | Signed 32-bit integer |
| `u64` | 8 | `<Q` | Unsigned 64-bit integer |
| `s64` | 8 | `<q` | Signed 64-bit integer |
| `float` | 4 | `<f` | IEEE 754 single-precision float |
| `bool` | 1 | `<?` | Boolean (0 = false, non-zero = true) |

### Composite Types

| Name | Size | Fields |
|------|------|--------|
| `Vector2i` | 8 | `{ s32 x, s32 y }` |
| `Vector3` | 12 | `{ float x, float y, float z }` |
| `Quaternion` | 16 | `{ float x, float y, float z, float w }` |

### LEB128 Encoding

String lengths in the Strings property array use **LEB128** (Little-Endian Base 128) variable-length encoding — the same encoding .NET uses for `BinaryWriter.Write(string)`.

**Decoding algorithm:**

```
result = 0
shift = 0
loop:
    byte = read_u8()
    result |= (byte & 0x7F) << shift
    if (byte & 0x80) == 0:
        return result
    shift += 7
```

This allows compact encoding: values 0–127 use 1 byte, 128–16383 use 2 bytes, etc.

---

## Hash Resolution

### Prefab Hashes

The `prefab` field in each ZDO is a 32-bit hash that identifies the game object type. These can be resolved to human-readable names using two sources:

1. **`prefabs.csv`** — A CSV file with columns `prefab_hash_signed`, `prefab_hash_hex`, and `prefab_name`:
   ```
   prefab_hash_signed,prefab_hash_hex,prefab_name
   -1443983522,0xA9E39B5E,piece_chest
   600954715,0x23D1884B,TreasureChest_meadows
   ```

2. **`rewind.hexpat`** — Contains a `Prefab` enum (starting at line ~10302) with ~10,000 entries mapping unsigned hex hashes to names.

### ZDO Variable Hashes

Each property key (`variableHash`) is also a 32-bit hash. These are resolved using the `ZDOVar` enum in `rewind.hexpat` (starting at line 129), which contains ~10,000 entries mapping hashes to variable names like `s_items`, `s_health`, `s_creator`, etc.

### Valheim's GetStableHashCode Algorithm

Valheim uses a custom deterministic hash function (not .NET's `GetHashCode()`) to generate stable 32-bit signed integer hashes from strings. The algorithm:

```python
def get_stable_hash_code(s: str) -> int:
    """Replicates Valheim's GetStableHashCode for strings."""
    hash_val = 5381
    for char in s:
        hash_val = ((hash_val << 5) + hash_val) ^ ord(char)
        hash_val = hash_val & 0xFFFFFFFF  # Keep as 32-bit unsigned
    # Convert to signed 32-bit integer
    if hash_val >= 0x80000000:
        hash_val -= 0x100000000
    return hash_val
```

This is a variant of the **djb2** hash algorithm (Daniel J. Bernstein). The result is always a signed 32-bit integer. For example:

| String | Hash (signed) | Hash (hex) |
|--------|--------------|------------|
| `items` | 179721187 | `0x0AB66BE3` |
| `creator` | -374753447 | `0xE9A22369` |
| `health` | 1581283705 | `0x5E41B579` |

In the binary format, hashes are stored as **unsigned** 32-bit integers. The scripts convert them to signed representation for lookup against `prefabs.csv` and the `ZDOVar` enum.

---

## Inventory Blob Format

Container ZDOs store their inventory as a **base64-encoded binary blob** in the `items` string property. After base64 decoding, the blob has the following structure:

### Inventory Header

| Offset | Size | Type | Field | Description |
|--------|------|------|-------|-------------|
| `0x00` | 4 | `s32` | `version` | Inventory serialization version |
| `0x04` | 4 | `s32` | `itemCount` | Number of items in the inventory |

### Item Record (repeated `itemCount` times)

| Order | Type | Field | Description |
|-------|------|-------|-------------|
| 1 | `LEB128 + char[]` | `prefab` | Item type name (e.g., `"SwordIron"`) |
| 2 | `s32` | `stack` | Stack count |
| 3 | `float` | `durability` | Current durability |
| 4 | `s32` | `x` | Grid X position in the container |
| 5 | `s32` | `y` | Grid Y position in the container |
| 6 | `bool` | `equipped` | Whether the item is equipped (for player inventories) |
| 7 | `s32` | `quality` | Upgrade level / quality tier |
| 8 | `s32` | `variant` | Visual variant index |
| 9 | `s64` | `crafterID` | Steam ID of the crafter |
| 10 | `LEB128 + char[]` | `crafterName` | Display name of the crafter |
| 11 | `s32` | `customDataCount` | Number of custom key-value pairs |
| 12 | *(repeated)* | `customData` | `customDataCount` × { `LEB128+string key`, `LEB128+string value` } |
| 13 | `s32` | `worldLevel` | World level at time of creation |
| 14 | `bool` | `pickedUp` | Whether the item has been picked up |

Strings within the inventory blob use the same LEB128-prefixed encoding as .NET's `BinaryReader.ReadString()`: a LEB128-encoded byte length followed by that many bytes of UTF-8 text.

---

## Reference Files

| File | Description |
|------|-------------|
| [`rewind.hexpat`](../rewind.hexpat) | ImHex pattern file — the authoritative source for enum definitions and struct layouts. Open with [ImHex](https://imhex.werwolv.net/) to visually inspect `.rewind` files. |
| [`prefabs.csv`](../prefabs.csv) | Prefab hash → name lookup table (~3,500 entries). Exported from game data. |
| [`parseRewind.py`](../rewind_dump%20-%20fully%20working.py) | Reference Python implementation of this specification. |
| [`parseItems.py`](../parseItems.py) | Contains the inventory blob parser implementation. |
