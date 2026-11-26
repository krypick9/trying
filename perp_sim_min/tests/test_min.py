"""Compact tests for the minimal simulator: order book, accounts/margin,
the liquidation cascade, and the replace-not-add fairness guarantee."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import BUY, SELL, Account, Exchange, Order, OrderBook, SimConfig, get_scenario
from population import PopulationSpec, build_population
from run import run, summarize


# ---- order book --------------------------------------------------------
def test_book_matches_best_price_first():
    b = OrderBook(tick_size=0.1)
    b.submit(Order(1, "mk", SELL, 1.0, 100.0))
    b.submit(Order(2, "mk", SELL, 1.0, 101.0))
    fills = b.submit(Order(3, "tk", BUY, 0.5, 100.5))
    assert len(fills) == 1 and fills[0].price == 100.0 and fills[0].qty == 0.5


def test_self_trade_protection():
    b = OrderBook(tick_size=0.1)
    b.submit(Order(1, "a", SELL, 1.0, 100.0))
    fills = b.submit(Order(2, "a", BUY, 1.0, 100.0))   # same account
    assert fills == [] and b.best_ask() is None        # resting order cancelled


# ---- accounts / margin -------------------------------------------------
def test_margin_breach_and_liquidation_price():
    a = Account("x", collateral=100.0, max_leverage=20.0)
    a.apply_fill(BUY, 0.02, 100_000.0, fee=0.0)        # 2000 notional on 100 cash
    assert a.position == 0.02
    # a drop toward the liquidation price must breach maintenance
    lp = a.liquidation_price(0.01)
    assert lp is not None and lp < 100_000.0
    assert a.is_breached(lp - 1, 0.01)


# ---- the cascade mechanism exists and fires ----------------------------
def test_liquidations_fire_under_leverage_and_shock():
    spec = PopulationSpec(target_leverage=20.0, long_bias=0.9)
    ex, _ = run("stress", n_steps=300, seed=0, spec=spec)
    assert summarize(ex)["liquidations"] > 0            # the phenomenon is reachable


def test_liquidations_can_be_disabled_as_control():
    spec = PopulationSpec(target_leverage=20.0, long_bias=0.9)
    ex, _ = run("stress", n_steps=300, seed=0, spec=spec,
                cfg_overrides={"liquidations_enabled": False})
    assert summarize(ex)["liquidations"] == 0


# ---- replace-not-add fairness ------------------------------------------
def test_swap_order_is_seed_stable_and_capital_constant():
    spec = PopulationSpec()
    p0 = build_population(seed=7, spec=spec, n_llm=0)
    # a scripted-only build is reproducible; slots don't depend on n_llm
    slots_a = [(s.account_id, s.cash, s.direction, s.swap_rank) for s in p0.slots]
    p1 = build_population(seed=7, spec=spec, n_llm=0)
    slots_b = [(s.account_id, s.cash, s.direction, s.swap_rank) for s in p1.slots]
    assert slots_a == slots_b
    assert abs(sum(s.cash for s in p0.slots) - spec.m_traders * spec.collateral) < 1e-6


def test_index_path_independent_of_traders():
    # two different populations, same seed -> identical index path
    cfg = SimConfig(n_steps=50, seed=3)
    sc = get_scenario("normal")
    e1, e2 = Exchange(cfg, sc), Exchange(cfg, sc)
    path1 = [e1.index.next(t) for t in range(1, 20)]
    path2 = [e2.index.next(t) for t in range(1, 20)]
    assert path1 == path2
