# perp_sim_min — minimal BTC perpetual-futures simulator

A deliberately small version of the Phase-0 `perp_sim`, for the FYP
*"Risk Monitoring for LLM Trading Agents"*. The goal of this cut is **fewer
moving parts**: when a risk number looks wrong, you should be able to tell which
component caused it. Roughly half the Phase-0 surface area is gone, and no claim
the project actually makes is weakened.

## The one idea that licenses the cuts

The project compares risk **relatively** — same market, same settings, only the
agent mix changes — and does **not** claim the simulator matches real BTC in
absolute terms. So the market only has to be *reasonable and fixed*, not *fitted*.
That means the entire absolute-calibration apparatus (method-of-simulated-moments
grid search, hand-set weights, tolerance bands, held-out "validation") can go. We
set parameters once to plausible values and validate **qualitatively** instead
(`sanity.py`).

## The causal spine (kept — do not cut)

    agent takes a leveraged position
      -> price moves
        -> margin breach
          -> forced liquidation hits the book
            -> book impact drags the mark
              -> next breach   ... = the cascade

Everything needed for that chain is kept:

| File | Role | Status |
|---|---|---|
| `engine/orderbook.py` | the limit order book + matching | **verbatim** from Phase-0 |
| `engine/accounts.py` | cash, position, margin maths | **verbatim** from Phase-0 |
| `engine/exchange.py` | matching + mark price + **liquidation engine** | trimmed |
| `engine/index_price.py` | exogenous reference price | GBM + jumps only |
| `engine/flow.py` | anonymous aggressive flow (demand) | trimmed |
| `agents.py` | one liquidatable archetype + LLM hook | new (replaces the bot zoo) |
| `population.py` | fixed slots + replace-not-add swap | trimmed |

The liquidation **mechanism** (multi-round forced closing, bad-debt sweep,
`mark = median(index, last, book-mid)` so a falling book feeds the cascade) is
unchanged — that is the phenomenon under study.

## What was cut, and why

| Cut | Why it's safe |
|---|---|
| **Absolute calibration pipeline** (`data/scripts/*`, MSM grid, scale calibration) | Only serves absolute claims we don't make; was the main source of judgement-laden, contradictory artifacts. |
| **One of two liquidity sources** (MakerBots) | The exchange background LP is now the *only* resting liquidity. Phase-0 had LP + MakerBots + taker flow — that overlap caused the flow/depth scale conflict. |
| **Funding** | Hourly, tiny, and was an uncalibrated default; irrelevant on a minutes-horizon cascade study. |
| **Four of five bot archetypes** | Trend/contrarian/value/crowd + their invented thresholds collapse to one leveraged position-taker, so a risk move is attributable to the agent mix, not a four-type interaction. |
| **Historical replay** | Kept the environment synthetic-only; removes a second validation burden and the confusing "-2.4× vs half" crash-replay artifact. |
| **Circuit breaker** | That's a Phase-2 *intervention*, not part of the baseline model. Re-add it as a toggle when you test interventions. |
| **Scenario matrix** (2×2×3 = 12) | Collapsed to two: `normal` and `stress`. |

## What was simplified but kept

- **Exogenous driver:** GBM + jumps + one optional scheduled shock (stress).
- **Volatility clustering:** restored as a hand-set AR(1) multiplier on the index
  vol (`vol_cluster_rho`, `vol_cluster_vov`) — NOT fitted. It was originally cut
  because Phase-0 couldn't *calibrate* it to 0.27; since we no longer calibrate,
  it only needs to be present and reasonable. It is the temporal structure that
  packs volatility into episodes, which is where cascades build.
- **Mark vs last price:** kept distinct on purpose — liquidating on `last` makes
  cascades trivially self-reinforcing; `mark = median(index, last, mid)` keeps
  them sane. This realism is load-bearing.
- **Replace-not-add swap:** the good part of Phase-0's population design is intact
  — fixed slots, seed-stable swap order, constant total capital, so n_llm is the
  only thing that changes between a control and a treatment run.
- **Queue-reactive-*inspired* flow:** the taker flow keeps two cheap properties of
  the Huang–Lehalle–Rosenbaum model (rate rises with volatility; flow leans to the
  thinner book side) without estimating queue intensities from L2 data.

## Validation — qualitative only, on purpose (`sanity.py`)

Two cheap, honest checks replace the calibration grid:

**A. Stylized facts** (does it behave like a market?) — sign/direction checks, not
"match real BTC to X%": fat tails (kurtosis > 3), volatility clustering
(squared-return ACF1 > 0), positive price impact (buys push up).

**B. Power check** (the important one): with scripted traders only, sweep leverage
and confirm liquidations respond. *If the instrument can't register a known
perturbation, it can't register an agent effect.* **Run this before any Phase-1
agent experiment.**

Current output (5 seeds / 3 seeds):

    A. fat tails      kurtosis   = 9.12   PASS   (real BTC ~10)
       vol clustering sq-ret ACF1= 0.090  PASS   (real ~0.27 — moderate, see caveat)
       price impact   slope      > 0      PASS
    B. leverage  2x ->   0.0 liquidations
       leverage  5x ->   0.0
       leverage 10x ->   0.0
       leverage 20x -> 738.0            monotone + detectable PASS

### Two honest caveats
- **Volatility clustering is moderate, not matched** (ACF ~0.09–0.12 vs real ~0.27).
  It is deliberately *not* pushed to 0.27: with a single AR(1) multiplier, raising
  it to 0.27 drags kurtosis to 14–22 (real ~10). A one-parameter vol process can't
  hit both targets at once — matching both would need a richer (GARCH/regime) vol
  model, which is more than a relative-comparison design needs. Present + plausible
  is the right call here; chasing 0.27 would be re-introducing the fitting we cut.
- **The power check passes but as a cliff** (0 liquidations up to 10×, then ~740 at
  20×). The instrument is insensitive to risk until extreme leverage. Before Phase
  1, tune the baseline so the risk metric responds across a *usable* range — e.g.
  raise the default leverage band, deepen the stress drawdown, or thin the LP depth
  — so agent effects are detectable without needing 20×.

## Run it

    python run.py --scenario normal --steps 600 --seed 0 --out run.csv
    python run.py --scenario stress --steps 600 --seed 0
    python sanity.py            # stylized facts + power check
    python -m pytest tests/ -q  # 7 tests: book, margin, cascade, fairness

## Plugging in LLM agents (Phase 1)

`population.build_population(seed, spec, n_llm=k, llm_factory=...)` swaps the first
`k` slots for agents. The factory returns an object with `account_id` and
`act(view) -> [OrderRequest/CancelAll]` — same contract as `agents.PositionTaker`.
See the skeleton at the bottom of `agents.py`. `n_llm=0` is the all-scripted
control; nothing else about the market changes when you raise it.

## Decisions I made (override if you disagree)
1. **Background LP = the only resting liquidity** (dropped MakerBots). If you'd
   rather the scripted crowd provide liquidity, reinstate a maker archetype in
   `agents.py` and `population.py`.
2. **One archetype = leveraged position-taker** with a `long_bias` knob. It's
   symmetric at `long_bias=0.5`; raise it for crowded longs.
3. **Funding removed.** Re-add as a step in `exchange.step` if you decide perp
   funding matters for your risk metrics.
