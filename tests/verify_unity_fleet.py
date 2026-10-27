"""Observe real Unity fleet completing the browser-submitted endpoint matrix."""
import json
import argparse
import time
import urllib.request
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--timescale', type=int, default=8)
parser.add_argument('--timeout', type=int, default=1200)
parser.add_argument('--render-mode', choices=['headless', 'graphical'], default='headless')
args = parser.parse_args()
submitted = json.loads(Path('build/validation/browser-submit.json').read_text())['submitted']
expected = {item['key'] for item in submitted}
previous = {}
traces = {}
max_active = max_moving = 0
started = time.monotonic()
while time.monotonic() - started < args.timeout:
    state = json.load(urllib.request.urlopen('http://127.0.0.1:8080/api/state', timeout=5))
    ours = [item for item in state['orders'] if item['key'] in expected]
    max_active = max(max_active, sum(c['order_id'] != 0 for c in state['cars']))
    moving = 0
    for car in state['cars']:
        key = str(car['id'])
        point = (car['x'], car['y'])
        if car['has_position']:
            if key in previous and abs(point[0] - previous[key][0]) + abs(point[1] - previous[key][1]) > .2 and car['order_id']:
                moving += 1
            if key not in previous or point != previous[key]:
                traces.setdefault(key, []).append({'x': point[0], 'y': point[1], 'order_id': car['order_id']})
            previous[key] = point
    max_moving = max(max_moving, moving)
    failed = [o for o in ours if o['status'] in ('REJECTED', 'INTERRUPTED')]
    if failed:
        raise AssertionError(f'Unity rejected orders: {failed}')
    if len(ours) == len(expected) and all(o['status'] == 'DELIVERED' for o in ours):
        assert max_active >= 3, max_active
        assert max_moving >= 2, max_moving
        assert len([v for v in traces.values() if len(v) > 3]) >= 3
        assert len({o['pickup_id'] for o in ours}) == 69
        assert len({o['delivery_id'] for o in ours}) == 69
        result = {'result': 'passed', 'runtime': 'real Tuanjie Linux player', 'render_mode': args.render_mode, 'timescale': args.timescale, 'combinations': len(ours), 'pickup_buildings': 69, 'delivery_buildings': 69, 'max_active_cars': max_active, 'max_simultaneously_moving_cars': max_moving, 'elapsed_seconds': round(time.monotonic()-started, 2), 'orders': ours, 'trajectories': traces}
        Path('build/validation/unity-fleet-result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
        print(json.dumps({k: v for k, v in result.items() if k not in ('orders', 'trajectories')}), flush=True)
        break
    print('progress', sum(o['status'] == 'DELIVERED' for o in ours), '/', len(expected), '; active', sum(c['order_id'] != 0 for c in state['cars']), flush=True)
    time.sleep(2)
else:
    Path('build/validation/unity-fleet-timeout.json').write_text(json.dumps({'state': state, 'trajectories': traces}, ensure_ascii=False, indent=2))
    raise TimeoutError('Unity did not complete all browser orders')
