"""Cost-optimal refuelling plan.

Classic "gas station problem", solved by the well-known O(n) greedy (provably optimal for a
single tank with a fixed range and per-station prices):

  at station i, look ahead within one tank's range for the next CHEAPER station j:
    * found    -> buy only enough to reach j, then drive to j
    * not found-> fill the tank completely (nothing ahead is cheaper), then drive to the next station

The destination is modelled as a free (price 0) station so the plan buys exactly what is needed to
arrive. The vehicle leaves with a full tank; the fuel it already has is valued at `start_price`.
"""
from dataclasses import dataclass

from .errors import PlanError


@dataclass
class Stop:
    node: int            # index into the candidate list (0-based, excludes start/end)
    mile: float          # miles along the route
    price: float         # $/gal
    gallons: float
    cost: float


@dataclass
class Plan:
    stops: list
    purchase_cost: float
    initial_tank_cost: float
    gallons_purchased: float
    gallons_from_initial_tank: float


def plan_fuel_stops(positions, prices, total_miles, start_price, max_range, mpg, start_range=None) -> Plan:
    """positions/prices: candidate stations sorted by route mile."""
    n = len(positions)
    if start_range is None:
        start_range = max_range

    # node 0 = start, 1..n = stations, n+1 = destination
    pos = [0.0] + [float(p) for p in positions] + [float(total_miles)]
    price = [float(start_price)] + [float(p) for p in prices] + [0.0]
    last = n + 1

    # Feasibility: every gap (incl. start->first and last->destination) must fit in one tank.
    # The first leg may only use the fuel the vehicle departs with.
    for k in range(last):
        limit = start_range if k == 0 else max_range
        gap = pos[k + 1] - pos[k]
        if gap > limit + 1e-9:
            where = "the start" if k == 0 else f"mile {pos[k]:.0f}"
            raise PlanError(
                f"No fuel station within {limit:.0f} miles of {where} along this route "
                f"(a {gap:.0f}-mile gap). Try a larger corridor_miles.",
                status=422,
                code="unreachable",
            )

    fuel = float(start_range)  # range remaining, in miles
    i = 0
    stops: list[Stop] = []
    bought_miles = 0.0
    purchase_cost = 0.0

    while i < last:
        # next strictly cheaper node within one full tank
        j, k = None, i + 1
        while k <= last and pos[k] - pos[i] <= max_range + 1e-9:
            if price[k] < price[i]:
                j = k
                break
            k += 1

        if j is not None:
            buy = max(0.0, (pos[j] - pos[i]) - fuel)
            nxt = j
        else:
            buy = max(0.0, max_range - fuel)
            nxt = i + 1

        if buy > 1e-9 and 1 <= i <= n:
            gallons = buy / mpg
            cost = gallons * price[i]
            stops.append(Stop(node=i - 1, mile=pos[i], price=price[i], gallons=gallons, cost=cost))
            purchase_cost += cost
            bought_miles += buy
        fuel += buy - (pos[nxt] - pos[i])
        i = nxt

    initial_miles = max(0.0, total_miles - bought_miles)  # initial tank is burned first
    return Plan(
        stops=stops,
        purchase_cost=purchase_cost,
        initial_tank_cost=initial_miles / mpg * start_price,
        gallons_purchased=bought_miles / mpg,
        gallons_from_initial_tank=initial_miles / mpg,
    )
