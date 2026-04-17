# Modulab Modules (PyLabware Wrappers)

This directory contains Modulab wrapper modules for PyLabware device drivers.

- One module file per device model.
- Shared runtime helper in `_pylabware_common.py`.
- Discovery/import entrypoint: `DRIVER_TEMPLATE` in each wrapper file.

## Recommended Modulab source path

Add this repository root as a Modulab source. The coordinator now filters source scans to `.py` files that include `DRIVER_TEMPLATE`, so non-module package files are ignored during module import.

## Verified smoke result

Validated against coordinator source handlers:

- Discover found 13 module files.
- Metadata extraction succeeded for all 13 wrappers.
- Source add initial import processed 13 wrappers with 0 errors.

Use this path when adding a local source:

`/home/jakub/projects/roschem_suite_with_coord_db/workspace/external_sources/pylabware_modulab_wrappers/modulab_modules`

