"""The rules docs/source/conventions.rst states for every awesIO file, checked on every
schema's example."""

import warnings
from pathlib import Path

import pytest

from awesio.validator import validate
from awesio.yaml import load_yaml

EXAMPLES = Path(__file__).parent.parent / "examples"
EXAMPLE_PER_SCHEMA = [
    "system_config/soft_kite_pumping_ground_gen_system.yml",
    "structure/minimal_structure.yml",
    "wind_resource.yml",
    "ground_gen/soft_kite_pumping_ground_gen_power_curves.yml",
    "ground_gen/soft_kite_pumping_ground_gen_operational_constraints.yml",
]


@pytest.fixture(params=EXAMPLE_PER_SCHEMA)
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

