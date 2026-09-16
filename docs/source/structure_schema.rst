AWE System Structure Schema
===========================

The structure schema describes the **resolved structural definition** of an AWE
system: the points, the segments, stations, pulleys, tethers and winches built on
them, the rigid bodies, and the joints that link those bodies. Each component carries
its own geometry and material, so a conforming file is a complete structural
definition rather than a connectivity sketch.

It is the layer :doc:`system_schema` leaves free-form — its ``wing_sections``,
``bridle_nodes``, ``bridle_lines`` and ``bridle_connections`` blocks are bare
``type: object`` under ``additionalProperties: true``, so today any content
validates.

Plotting is the clearest symptom of not having it. Two tools cannot draw each other's
system because neither can describe it, so every viewer is written against one model.
With a shared structure, drawing a state is one code path and every model gets every
viewer.

.. note::
   All quantities follow the SI unit convention used throughout awesIO.

Canonical form only
-------------------

A conforming file is **fully resolved and expanded**: no variable substitution block,
no segment counts left to expand, every component explicit. It is readable with
nothing beyond a YAML or JSON parser.

Authoring dialects — multi-variable substitution, tether expansion, defaults — stay
profiles of the tool that defines them and *emit* canonical files. An interchange
format is worth having only if any tool can read it, and requiring implementers to
build a substitution engine before they can load a file is an adoption barrier.
Draft-07 could not express an authoring layer in any case: a row whose arity depends
on a variables block has no vocabulary in JSON Schema.

Tables, not nesting
-------------------

Every block is a ``headers``/``data`` table and every reference is by name, so a file
reads as a spreadsheet and rows reorder without rewriting indices:

.. code-block:: yaml

   segments:
     headers: [name, points, l0, diameter, density, unit_stiffness,
               unit_damping, compression_frac, compression_damping_frac]
     data:
       - [seg_1, [ground, tether_1], 10.0, 0.004, 724.0, 614600.0, 473.0, 0.1, 1.0]

What an element connects is one column holding a two-element tuple — a segment's
``points``, a pulley's ``segments``, a joint's ``bodies`` and ``anchors_KA`` — so the
schema fixes that there are exactly two.

A block may carry columns beyond the ones the schema requires. **A reader addresses
columns by header, never by position** — that is what lets a later minor version
append a column without breaking an older reader. An absent optional block means the
same as an empty one; only ``metadata``, ``points`` and ``segments`` are required.

YAML and JSON are two encodings of one model. JSON is the machine encoding, and it
travels in the table-level metadata of an Arrow state log under the key ``topology``,
which is what makes a log self-describing: plotting it needs no sidecar file.

Stations are not aerodynamic sections
-------------------------------------

A **station** is a group of points sharing one twist degree of freedom. It is a
structural group, and it is coarser than the aerodynamic mesh: a wing meshed at forty
panels may carry four stations, each spanning ten of them.

The distinction is worth stating because conflating the two is a mistake that has
already been made and fixed once in a reference implementation, where a station count
was passed as a section count and produced a four-section wing. A reader that builds
a lifting surface by pairing adjacent station rows will draw the wrong shape. Station
rows carry no spanwise ordering guarantee and none should be assumed.

A station names the wing whose twist it carries in its ``wing`` column. That is stated
rather than left to be inferred from the station's points, which name their wing through
``body`` or ``wing`` and need not all be nodes of it.

Bodies, wings and joints
------------------------

Rigid bodies live in one ``bodies`` block. **A wing is a body that carries an
aerodynamic model**, so the wings of a system are the rows whose ``aero`` is not
null. There is no separate wings block, because two blocks describing overlapping
sets of the same objects fall out of step.

For the same reason a point names its wing once. ``body`` is the rigid body a
``BODY_STATIC`` point is fixed to; ``wing`` is the wing a point belongs to where
``body`` does not already name it — a free node of a wing, or a point on a non-wing
body that moves with one — and null otherwise.

A point carries its own ``mass``, not counting the segments attached to it, and the
``drag_area`` its ``drag_coefficient`` refers to. **A body's ``mass``,
``inertia_principal`` and ``com_offset_KA`` already include the points fixed to it**: a
reader takes the body row as it stands, rather than deriving it from those points or
adding them to it again.

Joints link two bodies by name, never points, and come in two blocks because their
field sets genuinely differ rather than their values: an ``elastic_joint`` holds four
stiffnesses resolved about relative degrees of freedom, while a
``timoshenko_joint`` holds ``EA``, ``GA``, ``GJ``, ``EIy`` and ``EIz`` with a shear
correction factor, and a chain of them forms a beam.

Every stiffness and rigidity accepts either a number — the linear value, in the units
its column names — or a **string naming a nonlinear law** the reader resolves to a
function of the corresponding strain, curvature or deflection. How such a law is
defined is not yet part of this schema, so a file using one is portable only between
readers that know the name. Both joint blocks also carry ``radius``, which is the
cylinder radius for drawing the element and has no effect on dynamics; null means the
element is not drawn.

Versioning
----------

The ``metadata`` block carries two fields that are easy to confuse:

``schema``
   Pinned by ``const`` to the filename, awesIO's convention. It identifies *which*
   schema, never which version.

``awesIO_version``
   The version. **A reader must refuse an unknown major version and warn on an
   unknown minor one.** Every implementation applies that one rule, so a breaking
   change is caught at load rather than silently misread.

``connectivity_sha`` guards the pairing of a structure with a state log. Its preimage
is ASCII and built in document order: the point count, a semicolon, then each
segment's two endpoints as **one-based** row numbers into the points block, comma
separated and semicolon terminated. The example file reads ``8;1,2;2,3;3,4;4,5;4,7;``.
The one-based convention is stated because a zero-based implementation would disagree
with every file ever written and see them all as mismatches.

Frames
------

A column's suffix names the frame of its vectors, following KiteUtils.jl:

``_cad``
   The CAD design frame the geometry was drawn in.

``_KA``
   The owning body's kite-aero frame: x from leading to trailing edge, y from the left
   to the right tip, z up.

``pos_cad`` is **design** geometry. Never draw it as if it were a world position: the
position of a point in the ENU world frame depends on elevation, azimuth, heading and
tether length, which are state, not structure.

The transforms that place CAD geometry into the world are **not part of this schema**,
and not because they are unfinished. Placement is a separate concern from structure:
the same structure flies at any elevation.

What is not described here
--------------------------

Live state: positions, velocities, forces, twist angles, reel-out lengths. A structure
is written once; state is written every step, which is why it belongs in the columns
of a log rather than in this document.

Example
-------

``examples/structure/minimal_structure.yml`` exercises every block: a ground anchor, a
three-segment tether, a control unit on the bridle, and two wing bodies joined to it.
It is illustrative rather than a physical system; a worked kite follows once a writer
emits conforming files.
