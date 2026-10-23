"""Pre-process the raw OPIS fuel price CSV into routing/data/stations.csv.

* keeps US stations only (the file also contains Canadian provinces)
* collapses repeated truckstop IDs to one row, keeping the LOWEST listed price
* geocodes each station to its city centroid using the offline gazetteer
  (the CSV has no coordinates, and doing this once means requests never geocode)
"""
import csv
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from routing.gazetteer import lookup_city

US_STATES = set(
    "AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC".split()
)


class Command(BaseCommand):
    help = "Geocode and de-duplicate the raw fuel price CSV into routing/data/stations.csv"

    def add_arguments(self, parser):
        parser.add_argument("--source", default=str(Path(settings.BASE_DIR) / "data" / "fuel-prices-for-be-assessment.csv"))
        parser.add_argument("--out", default=str(Path(settings.BASE_DIR) / "routing" / "data" / "stations.csv"))

    def handle(self, *args, **opts):
        best: dict[str, dict] = {}
        skipped_non_us = 0
        with open(opts["source"], newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                state = row["State"].strip().upper()
                if state not in US_STATES:
                    skipped_non_us += 1
                    continue
                sid = row["OPIS Truckstop ID"].strip()
                price = float(row["Retail Price"])
                cur = best.get(sid)
                if cur is None or price < cur["price"]:
                    best[sid] = {
                        "id": sid,
                        "name": row["Truckstop Name"].strip(),
                        "address": row["Address"].strip(),
                        "city": row["City"].strip(),
                        "state": state,
                        "price": price,
                    }

        rows, unmatched = [], []
        for st in best.values():
            hit = lookup_city(st["city"], st["state"])
            if hit is None:
                unmatched.append(f'{st["city"]}, {st["state"]}')
                continue
            st["lat"], st["lon"] = round(hit[0], 5), round(hit[1], 5)
            rows.append(st)

        rows.sort(key=lambda r: int(r["id"]))
        with open(opts["out"], "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=["id", "name", "address", "city", "state", "price", "lat", "lon"])
            w.writeheader()
            w.writerows(rows)

        self.stdout.write(self.style.SUCCESS(
            f"wrote {len(rows)} stations to {opts['out']} "
            f"(skipped {skipped_non_us} non-US rows, {len(unmatched)} US stations could not be geocoded)"
        ))
        if unmatched:
            self.stdout.write("unmatched: " + "; ".join(sorted(set(unmatched))[:40]))
