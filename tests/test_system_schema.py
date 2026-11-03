"""Conformance tests for the materials of system_schema.yml."""

import warnings
from pathlib import Path

import pytest

from awesio.validator import validate
from awesio.yaml import load_yaml

V3_SYSTEM = Path(__file__).parent.parent / "examples/system_config/v3_system.yml"


@pytest.fixture
def system():
    """The V3 system."""
    return load_yaml(V3_SYSTEM)


def material(system, name):
    return next(row for row in system["materials"] if row["name"] == name)


def tether_structure(system):
    return system["components"]["tethers"][0]["structure"]


@pytest.mark.parametrize(
    "label, mutate, message",
    [
        ("no materials", lambda d: d.pop("materials"), "'materials' is a required"),
        ("a material with an empty law name",
         lambda d: material(d, "bridle_line").update(law=""), "non-empty|too short"),
        ("a linear material without its Young's modulus",
         lambda d: material(d, "bridle_line")["parameters"].pop("youngs_modulus"),
         "'youngs_modulus' is a required"),
        ("a negative Young's modulus",
         lambda d: material(d, "bridle_line")["parameters"].update(youngs_modulus=-5.5e10),
         "minimum"),
        ("a membrane material holding a line's parameters",
         lambda d: material(d, "bridle_line").update(law="membrane"),
         "'areal_density' is a required"),
        ("a breukels2011 material without C19",
         lambda d: material(d, "breukels2011")["parameters"].pop("C19"), "'C19' is a required"),
        ("a breukels2011 material with a constant it does not define",
         lambda d: material(d, "breukels2011")["parameters"].update(C20=1.0), "does not match"),
        ("a material whose parameters are a list",
         lambda d: material(d, "bridle_line").update(parameters=[970.0, 5.5e10]),
         "not of type 'object'"),
        ("a material defined twice",
         lambda d: d["materials"].append(dict(material(d, "bridle_line"))), "defined twice"),
        ("a tether naming a material the system lacks",
         lambda d: tether_structure(d).update(material="unobtainium"),
         "names material 'unobtainium'"),
        ("a tether nesting its own material",
         lambda d: tether_structure(d).update(material={"youngs_modulus": 5.5e10}),
         "not of type 'string'"),
        ("a tether stating the density its material holds",
         lambda d: tether_structure(d).update(density=970.0), "density"),
    ],
)
def test_malformed_systems_are_rejected(system, label, mutate, message):
    mutate(system)
    with pytest.warns(UserWarning, match=message):
        validate(system)


def test_a_material_may_name_any_law_with_any_parameters(system):
    curve = {"strain": [0.0, 0.01], "force": [0.0, 80.0]}
    material(system, "bridle_line").update(law="tabulated", parameters=curve)
    with warnings.catch_warnings():
        warnings.simplefilter("error", UserWarning)
        validate(system)
