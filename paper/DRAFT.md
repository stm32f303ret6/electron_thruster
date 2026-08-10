# draft — ambient-electron exchange thruster (concept-first)

working skeleton for `main.tex`. same order as the paper, note form.
edit here first, port to prose after.

## 0. claim (one paragraph)

- thruster with **no propellant, no tank, no neutralizer**: cold electron gun
  inside a sealed floating body, one aperture, ionosphere closes the circuit.
- concept = a parameter-free ideal law; pic runs = evidence that a real
  geometry sits within ~20 % of it.
- mission corridor (chipsat + any same-shape body): closes on skin-harvested
  power at 550–600 km, impulse-closes at 500 km, fails honestly at 400 km.

## 1. why (intro)

- small sats below ~600 km die to drag in months–years.
- needed: nN–µN continuous thrust from mW-class power → **no flight system
  lives there** (smallest flight EP: ~5–30 µN at 8+ W, in 0.3–1 kg packages).
- idea: run the neutralizer *as* the thruster. fire electrons out, body
  charges +, ambient electrons return through the skin. propellant mass flow:
  ~ng/year, all from the ionosphere.
- five contributions:
  1. parameter-free ideal law + measured frontier validates it (within 20 %)
  2. collection law discriminated (pre-registered) → charging tax fixed
  3. momentum ledger: the return current does not cancel thrust
  4. mission corridor from year-long propagations, extrapolation flagged
  5. shape run → size cancels; corridor carries to cubesats unchanged

## 2. operating principle (the cycle)

1. supply holds cathode at $-V$ vs body → electrons accelerate away, exit
   through the aperture.
2. exit energy $\approx e(V-\varphi)$ minus space charge (measured
   KE/(V−φ) = 0.81, constant over the range).
3. each departure leaves the body +1 charge → body floats up (measured
   +16.98 V at 200 V).
4. positive body collects ambient electrons until collected = escaped
   (balance closes to 1.5–3.5 % at all points).
5. escaping beam momentum = thrust; returning electrons deposit ~1–9 %
   (gated per run).

no valves, no gimbal, no plasma stage. throttle = $(V, I)$ only.

## 3. the ideal law (the concept — before any simulation)

- beam momentum flux, nothing but $m_e$ and $e$:

$$F = \sqrt{2 m_e / e}\; I \sqrt{KE}, \qquad \sqrt{2 m_e/e} = 3.37\ \text{nN/(mA}\sqrt{\text{eV}})$$

- ideal beam-supply power $P = VI$ → fixed-thrust power law:

$$P = \frac{F \sqrt{V}}{c_{ideal}}, \qquad c_{ideal} = \sqrt{2 m_e/e}$$

- **throttle principle**: largest feasible escaped current, lowest voltage
  that meets the thrust demand.
- feasible current bounded by (acknowledge, don't optimize):
  - emitter ceiling
  - ambient return-current availability
  - acceptable spacecraft potential
  - beam escape
- this law is the concept; the rest of the paper is evidence:
  - how close does a real geometry get? → §5.1 (within 20 %)
  - does the form survive? → §5 ($1/\sqrt{V}$ within 2.5 %)
  - what sets the return current? → §6 (collection law)

## 4. simulation method + evidence contract

- warpx 26.5, RZ electrostatic, embedded-boundary conductor, charge-pump
  float (emitted − collected → φ via gauss-law capacitance).
- deck: ⌀10 mm × 5.9 mm can, 4 mm aperture, internal cathode disk.
  plasma row: $n_e = 1.627{\cdot}10^{12}$ m⁻³, $kT_e = 113.6$ meV,
  reservoir recycle. dx = 0.15 mm (debye 1.97 mm), CFL dt, 16 ppc,
  reduced ion mass 400 $m_e$, 800 ns/run.
- evidence contract:
  - frozen + hashed configs, atomic manifests, interrupted runs discarded
  - gates fixed in versioned policy files **before** each run
  - 100/300 V predictions + collection-law hypotheses pre-registered
  - validation ladder underneath (laplace, thermal ±1 %, biased, floating,
    gun rungs); ledger-vs-dump cross-checks ~1e-9

## 5. measured frontier

| V | I (mA) | φ (V) | F (nN) | P (mW) | F/P (µN/W) | escape | KE (eV) |
|---|---|---|---|---|---|---|---|
| 100 | 0.121 | +5.40 | 3.42 | 12.1 | 0.283 | 96.1 % | 77.2 |
| 200 | 0.342 | +16.98 | 13.65 | 68.4 | 0.200 | 98.4 % | 147.5 |
| 300 | 0.630 | +36.30 | 30.13 | 189 | 0.159 | 99.0 % | 210.1 |

- fixed $I/I_{CL} = 1.46$ along the path (self-similar optics).
- 100/300 V thrusts landed on pre-registered predictions to <1 %.
- $F/P \propto 1/\sqrt{V}$ confirmed within 2.5 %.
- two efficiencies, side by side on purpose:
  - energy conversion $\eta \approx 0.73$ (ion-thruster class)
  - impulse economy ~0.2 µN/W (~200× below gridded ion)
  - first explains why it deserves the nN regime, second why it owns
    nothing above it.
- error band (grid): F ±4 %, KE ±7 %, φ ±2 %.

### 5.1 validation vs the ideal law

measured / bound = **1.19–1.22** at all three points. the gap is a closed
ledger:

| tax | value | mechanism | cost |
|---|---|---|---|
| energy fraction κ | 0.81 | injection-plane space charge | ~10 % |
| thrust slope $c_F$ | 0.97 $c_{ideal}$ | plume divergence | ~3 % |
| float tax $V/(V-\varphi)$ | 1.06–1.14 | body charging | 6–14 % |

- with measured constants ($c_{eff} = c_F\sqrt{\kappa} = 0.87\,c_{ideal}$)
  the law reproduces all three powers to 4–6 %:
  model 11.7 / 65.8 / 177.9 vs measured 12.1 / 68.4 / 189 mW.
- off-optimum (low V, fixed thrust): 1.5–2× the bound. decomposes into
  (i) non-optimal voltage, (ii) beam interception in the can (isolated gun
  transmits 99.99 % at the same command). geometry-specific, not the law.
- confirmation inside committed data: model-optimal V for 13.65 nN is
  **196 V** → the 200 V anchor *is* that run (closes to 4 %, escape 98.4 %).
  the divergent points all commanded 2.7–10× over the emission ceiling —
  voltages the throttle principle never selects.
- role of pic: **prove the concept, not certify a mission thruster.**
  missions use the measured (conservative) calibration.

## 6. collection law (pre-registered discrimination)

$$I = \beta A\, j_{th}(n_e, T_e)\,(1+\chi)^\alpha, \qquad \chi = e\varphi/kT_e$$

predictions recorded before the 300 V run (all agree at 200 V anchor):

| α | predicted φ(300 V) | verdict |
|---|---|---|
| 1 (linear) | +31 V | refuted (float passes 31, keeps climbing) |
| 0.82 ± 0.06 | +36 V | **survives** (measured +36.30 V) |
| 0.5 (sqrt) | +90 V | refuted (nothing approaches 90) |

- caveat (pre-registered): 300 V still relaxing at 800 ns; settled
  extrapolation 42–48 V, brushes the 50 V limit. fit across all three
  points: α = 0.85–0.89.
- this law = the charging tax schedule: φ eats 5 % of supply at 100 V,
  12 % at 300 V.

## 7. momentum ledger — is the thrust real?

- objection: emitted current *returns*. does it cancel?
- predecessor (⌀14 mm, 800 V): full control-volume ledger every window.
  - vacuum fixture: residual +0.80 nN vs 1 nN gate
  - full-return null (escape 0 %): closed thrust −0.39 nN ≈ 0 ✓
  - operating point: closed thrust = $F_{beam}$ − 2.3 %; impact channel
    cancelled by field pull, not by the beam
- this campaign: $|F_{net}|/F_{beam}$ gated per run — 1.0 % (300 V) to
  8.8 % (100 V).
- physics ceiling: even all-astern arrival ≤ $\sqrt{\varphi/KE} \approx 41$ %;
  isotropic arrival → measured percent level.

## 8. numerical credibility

| axis | result |
|---|---|
| code-to-code (migrated vs predecessor, 200 V) | float 0.05 %, escape 0.001 %, F 0.09 % |
| thermal collection vs theory | ±1 % |
| ledger vs particle dumps | ~1e-9 (gate 2e-2) |
| ppc ×2 | ≤0.05 % — closed axis |
| grid 0.15→0.10 mm | F +4.0 %, KE +7.4 %, φ −1.8 % → the error band |
| dt, seed (predecessor) | ≤0.5 % |

- grid = leading uncertainty; sign is conservative for every gate
  (finer → more thrust, lower float). third grid point = future work.

## 9. comparison

- every incumbent's lowest operating power ≥ 10× our 300 V ceiling point;
  FEEP starts at ~8 W.
- jet efficiencies found: electrospray 28–45 %, FEEP ~35 %, hall ~31–44 %.
  ours: 68–73 % — exceeds every value found.
- but F/P ~200× below gridded ion → natural handoff: this device
  <0.1 µN, electrospray at µN, ion/hall at mN. that boundary is part of
  the claim.
- "continuous thrust" argument at nN is a **dry-system floor** argument
  (tank+feed+PPU ~0.3–1 kg does not shrink), not a propellant-mass one.

## 10. missions (year-long, real F10.7/Ap, IRI + NRLMSISE, per-5-min rows)

model applies the throttle principle per row, solves min-power $(V,I,\varphi)$
self-consistently with the collection law; out-of-envelope rows flagged,
never averaged in.

| altitude/pose | drag mean/max (nN) | feasible | duty | P mean (mW) | verdict |
|---|---|---|---|---|---|
| 400 axial | 32.9 / 92.4 | 21 % | 140 % | 136 | fails |
| 400 lateral | 21.7 / 60.7 | 54 % | 92 % | 111 | fails (power) |
| 500 axial | 7.6 / 28.4 | 81 % | 45 % | 39 | impulse-closes, power-bound |
| 550 axial | 3.8 / 16.3 | 92 % | 32 % | 17 | **closes** (~30 mW harvest) |
| 600 axial | 2.0 / 9.6 | 97 % | 25 % | 8 | **closes** |

- honesty flags: night rows drive the boundary and are exactly the
  unmeasured density axis (thin-plasma run = first item of future work);
  powers are beam power $VI$ only.
- why 400 km fails even ideally:
  1. impulse: peak drag needs 510 V; demand > ceiling 63 % of the time;
     duty 140 % — no battery fixes >100 %.
  2. energy: ideal-bound power at best V ≈ 98 mW vs ~30 mW harvest.
     drag wants ~1450 W/m² of ram; cells give ~100 W/m² of skin; best
     shape ratio 14 → margin 0.3.

## 11. geometry + scale-free

- slender run (⌀10 × 30.5 mm, skin ×3.24, same drive/grid/seed):
  φ 16.98 → **4.38 V** (area-only hypothesis confirmed, cylinder-limit
  refuted ~10×), thrust *up* to 14.22 nN (lower float returns drive
  energy). escape 98.4 %.
- drag buys the **ram silhouette**; collection + solar buy the **skin** →
  both sides of the power balance are areal → **size cancels**. what
  survives: shape ratio + altitude.

| body (skin/ram) | 400 | 500 | 550 | 600 km |
|---|---|---|---|---|
| squat can (4) | 0.1 | 0.4 | 0.8 | 1.6 |
| 1U face-on (6) | 0.1 | 0.6 | 1.2 | 2.3 |
| slender can / 3U end-on (14) | 0.3 | **1.4** | **2.8** | **5.4** |
| 6U end-on (12) | 0.3 | 1.2 | 2.4 | 4.6 |

(margin = harvest/demand at 100 V; >1 closes. 3U at 600 km: 8.8 mA,
0.88 W — cubesat-supply class.)

- larger bodies need *less* enhancement over bare thermal flux (4.3× vs
  15×) → **less extrapolation, not more**.
- caveat: cubesat radii are 25–60 $\lambda_D$ (thin-sheath regime, not
  measured). child-sheath estimate: benign at 550–600, tight at 500.
  single large-body run settles it — cheapest follow-on.

## 12. practical

- bom: conducting structure, mW-class HV supply (100–300 V), cold gun,
  aperture. no tank/valves/feed/RF/gimbal. floor = cathode + boost
  converter + the skin itself.
- retrofit: ion/hall neutralizer + spacecraft structure *is* this
  thruster after propellant exhaustion — software + wiring.
- lab demo: TODO (user's vacuum-chamber bench results).

## 13. limitations (state plainly)

1. collection law's density axis: one dayside row measured. night rows =
   extrapolation (thin-plasma run pending settle).
2. geometry axis: two points (L/r 0.6 and 6), not a map.
3. no run in the cubesat sheath regime (r/λ_D ≈ 2.5 measured vs 25–60).
4. grid resolution ±4–7 %, sign conservative.
5. 300 V float unsettled at 800 ns (42–48 V band carried).
6. reduced ion mass 400 $m_e$ (not O⁺).
7. stationary plasma (no ram wake — deferred, not estimated).
8. RZ axisymmetric, no geomagnetic field.
9. beam power only (no gate/converter overheads).
10. throttle optimization deferred: quoted powers = ideal bound + measured
    closure; off-optimum losses geometry-specific
    (→ `future_work/OPTIMIZATION_LEVERS.md`).

## 14. conclusion (three results)

1. measured frontier validates the parameter-free law: within 20 % of the
   bound, $1/\sqrt{V}$ within 2.5 %, η ≈ 0.73 at 0.16–0.28 µN/W.
2. the thrust is real: ledger + full-return null + per-run gates (1–9 %).
3. collection law fixes the charging tax → conservative model → corridor:
   closes 550–600, impulse 500, fails 400 — and by the areal argument the
   corridor is a statement about shape and altitude, not size.

cheap to test: a gun and a hole. retrofit path exists on every flying
ion/hall neutralizer.
