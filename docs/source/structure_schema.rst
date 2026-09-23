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

Every block is a ``headers``/``units``/``data`` table and every reference is by name,
so a file reads as a spreadsheet and rows reorder without rewriting indices:

.. code-block:: yaml

   segments:
     headers: [name, points, l0, diameter, density, unit_stiffness]
     units: ["-", "-", m, m, kg/m^3, N]
     data:
       - [seg_1, [ground, tether_1], 10.0, 0.004, 724.0, 614600.0]

What an element connects is one column holding a two-element tuple — a segment's
``points``, a pulley's ``segments``, a tube's ``bodies`` — so the schema fixes that
there are exactly two.

The ``units`` row says which unit each column is in, so a file reads without the
schema beside it. A block pins the unit of every column it requires, SI throughout
and spelled as the :doc:`conventions` list them, and a column a writer appends states
its own.

Every header and unit is a string, and the units and every row are exactly as long as
the headers, which the ``table`` definition states as ``rowsMatchHeaders`` — a keyword
``awesio.validator`` enforces and other draft-07 validators skip.

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
of the span the station covers is put.

A station's **local twist** is the angle its chord has turned through about the wing's
KA y axis from where the document places it, positive pitching the leading edge up.

A station is not tied to the aerodynamic mesh: it may cover several of its panels.
Station rows run from +y to -y of the wing's KA frame, left tip to right tip.

Bodies, and the tubes between them
----------------------------------

A rigid body has a position and a frame: ``pos_ENU`` is its origin, the centre of
its own mass, and ``Q_KA_to_ENU`` the rotation from its own KA frame into the world.
``extra_mass`` and ``extra_inertia_KA`` are taken about that origin.

Every mass in a document is extra mass, never a total: a reader adds what it
derives. A point's ``extra_mass`` leaves out its segments, and a reader adds half of
each attached segment's mass from their ``diameter``, ``density`` and ``l0``. A
body's ``extra_mass`` and ``extra_inertia_KA`` leave out the points fixed to it,
which a reader adds to the body.

``extra_inertia_KA`` is the full tensor in the body's KA axes. Where those are its
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

A column's suffix names the frame of its vectors, ``_ENU`` or ``_KA``, as the
:doc:`conventions` define them. Every position is in ENU, where the system is placed:
a document is expanded all the way into the world, so a reader needs no transform to
draw it.

A body's ``_KA`` frame holds the axes its ``extra_inertia_KA`` is stated in. A control
unit or a single tube has no leading edge to orient it by, so its writer
orients that frame as it likes and ``Q_KA_to_ENU`` is where the file says which
orientation it chose.

What is not described here
--------------------------

Live state: how positions, velocities, forces, twist angles and reel-out lengths move
from where the document places them. A structure is written once; state is written
every step, which is why it belongs in the columns of a log rather than in this
document.

Examples
--------

``examples/structure`` holds two models of the same kite — the TU Delft V3, a bridled
soft wing, placed at 70° elevation. They share the bridle, the tether and the single
winch, and differ in what carries the wing:

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

Columns
-------

The columns each block requires, in the order its ``headers`` must list them, with
the unit its ``units`` row must give each.

.. schema-columns:: ../../src/awesio/schemas/structure_schema.yml

Schema Structure
----------------

.. jsonschema:: ../../src/awesio/schemas/structure_schema.yml
   :auto_reference:
