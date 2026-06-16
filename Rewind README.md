# Rewind

*Save and load ZDOs to/from files.*

## Load Build

*Arguments in brackets are optional.*

    loadbuild                               lb
       --filename=<filename>                   --fn=<filename>
      [--buildorigin]                         [--bo]
      [--buildrotation]                       [--br]
      [--position=<x,y,z>]                    [--pos=<x,y,z>]
      [--rotation=<x,y,z>]                    [--rot=<x,y,z>]
      [--translate=<x,y,z>]                   [--t=<x,y,z>]
      [--ignore=<prefab1,prefab2>]            [--ig=<prefab1,prefab2>]
      [--include=<prefab1,prefab2>]           [--in=<prefab1,prefab2>]
      [--dry-run]                             [--dr]
      [--log-zdos=<filename>]                 [--logz=<filename>]
      [--filter-mobs=<matching|nonmatching>]
      [--use-pin-position]

  * `--filter-mobs=<matching|nonmatching>`
    * `matching` -- Mobs will **not** be loaded.
    * `nonmatching` -- **Only mobs** will be loaded.
    *  Mobs are prefabs that have a `Character` or `Humanoid` component.
  * `--use-pin-position`
    * Will override `--position` with the position of the placed pin.

### load-build-at-pin

    load-build-at-pin
      (see loadbuild)

  * Wrapper for `loadbuild` command that automatically adds `--use-pin-position` arg.

## Save Build

    savebuild                         sb
       --filename=<filename>             --fn=<filename>
       --radius=<123>                    --r=<123>
      [--origin=<x,y,z>]                [--o=<x,y,z>]
      [--timestamp=<none|epoch|iso>]    [--ts=<none|epoch|iso>]

  * `--timestamp` when specified will append the current timestamp to the filename.
    * `none` -- no timestamp will be appended.
    * `epoch` -- timestamp will be in seconds since epoch (`1767225599`).
    * `iso` -- timestamp will be formatted as `YYYYMMDDTHHMMMSSZ` (`20251231T235959Z`).
  * If using `--timestamp`, you should specify `--filename` using quotes and ending in a separator.
      * `--filename="apple-"`
      * `--filename="banana_"`

## Randomize Filename

  * When using `/loadbuild` or `/load-build-at-pin` you can now add randomized numbers anywhere in the filename.
  * When specifying `--filename=<text>`, anywhere in `<text>` you can put in `{!roll ...}` in one of three ways.
  * Any match of `{!roll ...}` will be replaced with a randomized number (see below).
  * The regex matching requires `{!roll}` to start and a `}` to end.
  * You MUST include `--roll-regex` to the command to toggle the new behaviour.
  * Invalid `--filename` values will throw an error.

### Roll from 1 to N

  * `--filename="abcde{!roll <N>}" --roll-regex`
  * Rolls from `1` to `<N>` (inclusive) to replace for match
  * `<N>` must be a positive integer >= `2`

### Roll X dice with Y faces

  * `--filename="abcde{!roll <X>d<Y>}" --roll-regex`
  * Rolls `X` dice with `Y` faces, uses result to replace for match

### Roll between a range

  * `--filename="abcd{!roll <start>,<end>}aaaaa" --roll-regex`
  * Rolls between `<start>` and `<end>` (inclusive) to replace for match
  * `<start>` and `<end>` must be integers, can be negative; (comma is used to separate)

### Tips

* Put `"` around the filename argument to help with the args parsing
* Can have multiple `{!roll}` of any kind like:
  * `TEST{!roll 10}THIS{!roll 3d10}OUT{!roll -5,15}.rewind`

## Pin (RadiusSphere)

*Arguments in brackets are optional.*

    pinorigin                 pin
      [--radius=<123.45>]       [--r=<123.45>]
      [--position=<x,y,z>]      [--pos=<x,y,z>]
      [--rotation=<x,y,z>]      [--rot=<x,y,z>]

    unpin

    showradius                showr
      [--radius=<123.45>]       [--r=<123.45>]
      [--position=<x,y,z>]      [--pos=<x,y,z>]
      [--rotation=<x,y,z>]      [--rot=<x,y,z>]

## BoundsCube

### Show a BoundsCube

*Arguments in brackets are optional.*

    showcube                  showc
      [--bounds=<x,y,z>]        [--b=<x,y,z>]
      [--position=<x,y,z>]      [--pos=<x,y,z>]
      [--rotation=<x,y,z>]      [--rot=<x,y,z>]
      [--sector]

  * `--sector` replaces all other arguments to create a bounds covering the current sector.

### Hide any existing BoundsCube

    hidecube                  hidec

### Save a build using the ZDOs within the BoundsCube

    savecube                          savec
       --filename=<abc>                  --fn=<abc>
      [--timestamp=<none|epoch|iso>]    [--ts=<none|epoch|iso>]

  * `--timestamp` when specified will append the current timestamp to the filename.
    * `none` -- no timestamp will be appended.
    * `epoch` -- timestamp will be in seconds since epoch (`1767225599`).
    * `iso` -- timestamp will be formatted as `YYYYMMDDTHHMMMSSZ` (`20251231T235959Z`).
  * If using `--timestamp`, you should specify `--filename` using quotes and ending in a separator.
      * `--filename="apple-"`
      * `--filename="banana_"`

### Delete all ZDOs within the BoundsCube

*Arguments in brackets are optional.*

    clearcube                 clearc
      [--ignore=<prefab1>]      [--ig=<prefab1>]

### Place BoundsCube using the Build Hammer

  * **Added `BoundsCube` prefab to the BuildHammer right next to the `Pin` prefab.**
  * Can be moved/rotated/scaled and will snap using the center of the cube.
  * On placement will move/replace current BoundsCube (and hide any existing Pin sphere).
  * To hide it, use the `/hidecube` command.

### BoundsCube Panel 

  * Whenever a BoundsCube is shown a small panel will display the position, rotation, scale and ZDOs to be saved inside.
  * Panel will be hidden when the cube is hidden.
