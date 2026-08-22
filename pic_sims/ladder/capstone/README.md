# Capstone — the ladder terminus

Two stages: the vacuum EB check and **the anchor**, the validated 200 V
operating point every other device run hangs off.

| folder | stage id | what it is |
|---|---|---|
| `1_two_node_laplace` | `capstone.two_node_laplace` | two-node EB in vacuum (seconds) |
| `2_chipsat_thruster` | `capstone.floating_body` | **200 V anchor**, Ø10 × 5.5 mm can (~6.3 GPU-h) — φ 16.98 V, F 13.65 nN, escape 98.44 %, KE 147.5 eV (`reference_results/20260801T142601Z_2f822a95`) |

The ladder deliberately ends here. Every run that *varies* the anchor — the
300 V / 100 V voltage points, the slender geometry, thin plasma, the tier-M1
magnetized pair — is a characterization spoke, not a rung: each depends only
on the anchor and never on another spoke. They live in
[`../../characterization/`](../../characterization/README.md),
each as a self-contained stage folder with its migrated evidence and
provenance notes.

Historical note: before 2026-08-11 those spokes ran as variant decks through
`2_chipsat_thruster` under the exploratory policy
`capstone.exploratory_axes.v1` (still committed here as
`2_chipsat_thruster/acceptance_exploratory.yaml`, whose header records the
required-vs-reported gate rationale). Their run manifests therefore carry
`stage_id: capstone.floating_body`; pre-registered predictions and results
live in each spoke's README under
[`../../characterization/`](../../characterization/README.md).
