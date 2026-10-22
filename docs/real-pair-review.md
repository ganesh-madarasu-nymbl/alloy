# Real paper pair: Brunton 2016 vs Kaheman 2020

Reviewed 21 Oct 2026. Sources and blockers are in `data/evidence/sindy_review.json`; every number
below comes from `uv run python scripts/real_pair_probe.py` (about two minutes).

## The disagreement

| | Brunton, Proctor & Kutz 2016 ([1509.03580](https://arxiv.org/abs/1509.03580)) | Kaheman, Brunton & Kutz 2020 ([2009.08810](https://arxiv.org/abs/2009.08810)) |
|---|---|---|
| Result | SINDy recovers Lorenz (Table 4, noise variance 1; form holds up to 10) | Original SINDy fails above 8% noise (Fig. 14 bar label) |
| Where the noise goes | Derivative targets; library built from clean states | State measurements, then finite differences |
| Record | x0 (-8, 7, 27), dt 0.001, t 0 to 100 (100,000 samples) | x0 (5, 5, 25), dt 0.01, t 0 to 25 (2,500 samples) |
| Library | Polynomials up to degree 5 | Not stated for original SINDy (degree 2 assumed) |
| Threshold | Not stated (0.025 from released code) | 100 values from 0.01 to 1; selection rule not stated |

Both use Gaussian noise and the standard Lorenz parameters. Brunton's noise (standard deviation 1)
is small next to the derivatives (standard deviation 44 to 81), while 8% of the state variance
(61 to 80) is noise of variance 5 to 6 on the states, so the absolute numbers are not directly
comparable. The question is which setting decides the outcome.

## What Alloy measured

| Run | Recovered |
|---|---|
| Brunton protocol, variance 1 on exact derivatives, ridge 0 | yes (coefficient error 0.0002) |
| Same, variance 10 | yes (0.0006) |
| Same, with pysindy's default ridge 0.05 | no |
| **Brunton record, variance 1 moved onto the states, finite differences** | **0 of 5 seeds** (error 0.50 to 1.02) |
| Kaheman protocol, 8% as Eq. 19's variance ratio | 0 of 5 datasets |
| Kaheman protocol, 8% as a standard-deviation ratio | 1 of 5 (all 5 at 6%, none from 10%) |
| Kaheman record, 8% variance ratio moved onto exact derivatives | 2 of 5 |

Kaheman's recovery counts a dataset as recovered if any of the 100 thresholds yields exactly the
true terms; the paper does not say how a threshold is picked.

## Findings

1. **Noise placement decides the outcome.** On Brunton's own record, moving the same noise from
   the derivatives to the states turns recovery into failure on every seed. Finite differences
   amplify state noise by about 1/dt and corrupt the library as well as the targets.
2. **Record length is secondary.** On Kaheman's short record, moving noise to the derivatives
   only lifts recovery from 0 to 2 of 5 datasets.
3. **Kaheman's noise unit is ambiguous.** Eq. 19 defines the noise level as a variance ratio, but
   under that reading original SINDy fails from about 0.5%, not 8%. Read as a standard-deviation
   ratio, the reproduced limit (6%) is close to the reported 8%. Section 4.4 uses a third
   convention (noise multiplied by percentage x var(signal)). We report this as consistent with a
   standard-deviation ratio, not as proof.
4. **Brunton's result needs plain least squares.** pysindy's default ridge penalty (0.05) loses the
   small linear terms in an unnormalised degree-5 library. The paper's Code 1 uses plain least squares.

## Why the pair is still not "eligible"

Alloy's exact-reproduction gate needs every setting stated in the paper. Brunton's threshold and
derivative construction, and Kaheman's threshold rule, library and finite-difference scheme, are
not, and Kaheman's 8% comes from a figure label rather than prose. `uv run alloy evidence-check`
lists these blockers. The runs above therefore use labeled assumptions; they show which condition
matters, not an exact replication of either paper.

## Adapter settings added for this review

`x0`, `poly_degree` (1 to 5), `noise_location` (`state` or `derivative`), `noise_scale`
(`state_std`, `absolute`, `variance`), `derivative` (`numeric` or `exact`), `ensemble_models`
and `ridge`. All are optional; omitted settings keep the original adapter behaviour. A
`recovered` metric (exactly the true terms) supports qualitative claims.
