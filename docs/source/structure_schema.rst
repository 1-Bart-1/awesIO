AWE System Structure Schema
===========================

The structure schema describes the **resolved structural definition** of an AWE
system: the points, the segments, stations, pulleys, tethers and winches built on
them, the rigid bodies, and the tubes between those bodies. Each component carries
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

Validation, units, versioning and a tool's own blocks follow the :doc:`conventions`
every awesIO file shares.

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
     headers: [name, points, l0, diameter, density, unit_stiffness]
     data:
       - [seg_1, [ground, tether_1], 10.0, 0.004, 724.0, 614600.0]

What an element connects is one column holding a two-element tuple — a segment's
``points``, a pulley's ``segments``, a tube's ``bodies`` — so the schema fixes that
there are exactly two.

Every header is a string and every row is exactly as long as its headers, which the
``table`` definition states as ``rowsMatchHeaders`` — a keyword ``awesio.validator``
enforces and other draft-07 validators skip.

YAML and JSON are two encodings of one model. JSON is the machine encoding, and it
travels in the table-level metadata of an Arrow state log under the key ``topology``,
which is what makes a log self-describing: plotting it needs no sidecar file.

The core, and what a tool carries beside it
-------------------------------------------

A column earns its place in the core by having a reader outside the tool it came
from; that test, and not whether the quantity is respectable, is what keeps one
solver's settings out of every other tool's files. SAM's own ``wings``,
``transforms`` and ``groups`` ride beside the core, while ``metadata`` and a table's
own keys stay closed.

Stations
--------

A **station** is a chordwise section of a wing, given by its points. They give the
local chord, from which a reader derives the section's angle of attack — and, where
they trace the profile, its airfoil shape — and they are where the aerodynamic load
of the span the station covers is put. They share one twist degree of freedom.

A station is not tied to the aerodynamic mesh: it may cover several of its panels.
Station rows carry no spanwise order.

Bodies, and the tubes between them
----------------------------------

A rigid body has a position and a frame: ``pos_CAD`` is its origin, the centre of
its own mass, and ``Q_KA_to_CAD`` the rotation from its own KA frame into CAD.
``mass`` and ``inertia_KA`` are taken about that origin.

Every ``mass`` in a document is extra mass, never a total. A body's ``mass`` and
``inertia_KA`` leave out the points fixed to it, which a reader adds to the body; a
point's ``mass`` leaves out its segments, and a reader adds half of each attached
segment's mass from their ``diameter``, ``density`` and ``l0``. A tool that carries
no rotational inertia writes zeros.

``inertia_KA`` is the full tensor in the body's KA axes. Where those are its
principal axes the tensor is diagonal; a wing body's KA axes are fixed by the wing's
geometry, so its tensor in general is not.

**A tube joins two bodies**, named in its ``bodies`` column and never as points.
Their positions fix its ends and so its rest length, and one ``diameter`` holds for
the whole element. How it curves between those ends belongs to the element: a
Timoshenko beam carries curvature of its own, and only a shape its ``law`` cannot
hold — or a taper — needs a chain of tubes.

How a law is parameterised is not yet part of this schema, so a file naming one is
portable only between readers that know the name. A segment's ``unit_stiffness`` takes
the same freedom: a number is the linear value, a string names a law.

Pairing with a state log
------------------------

``metadata.connectivity_sha`` guards the pairing of a structure with a state log. Its
preimage is spelled out on ``metadata.connectivity_sha`` in the schema below; the row
numbers in it are **one-based**, so that a zero-based reader does not see every file
as a mismatch.

Frames
------

A column's suffix names the frame of its vectors, ``_CAD``, ``_ENU`` or ``_KA``, as
the :doc:`conventions` define them.

A body's ``_KA`` frame holds the axes its ``inertia_KA`` is stated in. A control
unit or a single tube has no leading edge to orient it by, so its writer
orients that frame as it likes and ``Q_KA_to_CAD`` is where the file says which
orientation it chose.

``pos_CAD`` is **design** geometry. Never draw it as if it were a world position: the
position of a point in the ENU world frame depends on elevation, azimuth, heading and
tether length, which are state, not structure. A body's frame is ``Q_KA_to_CAD`` in a
structure document and ``Q_KA_to_ENU`` in a state log, which is the same rotation
composed with the placement.

The transforms that place CAD geometry into the world are **not part of this schema**,
and not because they are unfinished. Placement is a separate concern from structure:
the same structure flies at any elevation.

What is not described here
--------------------------

Live state: positions, velocities, forces, twist angles, reel-out lengths. A structure
is written once; state is written every step, which is why it belongs in the columns
of a log rather than in this document.

Examples
--------

``examples/structure`` holds two documents of the same kite — the TU Delft V3, a
bridled soft wing — from the two models `V3Kite.jl
<https://github.com/OpenSourceAWE/V3Kite.jl>`_ flies it with. They share the bridle,
the tether and the single winch, and differ in what carries the wing:

``v3_psm_structure.yml``
   The particle lattice: 44 points, 95 segments and 6 pulleys carry the wing's shape,
   and its mass sits on those points. No bodies and no tubes — the lattice *is* the
   structure.

``v3_beam_structure.yml``
   The beam wing: 22 rigid bodies, twelve down the leading-edge tube and ten down the
   trailing edge, joined by eleven ``le_beam_*`` tubes along the leading edge and ten
   ``strut_beam_*`` from front to back. The canopy's 150 points ride a twenty-third,
   ``KINEMATIC`` body whose frame is the wing's own and whose mass is zero, since the
   wing's 11 kg are already on the other 22. Under them the bridle and one tether, in
   a document of 220 points over 366 segments.

SymbolicAWEModels.jl wrote both from V3Kite.jl, against the schema before tubes, and
they were converted onto this one rather than generated again: the tube pressure is
V3Kite's 0.3 bar, the law Breukels', the diameter twice the old joint radius, and
each part body's frame V3Kite's ``Q_b_to_w``. ``metadata.note`` names the commits
they came from; once the writer emits this schema they are regenerated instead.

Both keep their source's names. V3Kite's are index-keyed, so a component it does not
name carries its row number instead — every row of ``v3_psm_structure.yml``, and the
beam file's wing body, is called ``"1"`` upwards. The beam wing's trailing edge also
ties its centre element twice, ``te_5`` and ``te_5_2`` over the same two points, which
is `V3Kite.jl#64 <https://github.com/OpenSourceAWE/V3Kite.jl/issues/64>`_ rather than
this schema's doing.

Columns
-------

The columns each block requires, in the order its ``headers`` must list them.

.. schema-columns:: ../../src/awesio/schemas/structure_schema.yml

Schema Structure
----------------

.. jsonschema:: ../../src/awesio/schemas/structure_schema.yml
   :auto_reference:
