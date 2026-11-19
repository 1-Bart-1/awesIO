### Changed

- BREAKING: materials moved from a structure file to its system file. `system_schema.yml` has a `materials` list, and a tether, wing or bridle names a material from it rather than nesting one; a tether's `density` is its material's. `structure_schema.yml` has no `materials` table, and its `material` columns name a material of the system. `assembly`, `kites` and `ground_station` of a system file are now optional.
- BREAKING: a structure's `metadata` requires `system`, the system file it discretises, and `system_sha`, the hash of that file and every file it pulls in with `!include`, which `awesio.validator.system_sha` computes.
- BREAKING: a tether's segments leave `diameter` null, since the system's tether owns it, and any reference in a structure, a tool's own column included, is by name and never by row number.
- `validate` given a structure loads its system and refuses a hash that does not match, a document that is not a system, a material or tether name that does not resolve, a tether naming a segment the structure lacks, a tether segment of another material or giving a diameter of its own, and rest lengths that do not add up to the tether's length; its new `system` keyword names the system file of a structure passed as a dictionary, or in place of the one a structure names. A system file refuses a tether defined twice, as it does a material.

### Added

- A V3 system file, a fixed-wing structure and a double-skin ram-air structure with its system file, under `examples/`.
