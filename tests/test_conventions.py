"""The rules docs/source/conventions.rst states for every awesIO file, checked on every
schema's example."""

import math
import re
import warnings
from pathlib import Path

import numpy as np
import pytest
from ruamel.yaml import YAML

from awesio.validator import validate
from awesio.yaml import load_yaml

EXAMPLES = Path(__file__).parent.parent / "examples"
CONVENTIONS = Path(__file__).parent.parent / "docs/source/conventions.rst"
OPERATIONAL_CONSTRAINTS = (
    "ground_gen/soft_kite_pumping_ground_gen_operational_constraints.yml"
)
EXAMPLE_FILES = [
    "system_config/soft_kite_pumping_ground_gen_system.yml",
    "structure/v3_beam_structure.yml",
    "structure/v3_psm_structure.yml",
    "wind_resource.yml",
    "ground_gen/soft_kite_pumping_ground_gen_power_curves.yml",
    OPERATIONAL_CONSTRAINTS,
]


@pytest.fixture(params=EXAMPLE_FILES)
def example(request):
    return load_yaml(EXAMPLES / request.param)


def validation_warnings(data):
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        validate(data)
    return [str(warning.message) for warning in caught]


def test_example_conforms(example):
    assert validation_warnings(example) == []


def test_a_tool_may_add_top_level_blocks_of_any_shape(example):
    example["my_tool"] = {"solver": "rk4", "tolerances": [1e-6, 1e-8]}
    example["my_tool_notes"] = ["free", "form"]
    assert validation_warnings(example) == []


@pytest.mark.parametrize("reference", ["azimuth_reference", "reference_point"])
def test_terrain_zones_reject_a_reference_other_than_the_enu_origin(reference):
    constraints = load_yaml(EXAMPLES / OPERATIONAL_CONSTRAINTS)
    constraints["terrain_constraints"][reference] = "magnetic north"
    [warning] = validation_warnings(constraints)
    assert reference in warning


def test_wind_directions_are_bearings_in_degrees():
    wind_resource = load_yaml(EXAMPLES / "wind_resource.yml")
    wind_resource["wind_direction_bins"]["bin_edges"][-1] = 361.0
    [warning] = validation_warnings(wind_resource)
    assert "361.0 is greater than the maximum of 360" in warning


def test_terrain_zones_are_bearings_in_degrees():
    constraints = load_yaml(EXAMPLES / OPERATIONAL_CONSTRAINTS)
    constraints["terrain_constraints"]["azimuth_zones"][-1]["azimuth_range"][1] = 361.0
    [warning] = validation_warnings(constraints)
    assert "361.0 is greater than the maximum of 360" in warning


def rotation(axis, angle):
    """Right-handed rotation by `angle` [rad] about the unit vector `axis`."""
    cross = np.array([[0, -axis[2], axis[1]], [axis[2], 0, -axis[0]], [-axis[1], axis[0], 0]])
    return np.eye(3) + math.sin(angle) * cross + (1 - math.cos(angle)) * cross @ cross


def placement_rotation(base_KA, elevation, azimuth, heading):
    """`R` of a placement row, step by step as the conventions page defines it."""
    elevation, azimuth, heading = np.radians([elevation, azimuth, heading])
    line = -base_KA / np.linalg.norm(base_KA)
    radial = np.array([math.cos(elevation) * math.sin(azimuth),
                       math.cos(elevation) * math.cos(azimuth), math.sin(elevation)])
    axis = np.cross(line, radial)
    if np.linalg.norm(axis) > 1e-12:
        to_radial = rotation(axis / np.linalg.norm(axis), math.acos(line @ radial))
    elif line @ radial > 0:
        to_radial = np.eye(3)
    else:
        reference = [1, 0, 0] if abs(line[0]) < 0.9 else [0, 1, 0]
        normal = np.cross(line, reference)
        to_radial = rotation(normal / np.linalg.norm(normal), math.pi)
    horizontal = np.array([-radial[1], radial[0], 0.0])
    y_t = (horizontal / np.linalg.norm(horizontal) if np.linalg.norm(horizontal) > 1e-12
           else np.array([0.0, 1.0, 0.0]))
    x_t = np.cross(y_t, radial)
    x_kite = to_radial[:, 0]
    current = math.atan2(x_kite @ y_t, x_kite @ x_t)
    return rotation(radial, heading - current) @ to_radial


def worked_example():
    """The placement, points and ENU result of the conventions page's worked example."""
    section = CONVENTIONS.read_text().split("Worked example\n~~~")[1]
    blocks = re.findall(r"code-block:: yaml\n\n((?:   .*\n|\n)+)", section)
    document, result = (YAML(typ="safe").load(block) for block in blocks)
    return document, result["pos_ENU"]


def test_the_worked_example_lands_where_the_page_says():
    document, pos_ENU = worked_example()
    [[_, base_point, base_pos, elevation, azimuth, heading]] = document["placement"]["data"]
    pos_KA = {name: np.array(position) for name, position in document["points"]["data"]}
    R = placement_rotation(pos_KA[base_point], elevation, azimuth, heading)
    for name, position in pos_KA.items():
        placed = np.array(base_pos) + R @ (position - pos_KA[base_point])
        assert placed == pytest.approx(pos_ENU[name], abs=5e-4), name
