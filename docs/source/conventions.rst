Conventions
===========

These rules hold for every awesIO file, whichever schema it follows. A schema page
states only what is specific to its own file.

Which schema a file follows
---------------------------

Every file opens with a ``metadata`` block. Its ``schema`` field is pinned to the
schema's filename, such as ``structure_schema.yml``, and names *which* schema the
file follows, never which version. ``awesio.validator.validate`` reads it to pick the schema, so a file is validated without being told its type:

.. code-block:: python

   from awesio.validator import validate

   data = validate("your_file.yml")

Units
-----

All quantities are in **SI units**, except angles in a YAML file, which are in
**degrees**. The time-history arrays in a companion ``.npz`` file are SI throughout,
angles in radians.

A table states the unit of each of its columns in a ``units`` row, one entry per
header, and spells each unit one way:

.. list-table::
   :header-rows: 1
   :widths: 1 4

   * - Unit
     - Quantity
   * - ``m``
     - length, position, diameter
   * - ``m^2``
     - area
   * - ``kg``
     - mass
   * - ``kg/m^2``
     - areal density
   * - ``kg/m^3``
     - density
   * - ``kg*m^2``
     - moment of inertia
   * - ``N``
     - force
   * - ``N/m``
     - force per length, such as a membrane stiffness
   * - ``Pa``
     - pressure
   * - ``deg``
     - angle
   * - ``-``
     - dimensionless, and a column holding names, flags, types, references or a law's
       parameters

A unit not listed is written the same way: SI symbols joined by ``*`` and ``/``,
powers with ``^``, such as ``m/s`` or ``N*m^2``. A schema pins the unit of every
column it requires, so a file writing ``mm`` where the schema says ``m`` does not
validate.

Versioning
----------

``metadata.awesIO_version`` is the version the file was written against. **A reader
refuses an unknown major version and warns on an unknown minor one**, so a breaking
change is caught at load rather than silently misread. A minor version only adds.

Names a reader does not know
----------------------------

A tool may carry data of its own as extra top-level blocks of any shape. ``metadata``
and the blocks a schema defines keep the keys that schema lists, except where the
schema opens one itself. **A reader ignores every name it does not know**, so a file
written for one tool still loads in another.

A later minor version may claim any such name for the schema, after which the tool
renames its own.

Frames
------

A vector's name ends in a suffix naming the frame it is written in. Every frame is
right-handed and in metres. The frames are those of `KiteUtils.jl
<https://opensourceawe.github.io/KiteUtils.jl/dev/reference_frames/>`_.

``_KA``
   The kite's frame: x from the leading to the trailing edge, y from the right to the
   left tip, z up. Right and left are as seen looking at the kite from the front, so a
   turn to the right is a positive rotation about z. Its origin is the point a document
   names as its origin, the control unit of a soft kite.

``_body``
   A rigid body's own frame, with its origin at the body's centre of mass.

``_ENU``
   The world: x east, y north, z up, with its origin at the tether exit point of the
   ground station.

A rotation reads ``Q_<from>2<to>``: a unit quaternion ``q``, scalar first
``[w, x, y, z]``, that takes a vector's components in ``<from>`` to the same vector's
components in ``<to>``, ``v_to = q v_from q*``. Its rotation matrix has ``<from>``'s
axes, written in ``<to>``, as its columns.

A bearing is a horizontal direction in ENU, the angle from north (``+y``) towards east
(``+x``): north is 0, east is 90. That is clockwise seen from above, a negative
rotation about ``z``. A wind direction is the bearing the wind blows from, so a westerly
wind has direction 270.

An azimuth is a horizontal direction in ENU as mathematics measures it, ``atan2(y, x)``:
the angle from east (``+x``) towards north (``+y``), from −180 to 180. That is
counter-clockwise seen from above, a positive rotation about ``z``. It converts to a
bearing as ``bearing = 90 − azimuth``, wrapped to 0–360, and to KiteUtils.jl's
``azimuth_east``, which counts clockwise, as ``azimuth = −azimuth_east``.

Placing a kite in the world
---------------------------

A kite is written in its ``_KA`` frame, and a **placement** puts it in ``_ENU``. A
placement row gives a base point ``b``, which sits at the ground station, the base
position ``g`` in ENU, an elevation ``ε``, an azimuth ``φ`` and a heading ``ψ``, all in
degrees. The elevation is the angle of the line from the base point to the kite above
the horizontal, and the azimuth is that line's azimuth. The heading turns the kite about
that line: it is 0 where the kite's x axis points away from the zenith, and a positive
heading is a turn to the right.

A row is applied to every point and body it places in three steps: translate the kite
so that ``b`` is at ``g`` with its axes along ENU's, rotate it about ``b`` so that the
line from ``b`` to the KA origin has the elevation and the azimuth, then turn it about
that line by the heading. Together they are one rotation ``R`` about ``b``: a position
``p_KA`` and the rotation matrix ``R_body2KA`` of a body's ``Q_body2KA`` are placed at

.. math::

   p_{ENU} = g + R\,(p_{KA} - b_{KA}), \qquad R_{body2ENU} = R\,R_{body2KA}

where ``R = R_ψ R_ε`` is built from unit vectors as follows. ``Rot(k, θ)`` is the
right-handed rotation by ``θ`` about the unit vector ``k``, ``Rot(k, θ) v = v cos θ +
(k × v) sin θ + k (k · v)(1 − cos θ)``.

1. **The line.** ``u = −b_KA / |b_KA|`` is the direction from the base point to the
   origin, and ``r = [cos ε cos φ, cos ε sin φ, sin ε]`` the direction it is placed
   along. A base point at the origin is an error.
2. **Elevation and azimuth.** ``R_ε = Rot((u × r)/|u × r|, acos(u · r))``, the
   smallest rotation taking ``u`` onto ``r``. Where ``u = r`` it is the identity. Where
   ``u = −r`` it is ``Rot(k, π)`` with ``k = (u × e)/|u × e|``, where ``e`` is ``[1, 0,
   0]`` if ``|u_x| < 0.9`` and ``[0, 1, 0]`` otherwise.
3. **Heading.** At ``r`` the tangent axes are ``y_t = [−r_y, r_x, 0]/|[−r_y, r_x, 0]|``,
   or ``[0, 1, 0]`` where ``r`` is vertical, and ``x_t = y_t × r``, which points away
   from the zenith. The kite's x axis after step 2 is ``a = R_ε [1, 0, 0]``, at the
   heading ``ψ_0 = atan2(a · y_t, a · x_t)``. Then ``R_ψ = Rot(r, ψ − ψ_0)``.

This is how SymbolicAWEModels.jl places a kite, except that its azimuth counts
clockwise, as KiteUtils.jl's ``azimuth_east`` does, and it measures the heading from a
reference body's x axis rather than the kite's.

Worked example
~~~~~~~~~~~~~~

A control unit at the origin, the ground anchor 100 m below it and a point at the
left tip, placed with the anchor at the ENU origin, the kite east of it (azimuth 0) at
60° elevation and turned 90° to the right:

.. code-block:: yaml

   placement:
     headers: [name, base_point, base_pos_ENU, elevation, azimuth, heading]
     units: [-, -, m, deg, deg, deg]
     data:
       - [kite, ground, [0.0, 0.0, 0.0], 60.0, 0.0, 90.0]
   points:
     headers: [name, pos_KA]
     units: [-, m]
     data:
       - [kcu, [0.0, 0.0, 0.0]]
       - [ground, [0.0, 0.0, -100.0]]
       - [tip, [0.5, 4.0, 2.0]]

``R_ε`` turns the kite 30° about north, so its x axis points along ``x_t`` and
``ψ_0 = 0``; ``R_ψ`` then turns it 90° about ``r``, which points the kite's x axis
north. The points land at

.. code-block:: yaml

   pos_ENU:
     kcu: [50.0, 0.0, 86.603]
     ground: [0.0, 0.0, 0.0]
     tip: [47.536, 0.5, 90.335]
