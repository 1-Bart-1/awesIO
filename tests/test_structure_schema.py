"""Conformance tests for structure_schema.yml and its worked example."""

import copy
import hashlib
import warnings
from pathlib import Path

import pytest

from awesio.validator import validate
from awesio.yaml import load_yaml

EXAMPLE = Path(__file__).parent.parent / "examples/structure/minimal_structure.yml"


@pytest.fixture
def structure():
    return load_yaml(EXAMPLE)


def assert_valid(data):
    """`validate` warns rather than raises, so a passing file must warn nothing."""
    with warnings.catch_warnings():
        warnings.simplefilter("error", UserWarning)
        validate(data)


def assert_invalid(data):
    with pytest.warns(UserWarning, match="Validation failed"):
        validate(data)


def wing_names(structure):
    """There is no wings block; a wing is a body whose `aero` is not null."""
    return {row[0] for row in structure["bodies"]["data"] if row[2] is not None}


def test_example_conforms(structure):
    assert_valid(structure)


def test_connectivity_sha_matches_its_documented_preimage(structure):
    """One-based row numbers, so zero-based readers do not disagree with the writer."""
    names = [row[0] for row in structure["points"]["data"]]
    preimage = f"{len(names)};" + "".join(
        f"{names.index(a) + 1},{names.index(b) + 1};"
        for _, (a, b), *_ in structure["segments"]["data"]
    )
    assert preimage == "8;1,2;2,3;3,4;4,5;4,7;"
    digest = hashlib.sha256(preimage.encode()).hexdigest()
    assert digest == structure["metadata"]["connectivity_sha"]


def test_n_points_agrees_with_the_points_block(structure):
    assert structure["metadata"]["n_points"] == len(structure["points"]["data"])


def test_wings_are_the_bodies_carrying_aero(structure):
    assert wing_names(structure) == {"wing_left", "wing_right"}


def test_a_point_on_a_wing_names_that_wing_once(structure):
    """`wing` is null where `body` already is the wing the point belongs to."""
    wings = wing_names(structure)
    for name, _, body, wing, *_ in structure["points"]["data"]:
        assert not (body in wings and wing is not None), name


def test_a_body_includes_the_mass_of_the_points_fixed_to_it(structure):
    """A reader must not add a BODY_STATIC point's `mass` to its body's again."""
    for body, _, _, _, body_mass, *_ in structure["bodies"]["data"]:
        point_mass = sum(row[5] for row in structure["points"]["data"]
                         if row[2] == body)
        assert point_mass <= body_mass, body


def test_every_reference_resolves_to_a_named_row(structure):
    def names(block):
        return {row[0] for row in structure.get(block, {"data": []})["data"]}

    points, segments, bodies = names("points"), names("segments"), names("bodies")
    wings = wing_names(structure)
    for _, endpoints, *_ in structure["segments"]["data"]:
        assert set(endpoints) <= points
    for _, pair, *_ in structure["pulleys"]["data"]:
        assert set(pair) <= segments
    for _, _, wing, members, *_ in structure["stations"]["data"]:
        assert wing in wings and set(members) <= points
    for _, start, end, members in structure["tethers"]["data"]:
        assert {start, end} <= points and set(members) <= segments
    for block in ("elastic_joints", "timoshenko_joints"):
        for _, pair, *_ in structure[block]["data"]:
            assert set(pair) <= bodies


@pytest.mark.parametrize(
    "label, mutate",
    [
        ("reordered headers",
         lambda d: d["points"].update(
             headers=["type", "name", "body", "wing", "pos_cad"])),
        ("unknown dynamics type",
         lambda d: d["points"]["data"][0].__setitem__(1, "FLOATING")),
        ("two-component pos_cad",
         lambda d: d["points"]["data"][0].__setitem__(4, [0.0, 0.0])),
        ("a point's body given as an index",
         lambda d: d["points"]["data"][4].__setitem__(2, 2)),
        ("a segment with three endpoints",
         lambda d: d["segments"]["data"][0][1].append("tether_2")),
        ("negative segment length",
         lambda d: d["segments"]["data"][0].__setitem__(2, -1.0)),
        ("efficiency above one",
         lambda d: d["pulleys"]["data"].append(
             ["p1", ["seg_1", "seg_2"], "DYNAMIC", 1.4])),
        ("a point with negative mass",
         lambda d: d["points"]["data"][3].__setitem__(5, -8.4)),
        ("a point row without its drag coefficient",
         lambda d: d["points"]["data"][3].pop()),
        ("a station naming no wing",
         lambda d: d["stations"]["data"][0].__setitem__(2, None)),
        ("a station holding a bare point name",
         lambda d: d["stations"]["data"][0].__setitem__(3, "le_left")),
        ("a joint linking a point instead of a body",
         lambda d: d["elastic_joints"]["data"][0][1].__setitem__(1, None)),
        ("a joint with one anchor",
         lambda d: d["elastic_joints"]["data"][0][2].pop()),
        ("a two-component anchor offset",
         lambda d: d["timoshenko_joints"]["data"][0][2].__setitem__(0, [0.0, 2.0])),
        ("body offsets under the old body-frame suffix",
         lambda d: d["bodies"]["headers"].__setitem__(7, "com_offset_b")),
        ("negative axial rigidity",
         lambda d: d["timoshenko_joints"]["data"][0].__setitem__(3, -1.0)),
        ("short segment row",
         lambda d: d["segments"]["data"][0].pop()),
        ("empty component name",
         lambda d: d["segments"]["data"][0].__setitem__(0, "")),
        ("tether segments given as indices",
         lambda d: d["tethers"]["data"][0].__setitem__(3, [1, 2, 3])),
        ("undeclared transforms block",
         lambda d: d.update(transforms={"headers": ["name"], "data": []})),
        ("truncated connectivity_sha",
         lambda d: d["metadata"].update(connectivity_sha="abc")),
        ("uppercase connectivity_sha",
         lambda d: d["metadata"].update(connectivity_sha="A" * 64)),
        ("awesIO_version without a patch component",
         lambda d: d["metadata"].update(awesIO_version="0.1")),
        ("another schema's name",
         lambda d: d["metadata"].update(schema="system_schema.yml")),
        ("missing segments block",
         lambda d: d.pop("segments")),
        ("undeclared top-level block",
         lambda d: d.update(joints={"headers": [], "data": []})),
    ],
)
def test_malformed_structures_are_rejected(structure, label, mutate):
    broken = copy.deepcopy(structure)
    mutate(broken)
    assert_invalid(broken)


def test_optional_blocks_may_be_absent(structure):
    """An absent optional block means the same as an empty one."""
    sparse = copy.deepcopy(structure)
    for block in ("stations", "pulleys", "tethers", "winches",
                  "bodies", "elastic_joints", "timoshenko_joints"):
        sparse.pop(block)
    for row in sparse["points"]["data"]:
        row[2] = row[3] = None
    assert_valid(sparse)


def test_a_reader_accepts_columns_appended_by_a_later_minor_version(structure):
    """Blocks are addressed by header, so appended columns must not break v0.1."""
    extended = copy.deepcopy(structure)
    extended["segments"]["headers"] += ["youngs_modulus"]
    for row in extended["segments"]["data"]:
        row += [1.1e11]
    assert_valid(extended)
