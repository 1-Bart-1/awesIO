"""Conformance tests for structure_schema.yml and the examples it is written for."""

import copy
import hashlib
import warnings
from pathlib import Path

import pytest

from awesio.validator import validate
from awesio.yaml import load_yaml

EXAMPLE_DIR = Path(__file__).parent.parent / "examples/structure"
EXAMPLES = sorted(EXAMPLE_DIR.glob("*.yml"))


@pytest.fixture(params=EXAMPLES, ids=lambda path: path.stem)
def structure(request):
    """Every .yml in examples/structure, so the invariants below cover all of them."""
    return load_yaml(request.param)


@pytest.fixture
def beam():
    """The example filling the most blocks, which is what a mutation needs to break."""
    return load_yaml(EXAMPLE_DIR / "v3_beam_structure.yml")


def a_point_on_a_body(structure):
    """Most rows leave `body` null; breaking that column needs one that does not."""
    return next(row for row in structure["points"]["data"] if row[2] is not None)


def an_elastic_joint(structure, bodies, anchors):
    """No V3 model has an elastic joint, so a case against that block writes one."""
    structure["elastic_joints"] = {
        "headers": ["name", "bodies", "anchors_KA", "stiffness_axial",
                    "stiffness_shear", "stiffness_torsion", "stiffness_bending",
                    "damping", "radius"],
        "data": [["spring", bodies, anchors, 1.2e5, 4.0e4, 900.0, 1500.0,
                  0.002, 0.06]]}


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


def connectivity_preimage(structure):
    """One-based row numbers, so zero-based readers do not disagree with the writer."""
    row_number = {row[0]: i + 1 for i, row in enumerate(structure["points"]["data"])}
    return f"{len(row_number)};" + "".join(
        f"{row_number[a]},{row_number[b]};"
        for _, (a, b), *_ in structure["segments"]["data"]
    )


def test_connectivity_sha_hashes_the_preimage(structure):
    digest = hashlib.sha256(connectivity_preimage(structure).encode()).hexdigest()
    assert digest == structure["metadata"]["connectivity_sha"]


def test_the_documented_preimage_is_what_the_rule_produces():
    """The line the schema and the docs page quote, from three points in a row."""
    three_in_a_row = {"points": {"data": [["a"], ["b"], ["c"]]},
                      "segments": {"data": [["s1", ("a", "b")], ["s2", ("b", "c")]]}}
    assert connectivity_preimage(three_in_a_row) == "3;1,2;2,3;"


def test_n_points_agrees_with_the_points_block(structure):
    assert structure["metadata"]["n_points"] == len(structure["points"]["data"])


def test_wings_are_the_bodies_carrying_aero(structure):
    assert wing_names(structure), "every example describes a system that flies"


def test_a_point_fixed_to_a_body_leaves_its_wing_null(structure):
    """The body's own row names the wing, so the point does not name it again."""
    for name, _, body, wing, *_ in structure["points"]["data"]:
        assert body is None or wing is None, name


def test_a_body_includes_the_mass_of_the_points_fixed_to_it(structure):
    """A reader must not add a BODY_STATIC point's `mass` to its body's again."""
    for body, _, _, _, body_mass, *_ in structure["bodies"]["data"]:
        point_mass = sum(row[5] for row in structure["points"]["data"]
                         if row[2] == body)
        assert point_mass <= body_mass, body


def test_every_reference_resolves_to_a_named_row(structure):
    def rows(block):
        return structure.get(block, {"data": []})["data"]

    def names(block):
        return {row[0] for row in rows(block)}

    points, segments, bodies = names("points"), names("segments"), names("bodies")
    wings = wing_names(structure)
    for name, _, body, wing, *_ in rows("points"):
        assert body is None or body in bodies, name
        assert wing is None or wing in wings, name
    for name, _, _, wing, *_ in rows("bodies"):
        assert wing is None or wing in wings, name
    for _, endpoints, *_ in rows("segments"):
        assert set(endpoints) <= points
    for _, pair, *_ in rows("pulleys"):
        assert set(pair) <= segments
    for _, _, wing, members, *_ in rows("stations"):
        assert wing in wings and set(members) <= points
    for _, start, end, members in rows("tethers"):
        assert {start, end} <= points and set(members) <= segments
    for block in ("elastic_joints", "timoshenko_joints"):
        for _, pair, *_ in rows(block):
            assert set(pair) <= bodies


@pytest.mark.parametrize(
    "label, mutate",
    [
        ("reordered headers",
         lambda d: d["points"]["headers"].reverse()),
        ("unknown dynamics type",
         lambda d: d["points"]["data"][0].__setitem__(1, "FLOATING")),
        ("two-component pos_cad",
         lambda d: d["points"]["data"][0].__setitem__(4, [0.0, 0.0])),
        ("a point's body given as an index",
         lambda d: a_point_on_a_body(d).__setitem__(2, 2)),
        ("a segment with three endpoints",
         lambda d: d["segments"]["data"][0][1].append("wing_le_1")),
        ("negative segment length",
         lambda d: d["segments"]["data"][0].__setitem__(2, -1.0)),
        ("efficiency above one",
         lambda d: d["pulleys"]["data"][0].__setitem__(3, 1.4)),
        ("a point with negative mass",
         lambda d: d["points"]["data"][0].__setitem__(5, -8.4)),
        ("a point row without its drag coefficient",
         lambda d: d["points"]["data"][0].pop()),
        ("a station naming no wing",
         lambda d: d["stations"]["data"][0].__setitem__(2, None)),
        ("a station holding a bare point name",
         lambda d: d["stations"]["data"][0].__setitem__(3, "wing_le_1")),
        ("a joint naming one body and one null",
         lambda d: an_elastic_joint(d, ["wing_le_body_1", None],
                                    [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]])),
        ("a joint with one anchor",
         lambda d: an_elastic_joint(d, ["wing_le_body_1", "wing_le_body_2"],
                                    [[0.0, 0.0, 0.0]])),
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
        ("a non-string appended header",
         lambda d: d["segments"]["headers"].append(42)),
        ("a row shorter than its appended headers",
         lambda d: d["segments"]["headers"].append("youngs_modulus")),
        ("a row longer than its headers",
         lambda d: d["segments"]["data"][0].append(1.1e11)),
        ("an undeclared key inside metadata",
         lambda d: d["metadata"].update(tool="SAM")),
        ("an undeclared key beside a table's headers and data",
         lambda d: d["segments"].update(units=["-"])),
    ],
)
def test_malformed_structures_are_rejected(beam, label, mutate):
    broken = copy.deepcopy(beam)
    mutate(broken)
    assert_invalid(broken)


def test_optional_blocks_may_be_absent(structure):
    """An absent optional block means the same as an empty one."""
    sparse = copy.deepcopy(structure)
    for block in ("stations", "pulleys", "tethers", "winches",
                  "bodies", "elastic_joints", "timoshenko_joints"):
        sparse.pop(block, None)
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
