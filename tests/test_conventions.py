"""The rules docs/source/conventions.rst states for every awesIO file, checked on every
schema's example."""

import warnings
from pathlib import Path

import pytest

from awesio.validator import validate
from awesio.yaml import load_yaml

EXAMPLES = Path(__file__).parent.parent / "examples"
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
