import itertools
import random

from django.test import SimpleTestCase

from routing.errors import PlanError
from routing.optimizer import plan_fuel_stops

RANGE, MPG = 500.0, 10.0


def brute_force_cost(positions, prices, total, start_price):
    """Exact optimum by trying every subset of stations to stop at, filling just enough at each
    (the buy-just-enough-to-reach-next-stop plan is optimal for a fixed stop set only if we
    also consider cheaper-ahead logic, so instead solve the LP-ish problem via DP over fuel levels in 1-mile steps)."""
    # DP over (station index, miles of fuel) with 1-mile resolution. Costs in $/mile of fuel.
    step = 1
    nodes = [(0.0, start_price)] + list(zip(positions, prices)) + [(total, 0.0)]
    INF = float("inf")
    cap = int(RANGE)
    # best[f] = min cost to be at current node holding f miles of fuel (initial tank cost is accounted separately)
    best = {cap: 0.0}
    for k in range(len(nodes) - 1):
        pos, price = nodes[k]
        gap = nodes[k + 1][0] - pos
        nxt = {}
        for f, c in best.items():
            # optionally top up to any level (no purchase at the start node)
            levels = [f] if k == 0 else range(f, cap + 1)
            for g in levels:
                cost = c + (g - f) * price / MPG
                rem = g - gap
                if rem < -1e-6:
                    continue
                r = int(rem) if rem == int(rem) else int(rem)  # floor keeps it conservative
                if rem - r > 1e-9:
                    r = int(rem)
                if cost < nxt.get(r, INF):
                    nxt[r] = cost
        best = nxt
    return min(best.values()) if best else INF


class OptimizerTests(SimpleTestCase):
    def test_short_trip_needs_no_stops(self):
        plan = plan_fuel_stops([100, 200], [3.0, 2.0], 300, 3.5, RANGE, MPG)
        self.assertEqual(plan.stops, [])
        self.assertAlmostEqual(plan.initial_tank_cost, 300 / MPG * 3.5)

    def test_buys_at_cheapest_station_and_only_what_is_needed(self):
        # 900-mile trip, cheap station at mile 400. Should buy there, enough to finish.
        plan = plan_fuel_stops([200, 400, 700], [4.0, 3.0, 5.0], 900, 4.0, RANGE, MPG)
        self.assertEqual([round(s.mile) for s in plan.stops], [400])
        self.assertAlmostEqual(plan.gallons_purchased, (900 - 500) / MPG)  # 40 gal
        self.assertAlmostEqual(plan.gallons_from_initial_tank, 50.0)

    def test_multiple_stops_on_long_trip(self):
        positions = [300, 600, 900, 1200, 1500, 1800]
        prices = [3.5, 3.2, 3.9, 3.1, 3.8, 3.3]
        plan = plan_fuel_stops(positions, prices, 2200, 3.5, RANGE, MPG)
        self.assertGreaterEqual(len(plan.stops), 3)
        total_gal = plan.gallons_purchased + plan.gallons_from_initial_tank
        self.assertAlmostEqual(total_gal, 2200 / MPG)
        # never carries more than a tank: gallons bought at any stop <= 50
        self.assertTrue(all(s.gallons <= 50 + 1e-9 for s in plan.stops))

    def test_unreachable_gap_raises(self):
        with self.assertRaises(PlanError) as ctx:
            plan_fuel_stops([100], [3.0], 900, 3.0, RANGE, MPG)  # 800-mile gap to destination
        self.assertEqual(ctx.exception.status, 422)

    def test_matches_brute_force_on_random_instances(self):
        rng = random.Random(7)
        for _ in range(60):
            total = rng.randint(600, 1800)
            n = rng.randint(3, 8)
            positions = sorted(rng.sample(range(20, total - 20), n))
            prices = [round(rng.uniform(2.8, 4.5), 3) for _ in range(n)]
            try:
                plan = plan_fuel_stops(positions, prices, total, 3.5, RANGE, MPG)
            except PlanError:
                continue
            greedy = plan.purchase_cost + plan.initial_tank_cost
            # brute force: purchase cost only + initial tank valued at same start price for consumed miles
            opt = brute_force_cost(positions, prices, total, 3.5)
            # The DP's initial-tank cost is implicit (free); add initial miles used at start price for parity.
            opt_total = opt + plan.gallons_from_initial_tank * 3.5
            # DP (1-mile resolution) can only match or be within rounding of the greedy optimum
            self.assertLessEqual(greedy, opt_total + 0.5, msg=(positions, prices, total))
