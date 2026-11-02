from __future__ import annotations

from pathlib import Path, PosixPath, WindowsPath
from referencing import Registry, Resource
from referencing.exceptions import NoSuchResource
import copy
import hashlib
import jsonschema
import jsonschema.validators
import math
import warnings

from .yaml import load_yaml
from .schemas import schemaPath, schema_validation_error_formatter


def retrieve_yaml(uri: str):
    if not uri.endswith(".yaml"):
        raise NoSuchResource(ref=uri)
    uri = uri.removeprefix("src/awesio/")
    path = schemaPath / Path(uri)
    contents = load_yaml(path)
    return Resource.from_contents(contents)


registry = Registry(retrieve=retrieve_yaml)

TOLERANCE = 1e-9  # relative, for floats a writer summed or printed


def rows_match_headers(validator, enabled, instance, schema):
    """The `rowsMatchHeaders` keyword: the units and every row of a headers/units/data
    table are as long as its headers."""
    if not (enabled and validator.is_type(instance, "object")):
        return
    headers = instance.get("headers")
    if not validator.is_type(headers, "array"):
        return
    units, rows = instance.get("units"), instance.get("data")
    if validator.is_type(units, "array") and len(units) != len(headers):
        yield jsonschema.ValidationError(
            f"{len(units)} units for {len(headers)} headers", path=["units"]
        )
    if not validator.is_type(rows, "array"):
        return
    for i, row in enumerate(rows):
        if validator.is_type(row, "array") and len(row) != len(headers):
            yield jsonschema.ValidationError(
                f"row has {len(row)} columns for {len(headers)} headers", path=["data", i]
            )


def optional_columns(validator, columns, instance, schema):
    """The `optionalColumns` keyword: a column of a headers/units/data table under a
    header it names has the unit and the values it gives that header, wherever the
    column stands."""
    if not validator.is_type(instance, "object"):
        return
    headers, units, rows = (instance.get(key) for key in ("headers", "units", "data"))
    if not validator.is_type(headers, "array"):
        return
    for i, header in enumerate(headers):
        column = columns.get(header) if validator.is_type(header, "string") else None
        if column is None:
            continue
        unit = units[i] if validator.is_type(units, "array") and i < len(units) else None
        if unit is not None and unit != column["unit"]:
            yield jsonschema.ValidationError(
                f"{header} is in {column['unit']!r}, not {unit!r}", path=["units", i]
            )
        for row_number, row in enumerate(rows if validator.is_type(rows, "array") else []):
            if not (validator.is_type(row, "array") and i < len(row)):
                continue
            for error in validator.descend(row[i], column["value"], path=i):
                error.path.extendleft([row_number, "data"])
                yield error


def table_rows(document: dict, block: str) -> list[dict]:
    """The rows of a headers/units/data table as mappings by header; none if it is absent."""
    table = document.get(block, {"headers": [], "data": []})
    return [dict(zip(table["headers"], row)) for row in table["data"]]


def system_errors(system: dict) -> list[str]:
    """What a system document gets wrong that its schema cannot say: a material defined
    twice, or a tether, wing or bridle naming a material it does not define."""
    names = [material["name"] for material in system["materials"]]
    errors = [f"material {name!r} is defined twice"
              for name in sorted({name for name in names if names.count(name) > 1})]
    components = system["components"]
    kites = components.get("kites", [])
    parts = [*components["tethers"], *(kite["wing"] for kite in kites),
             *(kite["bridle"] for kite in kites if "bridle" in kite)]
    for part in parts:
        material = part["structure"].get("material")
        if material is not None and material not in names:
            errors.append(f"{part['name']!r} names material {material!r}, not in the system")
    return errors


def structure_errors(structure: dict, system: dict) -> list[str]:
    """Where a structure disagrees with the system it discretises: a material or tether
    name that does not resolve, a tether segment not of the tether's diameter, or rest
    lengths not adding up to the tether's length. A column left out states nothing."""
    materials = {material["name"] for material in system["materials"]}
    errors = []
    for block, column in (("segments", "material"), ("tubes", "material"),
                          ("wings", "canopy_material")):
        for row in table_rows(structure, block):
            material = row.get(column)
            if material is not None and material not in materials:
                errors.append(
                    f"{block} row {row['name']!r} names material {material!r}, "
                    "not in the system"
                )
    tethers = {tether["name"]: tether["structure"]
               for tether in system["components"]["tethers"]}
    segments = {row["name"]: row for row in table_rows(structure, "segments")}
    for row in table_rows(structure, "tethers"):
        name = row["name"]
        if name not in tethers:
            errors.append(f"tether {name!r} is not in the system")
            continue
        members = [segments[member] for member in row["segments"] if member in segments]
        errors += tether_errors(name, tethers[name], members)
    return errors


def tether_errors(name: str, tether: dict, segments: list[dict]) -> list[str]:
    """Where a tether's segments disagree with the system's diameter and length of it."""
    errors = [
        f"tether {name!r} segment {segment['name']!r} has diameter "
        f"{segment['diameter']}, the system says {tether['diameter']}"
        for segment in segments
        if "diameter" in segment and "diameter" in tether
        and not math.isclose(segment["diameter"], tether["diameter"], rel_tol=TOLERANCE)
    ]
    if all("rest_length" in segment for segment in segments):
        total = sum(segment["rest_length"] for segment in segments)
        if not math.isclose(total, tether["length"], rel_tol=TOLERANCE):
            errors.append(
                f"tether {name!r} segments add up to {total} m, "
                f"the system says {tether['length']} m"
            )
    return errors


def check_against_system(structure: dict, system_path: Path) -> None:
    """Raise a ValueError unless the file at `system_path` is the valid system whose hash
    `structure` quotes, and `structure` agrees with it."""
    if not system_path.is_file():
        raise ValueError(f"system file {system_path} not found")
    digest = hashlib.sha256(system_path.read_bytes()).hexdigest()
    if digest != structure["metadata"]["system_sha"]:
        raise ValueError(
            f"metadata.system_sha is {structure['metadata']['system_sha']}, "
            f"but {system_path} hashes to {digest}"
        )
    system = load_yaml(system_path)
    check_document(system, load_schema(system))
    errors = structure_errors(structure, system)
    if errors:
        raise ValueError("\n".join(errors))


def _enforce_no_additional_properties(schema):
    """Recursively set additionalProperties: false for all objects in the schema"""
    if isinstance(schema, dict):

        # If this is an object type schema, and additionalProperties is not specified,
        #   set additionalProperties: false
        if (schema.get("type") == "object" or "properties" in schema
        ) and "additionalProperties" not in schema:
            schema["additionalProperties"] = False

        # Recursively process all nested schemas
        for key, value in schema.items():
            if key == "properties":
                # Process each property's schema
                for prop_schema in value.values():
                    _enforce_no_additional_properties(prop_schema)
            elif key in ["items", "additionalItems"]:
                # Process array item schemas
                _enforce_no_additional_properties(value)
            elif key in ["oneOf", "anyOf", "allOf"]:
                # Process each subschema in these combining keywords
                for subschema in value:
                    _enforce_no_additional_properties(subschema)
    return schema


def load_schema(data: dict, restrictive: bool = False) -> dict:
    """The schema `data` names in `metadata.schema`.

    Raises:
        FileNotFoundError: If the schema file is not found.
        ValueError: If `data` has no `metadata.schema`.
    """
    # Auto-detect schema_type from metadata
    if "metadata" not in data or "schema" not in data["metadata"]:
        raise ValueError(
            "Schema type could not be automatically determined. "
            "The input data must contain 'metadata.schema' field."
        )
    schema_filename = data["metadata"]["schema"]
    # Remove .yml or .yaml extension to get schema_type
    schema_type = schema_filename.replace(".yml", "").replace(".yaml", "")

    schema_file = schemaPath / f"{schema_type}.yaml"
    if not schema_file.exists():
        schema_file = schemaPath / f"{schema_type}.yml"
    if not schema_file.exists():
        raise FileNotFoundError(f"Schema file {schema_file} not found.")

    schema = load_yaml(schema_file)
    return _enforce_no_additional_properties(schema) if restrictive else schema


def check_document(data: dict, schema: dict) -> None:
    """Raise unless `data` conforms to `schema`, and a system to its own material names."""
    _jsonschema_validate_modified(data, schema, registry=registry)
    if data["metadata"]["schema"] == "system_schema.yml":
        errors = system_errors(data)
        if errors:
            raise ValueError("\n".join(errors))


def validate(
    input: dict | str | Path, restrictive: bool = False, system: str | Path | None = None,
) -> None:
    """
    Validates a given AWESIO input by auto-detecting the schema type from metadata.

    A structure is also checked against its system file: `system` where given, else
    `metadata.system` relative to the structure's own file. A structure passed as a
    dictionary without `system` has no file to resolve against, so only its schema is
    checked.

    Args:
        input (dict | str | Path): Input data as a dictionary or a path to a YAML file 
            containing the data to be validated.
        restrictive (bool, optional): If True, the schema will be modified to enforce
            that no additional properties are allowed. Defaults to False.
        system (str | Path, optional): The system file of a structure, in place of the
            one it names.

    Raises:
        FileNotFoundError: If the schema file corresponding to the schema type is not found.
        TypeError: If the input type is not supported (must be dict, str, or Path-like).
        ValueError: If the schema type cannot be determined from the input data.

    Returns:
        dict: The validated input data. If validation fails, the data
        is still returned but a validation error message is printed.
    """
    if type(input) is dict:
        data = copy.deepcopy(input)
    elif type(input) in [str, Path, PosixPath, WindowsPath]:
        data = load_yaml(input)
    else:
        raise TypeError(f"Input type {type(input)} is not supported.")
    
    schema = load_schema(data, restrictive)

    try:
        check_document(data, schema)
        if data["metadata"]["schema"] == "structure_schema.yml":
            if system is not None:
                check_against_system(data, Path(system))
            elif type(input) is not dict:
                check_against_system(data, Path(input).parent / data["metadata"]["system"])

    except (ValueError, jsonschema.ValidationError) as e:
        warnings.warn(f"Validation failed: {e}", UserWarning, stacklevel=2)
        return data

    return data


def _jsonschema_validate_modified(instance, schema, cls=None, *args, **kwargs):
    """`jsonschema.validate` with awesIO's own keywords and a clearer error message."""
    if cls is None:
        cls = jsonschema.validators.extend(
            jsonschema.validators.validator_for(schema),
            {"rowsMatchHeaders": rows_match_headers, "optionalColumns": optional_columns},
        )

    cls.check_schema(schema)
    validator = cls(schema, *args, **kwargs)
    schema_validation_error_formatter(validator.iter_errors(instance), schema['$id'])