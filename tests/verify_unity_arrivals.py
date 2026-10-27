"""Check actual Tuanjie stop coordinates for every browser-submitted order."""
import csv
import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
submitted = json.loads((ROOT / 'build/validation/browser-submit.json').read_text())['submitted']
with (ROOT / 'data/buildings.tsv').open() as stream:
    buildings = {b['stable_id']: b for b in csv.DictReader(stream, delimiter='\t')}
log = (ROOT / 'build/validation/all-docks/player.log').read_text()
stops = {}
for phase, order_id, building_id, position in re.findall(r'\[car\] (PICKUP|ARRIVED) order=(\d+) building=(B\d{4}) pos=\(([^)]+)\)', log):
    x, _, z = map(float, position.split(','))
    stops[(int(order_id), phase)] = (building_id, (-x, -z))
errors = []
for order in submitted:
    for phase, key in [('PICKUP', 'from'), ('ARRIVED', 'to')]:
        building_id, point = stops[(order['id'], phase)]
        assert building_id == order[key], (order, phase, building_id)
        dock = buildings[building_id]
        error = math.dist(point, (float(dock['dock_x']), float(dock['dock_y'])))
        assert error < .3, (order, phase, error)
        errors.append(error)
assert len({o['from'] for o in submitted}) == len({o['to'] for o in submitted}) == 69
assert len(errors) == 138
result = dict(result='passed', actual_pickups=69, actual_deliveries=69,
              max_stop_error_m=round(max(errors), 4),
              tolerance_m=.3, position_log_rounding_m=.01)
(ROOT / 'build/validation/all-docks/arrival-coordinates.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result))
