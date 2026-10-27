"""Exercise every ordered building pair against the live C++ TCP dispatcher.

Run without real Unity cars or a Web gateway. The simulated car verifies the
complete task payload; actual driving is covered by verify_unity_fleet.py.
"""
import csv
import json
import math
import socket
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
with (ROOT / 'data/buildings.tsv').open() as stream:
    buildings = list(csv.DictReader(stream, delimiter='\t'))


def line(sock, file):
    # This contract test sends tiny consecutive replies. Acknowledge them
    # immediately instead of spending 40 ms on Linux delayed ACK per order.
    if hasattr(socket, 'TCP_QUICKACK'):
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_QUICKACK, 1)
    result = file.readline()
    if hasattr(socket, 'TCP_QUICKACK'):
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_QUICKACK, 1)
    return result


def login(role):
    sock = socket.create_connection(('127.0.0.1', 10000), timeout=5)
    sock.settimeout(5)
    file = sock.makefile('r', encoding='utf-8')
    sock.sendall(f'LOGIN,{role}\n'.encode())
    welcome = line(sock, file).strip()
    assert welcome.startswith(f'WELCOME,{role}'), welcome
    return sock, file, welcome


monitor, monitor_file, _ = login('MONITOR')
monitor.sendall(b'SNAPSHOT\n')
initial = json.loads(line(monitor, monitor_file))
assert not initial['cars'] and not initial['orders'], 'Use a fresh backend without real cars'
car, car_file, welcome = login('UNITY')
car_id = int(welcome.split(',')[2])
client, client_file, _ = login('CLIENT')
count, started = 0, time.monotonic()
try:
    for pickup in buildings:
        for delivery in buildings:
            source, target = pickup['stable_id'], delivery['stable_id']
            if source == target:
                continue
            client.sendall(f'ORDER_BUILDINGS,{source},{target},matrix,0\n'.encode())
            accepted = line(client, client_file).strip().split(',')
            assert accepted[0] == 'ORDER_ACCEPTED', accepted
            order_id = int(accepted[1])
            assert line(client, client_file).strip() == f'STATUS,{order_id},ASSIGNED'
            task = line(car, car_file).strip().split(',')
            assert task[0] == 'TASK_BUILDINGS' and len(task) == 11, task
            assert task[5:] == [str(car_id), str(order_id), source, target, pickup['dock_node_id'], delivery['dock_node_id']], task
            expected = [float(b[k]) for b in (pickup, delivery) for k in ('dock_x', 'dock_y')]
            assert all(math.isclose(float(a), b, abs_tol=.00001) for a, b in zip(task[1:5], expected)), task
            car.sendall(f'REPORT_BUILDING,PICKUP,{car_id},{order_id},{source}\nREPORT_BUILDING,ARRIVED,{car_id},{order_id},{target}\n'.encode())
            assert line(client, client_file).strip() == f'STATUS,{order_id},PICKUP,{source}'
            assert line(client, client_file).strip() == f'STATUS,{order_id},DELIVERED,{target}'
            count += 1
        print('validated', source, count, flush=True)
    monitor.sendall(b'SNAPSHOT\n')
    final = json.loads(line(monitor, monitor_file))
    assert len(final['orders']) == 69 * 68 == count
    assert all(o['status'] == 'DELIVERED' for o in final['orders'])
    result = dict(result='passed', ordered_pairs=count, buildings=len(buildings),
                  task_node_and_coordinate_checks=count, completed_report_sequences=count,
                  elapsed_seconds=round(time.monotonic() - started, 2),
                  scope='TCP contract with simulated reports, not real vehicle motion')
    path = ROOT / 'build/validation/all-docks/protocol-matrix.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result), flush=True)
finally:
    for sock, file in ((client, client_file), (car, car_file), (monitor, monitor_file)):
        file.close()
        sock.close()
