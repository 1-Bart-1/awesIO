AWE System Schema
==================================

The system configuration schema defines the physical properties of a complete AWE
system in a **single file**. All system components — wing, bridle, control system,
tether, and ground station — are described together at the same hierarchy level. This
flat, modular structure reflects the physical organization of an AWE system and makes
it straightforward to identify, version, and exchange complete system definitions.

Aerodynamic properties are intentionally excluded from the system configuration.
Aerodynamic models are tool-dependent: some tools work with a small number of
coefficients for a limited set of operating states, while others use higher-fidelity
models to determine the full aerodynamic behaviour of the kite or aircraft. Keeping
aerodynamics outside the system schema avoids imposing one model structure on all
tools.

Validation, units, versioning and a tool's own blocks follow the :doc:`conventions`
every awesIO file shares.

The system file owns the design: a :doc:`structure_schema` file discretising it holds only what discretising adds, as the :doc:`conventions` define under *Which file owns what*. A file says what its writer knows: only ``metadata``, ``materials`` and the tethers are required, so a tool can write the system file of a model it has discretised without inventing the rest.

Materials and their laws
------------------------

``materials`` lists what the system is made of. A tether, a wing and a bridle name a material from it in their ``material``, and a structure's segments, tubes and canopies name one in theirs. A material is a stiffness ``law`` and that law's ``parameters``:

.. code-block:: yaml

   materials:
     - name: dyneema
       law: linear
       parameters: {density: 970.0, youngs_modulus: 5.5e+10}
     - name: ripstop
       law: membrane
       parameters: {areal_density: 0.17, membrane_stiffness: 1000.0}

The schema defines the laws more than one tool implements: ``linear`` for a line, ``membrane`` for canopy fabric and ``breukels2011`` for an inflated tube. Each fixes the names and units of its parameters and states the curve they describe, so a reader that has never met the law evaluates it from the schema alone. ``breukels2011`` carries its nineteen correlation constants rather than standing for them. Any other law is free: its name is a model its readers implement, which fixes its parameters, and the file still carries every number that model needs. A reader that does not implement a material's law fails on the elements naming it rather than substituting another.

Component Types
---------------

AWE systems vary in physical layout and operating principle. A fly-generation system
may use a conductive tether, while a ground-generation system uses a non-conductive
tether. The airborne component can be a leading-edge inflatable soft kite, a ram-air
kite, a single-skin kite, or a fixed-wing aircraft.

To represent this variety within a single schema, each component specifies a
**component type**. The type determines which fields are required or applicable for
that component, for example:

* A **conductive tether** requires different parameters than a **non-conductive
  tether**.
* A **soft kite** (ram-air, single-skin, or leading-edge inflatable) requires
  different properties than a **fixed-wing aircraft**.

Where possible, parameters are kept consistent across related component types to
support comparison between designs and reduce unnecessary differences between similar
systems.

Each component also includes a **name** and **version** identifier. These metadata
fields improve traceability by making clear which component definition is used.
Equivalent metadata are also included at the top level of the file, so that the full
system configuration can be identified and versioned consistently.

Schema File
-----------

.. code-block:: text

   src/awesio/schemas/system_schema.yml

Example File
------------

See: ``examples/system_config/soft_kite_pumping_ground_gen_system.yml``

Schema Structure
----------------

.. jsonschema:: ../../src/awesio/schemas/system_schema.yml
   :auto_reference:
