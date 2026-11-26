"""
The reference ("index"/"spot") price: what BTC is worth OUTSIDE this exchange.
The background LP keeps its quotes loosely tied to it.

Minimal version: synthetic geometric Brownian motion with occasional jumps, an
AR(1) volatility multiplier so high-vol minutes cluster into episodes (the regime
where cascades build), and an optional single scheduled shock. No historical
replay (removed for simplicity -- see README).

The clustering is a hand-set AR(1) on a latent state, turned into a vol
multiplier -- there is no fitting to a target ACF. It is centred so the long-run
average volatility is unchanged; it only changes the *timing* of volatility.

The path is deterministic for a given regime/seed and NEVER depends on who
trades, so two runs that differ only in the agent mix see the identical outside
world.
"""

import math
import random

from .config import Scenario, SimConfig


class IndexPriceProcess:
    def __init__(self, cfg: SimConfig, scenario: Scenario, rng: random.Random):
        self.cfg = cfg
        self.scenario = scenario
        self.rng = rng
        self.price = cfg.initial_price
        self.shock_step = scenario.shock_step(cfg.n_steps)
        self.vol_state = 0.0          # latent AR(1), stationary unit variance

    def _vol_multiplier(self) -> float:
        rho, vov = self.scenario.vol_cluster_rho, self.scenario.vol_cluster_vov
        if rho <= 0 or vov <= 0:
            return 1.0
        self.vol_state = rho * self.vol_state + math.sqrt(1 - rho ** 2) * self.rng.gauss(0.0, 1.0)
        # exp of the latent state, centred so E[multiplier] = 1 (level unchanged)
        return math.exp(vov * self.vol_state - 0.5 * vov ** 2)

    def next(self, step: int) -> float:
        s, dt = self.scenario, self.cfg.hours_per_step
        sigma = s.sigma_hourly * self._vol_multiplier()
        log_return = -0.5 * sigma ** 2 * dt + sigma * math.sqrt(dt) * self.rng.gauss(0.0, 1.0)
        if self.rng.random() < s.jump_rate_per_hour * dt:
            log_return += self.rng.gauss(s.jump_mean, s.jump_std)
        if self.shock_step is not None and step == self.shock_step:
            log_return += math.log(1.0 + s.shock_return)
        self.price *= math.exp(log_return)
        return self.price
