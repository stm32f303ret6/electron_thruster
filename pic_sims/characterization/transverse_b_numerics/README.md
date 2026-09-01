# characterization.transverse_b_numerics: the mini-ladder under the transverse-B measurement

Single test electrons on the exact grid (64 × 64 × 72 at 1.0 mm) and time
step (36.7 ps) of `../magnetized_transverse/`, pushed by the same Boris /
electrostatic machinery with the same applied-field mechanism, against closed
forms. Each gate is a numerics claim the measurement rides on. The design
note for tier M2 (`../../../future_work/M2_TRANSVERSE_B.md`) asked for exactly
this before any measurement run: "single-particle gyro-orbit vs exact r_g and
T_ce on the coarse grid; E×B drift vs analytic". Pre-registered 2026-09-01.

| scenario | what | closed form | gate |
|---|---|---|---|
| `gyro_1x` | 164.5 eV electron launched along +z in Bx = 30 µT (r_g = 1.44 m; a 2.4° arc fits the box) | ω_c = eB/m, r_g = p/(eB), KE constant | ω to 0.2 %, r_g to 0.5 %, KE to 10⁻⁶ |
| `gyro_10x` | the same in Bx = 300 µT (r_g = 144 mm, a 25° arc) | same | same |
| `exb_10x` | electron born at rest in Bx = 300 µT and Ez = 30 V/m (z-face potentials, x,y periodic) over three gyroperiods | v_d = Ez/Bx = 10⁵ m/s along +y, no z drift | v_d to 1 %, v_z/v_d < 2 % |

The trajectory is the `BeamRelevant` reduced diagnostic (mean position and
momentum of the one particle, every step). Frequency from the rotation of
(p_y, p_z); radius from an algebraic circle fit to (y, z); drift from a
least-squares fit `y(t) = y0 + v t + A cos ω_c t + B sin ω_c t`.

## Results

Pending (2026-09-01).

## Dependencies

Requires `capstone.floating_body` per the spoke rule. Run before
`characterization.magnetized_transverse`.

## Cost

Seconds to a few minutes per scenario (a Poisson solve per step on the
measurement grid, one particle).

## Commands

```bash
python simulation.py --scenario gyro_1x        # gyro_10x, exb_10x
python analyze.py --runs outputs/<gyro_1x> outputs/<gyro_10x> outputs/<exb_10x>
```
