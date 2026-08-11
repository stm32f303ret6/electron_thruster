# SETUP — environments, WarpX build, and how to run everything

Everything below is transcribed from the machine that produced the committed
evidence, not from documentation. Versions were read out of the live
environments; build flags were read out of `build/CMakeCache.txt`. Where a
number is a measurement (wall time, GPU memory) it says so.

For what the ladder *proves*, see `pic_sims/ladder/README.md` and
`LADDER_SUMMARY.md`. This file is only about making it run.

---

## 1. The machine the evidence came from

| | |
|---|---|
| GPU | NVIDIA GeForce RTX 3060, 12 288 MiB |
| NVIDIA driver | 580.159.03 |
| CUDA toolkit (`nvcc`) | 13.1, V13.1.115 (from the conda env, not the system) |
| CUDA arch built for | `8.6` (Ampere / GA106) |
| OS | Linux 6.8.0 x86_64 |
| Python | 3.12.13 |

A different GPU needs one change: `AMReX_CUDA_ARCH` in §3. Nothing else in the
repo is hardware-specific. The runs are single-rank (`mpi_ranks: 1` in every
manifest) — MPI is compiled in but not used for the committed evidence.

---

## 2. Conda environments

Two environments, one per tree. Recipes are committed in `env/`, generated with
`conda env export --from-history` (explicit requests only, so they resolve on
other machines).

### `warpx-cpu-mpich-dev` — the PIC tree

> **The name is a historical misnomer.** It is a **CUDA** build
> (`WarpX_COMPUTE=CUDA`). Do not infer the backend from the environment name;
> `build/CMakeCache.txt` is the authority. The name is kept because every
> committed manifest and log references it.

```bash
conda env create -n warpx-cpu-mpich-dev -f env/environment-warpx.yml
conda activate warpx-cpu-mpich-dev
```

The recipe is the upstream WarpX developer environment
(`Docs/source/install/dependencies.rst`) plus `cuda`, `cuda-nvtx-dev`, `cupy`
for the GPU backend. Versions resolved on the evidence machine:

```
pywarpx        == 26.5          numpy          == 2.4.6
picmistandard  == 0.34.0        scipy          == 1.16.3
openpmd-viewer == 1.11.0        h5py           == 3.16.0
matplotlib     == 3.10.7        pandas         == 2.2.3
PyYAML         == 6.0.3         mpi4py         == 4.1.2
pytest         == 9.0.3
```

`pywarpx` is **not** installed from PyPI — it is the local build of §3
installed into this environment's `site-packages`.

### `tudat-sk` — the orbit tree

```bash
conda env create -n tudat-sk -f env/environment-tudat.yml
conda activate tudat-sk
pip install iricore==1.9.0
python -c "import iricore; iricore.update()"    # IRI solar-index data; needs internet
```

`tudatpy 1.0.0` (NRLMSISE-00 atmosphere, SPICE, J2 propagation) and
`iricore 1.9.0` (IRI-2020 ionosphere). Note this environment pins
**numpy 1.26.4**, incompatible with the PIC environment's numpy 2.x — which is
why they are separate and why nothing is ever run cross-environment.

The IRI index files and the failure mode when they are stale are documented in
`orbit_sims/README.md` §Environment; the run refuses to start if the index does
not cover the mission span.

---

## 3. Building WarpX

### Source

WarpX lives in the **parent** directory of this repo — this repo is nested
inside a WarpX checkout:

```
/home/rsc/Desktop/repos/warpequisd/          <- WarpX checkout (build/ lives here)
└── electron_thruster_3/                     <- this repo
```

Version actually used, recorded in every run manifest as `warpx_version: 26.5`:

| component | version | commit |
|---|---|---|
| WarpX | `26.05-62-geba7343d7` | `eba7343d7` |
| AMReX | 26.05 | `c2eb6db7ee7965de0ddfc4c05d40dc2d3d61da93` |
| PICSAR | 26.05 | — |
| pyAMReX | 26.05 | — |
| pybind11 | v3.0.4 | — |
| picmistandard | 0.34.0 | `368db4a7fe7f98f4915209702930e08c59769717` |

AMReX/PICSAR/pyAMReX are fetched by CMake at configure time from the pins in
the WarpX checkout's `dependencies.json` — they are not vendored here. The
runtime banner in every log prints `AMReX (26.05-63-gc2eb6db7ee79)`, which is
the fetched AMReX commit above.

### Configure and build

The build directory is inside the WarpX checkout root (repo convention — never
outside the working tree):

```bash
conda activate warpx-cpu-mpich-dev
cd /home/rsc/Desktop/repos/warpequisd            # the WarpX checkout, NOT this repo

cmake --fresh -S . -B build \
  -DCMAKE_BUILD_TYPE=Release \
  -DWarpX_DIMS="3;RZ" \
  -DWarpX_COMPUTE=CUDA \
  -DAMReX_CUDA_ARCH=8.6 \
  -DWarpX_EB=ON \
  -DWarpX_PYTHON=ON \
  -DWarpX_OPENPMD=ON \
  -DWarpX_MPI=ON \
  -DWarpX_MPI_THREAD_MULTIPLE=ON \
  -DWarpX_QED=ON \
  -DWarpX_FFT=OFF \
  -DWarpX_PRECISION=DOUBLE \
  -DWarpX_PARTICLE_PRECISION=DOUBLE \
  -DWarpX_IPO=OFF \
  -DWarpX_PYTHON_IPO=OFF \
  -DWarpX_CCACHE=ON

cmake --build build -j 8 --target pip_install
```

That last target compiles **and** installs `pywarpx` into the active
environment. After a source edit, `--target pip_install_nodeps` is faster.

### Which flags matter, and why

| flag | value | why the campaign needs it |
|---|---|---|
| `WarpX_DIMS` | `3;RZ` | every stage is **RZ** (cylindrical, `n_azimuthal_modes=1`). `3` is built only so the upstream test suite still runs; nothing in this repo uses it. Building `RZ` alone is enough and roughly halves compile time. |
| `WarpX_COMPUTE` | `CUDA` | the capstone runs are 9–10 GPU-hours each; CPU is not viable for them. The four `current_collection` steps are CPU-cheap and run either way. |
| `AMReX_CUDA_ARCH` | `8.6` | **change this for your GPU** (Ampere consumer = 8.6, A100 = 8.0, Ada = 8.9, Hopper = 9.0). |
| `WarpX_EB` | `ON` | **mandatory.** The whole device is an embedded-boundary conductor with a two-node piecewise Dirichlet potential. Without EB nothing above `emitter.negative_cathode` builds a geometry. |
| `WarpX_PYTHON` | `ON` | **mandatory.** Every stage is a PICMI Python deck driving `libwarpx` in-process; the charge pump reads and writes the EB potential *between steps*, which no input-file run can do. |
| `WarpX_OPENPMD` | `ON` | **mandatory.** Analysis reads openPMD field dumps (`phi`, `rho`, `Er`, `Ez`) via `openpmd-viewer`; the sheath-containment and energy-ledger gates are computed from them. |
| `WarpX_PRECISION`, `WarpX_PARTICLE_PRECISION` | `DOUBLE` | the charge pump integrates a current balance over ~160 000 steps; the ledger-vs-dump gates hold to 1e-9 in double and would not in single. |
| `WarpX_FFT` | `OFF` | no spectral solver is used — every stage is electrostatic multigrid (`ElectrostaticSolver(method="Multigrid")`). |
| `WarpX_QED` | `ON` | upstream default; unused by this campaign. `OFF` is fine and builds faster. |
| `WarpX_IPO`, `WarpX_PYTHON_IPO` | `OFF` | link-time optimisation off — upstream's documented developer setting for fast link times. |
| `WarpX_CCACHE` | `ON` | rebuild speed only. |
| `WarpX_MPI` | `ON` | compiled in, **not exercised**: all committed evidence is single-rank. |

### Verify the build

```bash
conda activate warpx-cpu-mpich-dev
python -c "from pywarpx import picmi; print('picmi ok')"
python -c "import importlib.metadata as m; print('pywarpx', m.version('pywarpx'))"   # -> 26.5

# cheapest real check: the vacuum two-node EB stage (seconds, exact references)
cd electron_thruster_3/pic_sims
python run_ladder.py --check                       # contract + topology, no GPU
python run_ladder.py --stages capstone.two_node_laplace
```

If `run_ladder.py --check` passes but a stage aborts with
`Arena out of memory / cudaMalloc returned 2`, see §6.

---

## 4. Running the ladder

```bash
conda activate warpx-cpu-mpich-dev
cd pic_sims
```

| goal | command |
|---|---|
| validate the contract and stage topology, no simulation | `python run_ladder.py --check` |
| run + analyze the whole ladder group, in dependency order | `python run_ladder.py` |
| run a characterization spoke (see `thruster_characterization/`) | `python run_ladder.py --stages characterization.slender_body` |
| one stage (dependencies must already have passed) | `python run_ladder.py --stages capstone.floating_body` |
| re-analyze existing runs without re-simulating | `python run_ladder.py --analyze-only` |

The orchestrator runs each stage in a **fresh subprocess** — `libwarpx` cannot
initialise twice in one process, so a stage is never imported.

### Stage order and cost

Costs are measured on the §1 machine.

```
electron_gun/                 EMITTER side
  1_negative_cathode   emitter.negative_cathode    plane diode, no EB        ~3 min
  2_electron_gun       emitter.holed_anode         + holed anode, 3 scenarios ~10 min
current_collection/           COLLECTOR side
  1_thermal            collector.thermal           sphere at 0 V, exact      ~16 min
  2_biased_3v          collector.biased_3v         OML ceiling, chi = 26.4   ~65 min
  3_biased_10v         collector.biased_10v        sheath growth, chi = 88   ~80 min
  4_floating           collector.floating          charge pump -> phi_f      ~35 min
capstone/                     THE DEVICE (ladder terminus)
  1_two_node_laplace   capstone.two_node_laplace   two-node EB in vacuum     seconds
  2_chipsat_thruster   capstone.floating_body      200 V anchor              ~6.3 h

../thruster_characterization/   SPOKES OFF THE ANCHOR (run via --stages)
  high_thrust          capstone.high_thrust        300 V, 192 680 steps      7 h 14 min
  low_power            capstone.low_power          100 V, 115 480 steps      4 h 56 min
  slender_body         characterization.slender_body   geometry, L/r = 6     ~6.5 h
  thin_plasma          characterization.thin_plasma    density, n0/3         ~7 h
  magnetized_1x        characterization.magnetized_1x  Bz 30 uT (1x LEO)     ~6.4 h
  magnetized_10x       characterization.magnetized_10x Bz 300 uT (10x)       ~6.4 h
```

A full cold ladder is roughly **20 GPU-hours**, dominated by the three capstone
frontier runs. The lower steps are what let you trust the top one; run them once
and they stay valid until a config or the code changes.

### Running one stage directly

`run_ladder.py` is a wrapper. A stage is self-contained and runs on its own:

```bash
cd ladder/capstone/2_chipsat_thruster
python simulation.py                                  # uses the committed config.yaml
python analyze.py --run outputs/<run-id>              # --run is REQUIRED
python analyze.py --run outputs/<run-id> --policy acceptance_exploratory.yaml
```

`analyze.py` writes `metrics.json` + `verdict.json` and exits **0** if all
required gates pass, **1** if a gate fails, **2** on invalid evidence.

### Variant runs — how the frontier, convergence, and geometry runs were done

**Committed stage configs are never edited.** Every off-baseline run (the
convergence pair, the slender-body geometry run, the pre-registered thin-plasma
run) is a *copy* of the stage config with a few keys changed, passed with
`--config`:

```bash
cp config.yaml /tmp/my_variant.yaml
$EDITOR /tmp/my_variant.yaml
python simulation.py --config /tmp/my_variant.yaml
```

The run freezes its own `config_used.yaml` and hashes it into `case_sha256`, so
a variant is fully self-describing without touching git. Variants that answer a
pre-registered question get a plan document committed *before* they run —
`pic_sims/thruster_characterization/slender_body/SLENDER_BODY_PLAN.md`, `pic_sims/thruster_characterization/thin_plasma/THIN_PLASMA_PLAN.md` — and, when the
default gates would gate the answer rather than the trustworthiness of the
measurement, their own acceptance policy (`acceptance_exploratory.yaml`).

### Long runs that must survive the terminal

```bash
setsid nohup conda run --no-capture-output -n warpx-cpu-mpich-dev \
    python simulation.py --config /path/to/variant.yaml \
    > run.log 2>&1 < /dev/null &
```

`setsid` detaches from the session; `conda run --no-capture-output` keeps the
log unbuffered so progress is readable live. Watch with
`tail -f run.log` or `tail -2 outputs/<run-id>/diags/contactor_log.csv`.

---

## 5. The other trees

```bash
# orbit demand side  (see orbit_sims/README.md for IRI data setup)
conda activate tudat-sk
cd orbit_sims && python3 run_station_keeping.py 400km_station_keeping_chipsat

# minimal model: calibrate from committed reference_results, sweep every mission
conda activate warpx-cpu-mpich-dev
python model/minimal_model.py --calibrate
python model/minimal_model.py --all          # -> model/results/

# paper figures (read committed calibration + summaries; no hand-typed numbers)
cd paper/figs && python make_frontier.py && python make_missions.py && python make_fpplane.py

# paper and slides
cd paper && pdflatex main.tex && pdflatex main.tex
cd paper/slides && pdflatex slides.tex && pdflatex slides.tex
```

Stage unit tests (no WarpX, no GPU, ~4 s for all 278):

```bash
for d in pic_sims/ladder/tests pic_sims/ladder/*/*/tests; do
    PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest "$d" -q
done
```

**One pytest process per stage is required, not a stylistic choice.** Stage
self-containment (§Architecture in `pic_sims/ladder/README.md`) means
every stage ships its own `helpers.py`, `tests/test_helpers.py` and
`tests/test_analysis.py`, and each `tests/conftest.py` puts *its own* stage
directory on `sys.path`. Collecting them in one process collides on those
module basenames — `pytest pic_sims/ladder` fails with
`import file mismatch` / wrong-`helpers` errors, and `--import-mode=importlib`
only fixes half of them. The loop above is the working invocation; it is also
what `run_ladder.py` effectively does by running each stage in a subprocess.

`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` avoids unrelated plugins in `~/.local`
being auto-loaded into the conda environment and failing on missing imports.

Expected counts: shared contract 49, `two_node_laplace` 20,
`chipsat_thruster` 38, `high_thrust` 37, `low_power` 37, `thermal` 17,
`biased_3v` 12, `biased_10v` 11, `floating` 23, `negative_cathode` 17,
`electron_gun` 17.

---

## 6. GPU memory — the one setting you will have to tune

`compute.gpu_arena_bytes` in each stage config pre-allocates the AMReX device
arena. It is a hard reservation: the process resides at roughly that size for
its whole life. Measured on the 12 GiB card:

| domain | cells | `gpu_arena_bytes` | resident |
|---|---|---|---|
| capstone baseline (rmax 30 mm) | 200 × 440 = 88 000 | `6000000000` | ~5.8 GiB |
| slender / thin-plasma variants | ~120 000 | `9000000000` | ~8.7 GiB |

Rules learned the expensive way:

- **Never run two simulations on one GPU.** Two arenas will not fit and the
  second aborts with `amrex::Abort: Arena out of memory / cudaMalloc returned 2`
  — which also kills nothing but wastes the slot. Chain runs instead, and arm
  the chain on the *first* run's `manifest.json` containing the literal string
  `"status": "COMPLETE"` — **not** on the file existing, which it does from run
  start with `status: RUNNING`.
- Grow the arena when you grow the domain. Cells scale as `rmax * Lz / dx²`, and
  the axial extent is derived (`domain.aspect`, `zmargin_*`), so a radial change
  can enlarge the domain in both directions at once — check `nr × nz` with
  `helpers.load_config(...)` before launching, not after.
- Desktop GPU use (a browser, a game) costs a few hundred MiB and is survivable
  at the 6 GB arena, tight at 9 GB.

---

## 7. Evidence rules that constrain how you run things

These are contract, not style. They are why the numbers in the paper are
citable.

1. **A run is evidence only if its `manifest.json` says `status: COMPLETE`** and
   `observed_final_iteration == expected_final_iteration`.
2. **An interrupted run is FAILED evidence and is never resumed.** Kill it,
   record why, rerun from the top. There is no checkpoint path on purpose.
3. **Committed stage configs and acceptance policies are immutable.** Changing a
   tolerance requires a new `policy_id`; every verdict records the policy's
   SHA-256 and the config's `case_sha256`.
4. **Commit before launching a production run.** The manifest records
   `git_commit` and `git_dirty`; a dirty tree makes the run unciteable.
5. **Pre-register predictions before the run that tests them**, in a committed
   plan document. `SLENDER_BODY_PLAN.md` also carries an *amendment* recording a
   killed, invalid run rather than quietly rewriting the original plan.
6. `random_seed: 42` everywhere; it is recorded in every manifest.
