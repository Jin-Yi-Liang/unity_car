"""Integration checks; start the rebuilt C++ server and web/server.py first."""
import json
import socket
import time
import unittest
import urllib.error
import urllib.request
import uuid

URL = 'http://127.0.0.1:8080'


def state():
    return json.load(urllib.request.urlopen(URL + '/api/state', timeout=5))


def post(payload):
    request = urllib.request.Request(URL + '/api/orders', data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
    return json.load(urllib.request.urlopen(request, timeout=6))


def wait(predicate):
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        current = state()
        if predicate(current):
            return current
        time.sleep(.15)
    raise AssertionError('state did not converge')


class WebOrderIntegration(unittest.TestCase):
    def test_catalog_and_parallel_dispatch(self):
        current = state()
        self.assertTrue(current['online'])
        self.assertEqual(len(current['buildings']), 69)
        self.assertEqual(sum(b['navigation_status'] == 'simulation_dock' for b in current['buildings']), 69)
        self.assertEqual(len(current['cars']), 0, 'run protocol checks before the Unity player')
        for source, target in [('B9999', 'B0003'), ('B0003', 'B9999'), ('B0003', 'B0003')]:
            with self.assertRaises(urllib.error.HTTPError) as error:
                post({'pickup_id': source, 'delivery_id': target, 'food': 'test', 'priority': 0, 'request_key': str(uuid.uuid4())})
            self.assertEqual(error.exception.code, 422)
            error.exception.close()
        cars = []
        try:
            for _ in range(3):
                sock = socket.create_connection(('127.0.0.1', 10000), timeout=5)
                sock.settimeout(5)
                file = sock.makefile('r', encoding='utf-8')
                sock.sendall(b'LOGIN,UNITY\n')
                car_id = int(file.readline().strip().split(',')[2])
                cars.append((sock, file, car_id))
            payload = {'pickup_id': 'B0019', 'delivery_id': 'B0003', 'food': '中文并发测试', 'priority': 0, 'request_key': str(uuid.uuid4())}
            first = post(payload)
            self.assertEqual(first, post(payload), 'retry must not duplicate an order')
            ids = [first['id']]
            for _ in range(3):
                payload['request_key'] = str(uuid.uuid4())
                ids.append(post(payload)['id'])
            current = wait(lambda s: len([o for o in s['orders'] if o['id'] in ids and o['session'] == s['session']]) == 4)
            orders = [o for o in current['orders'] if o['id'] in ids and o['session'] == current['session']]
            self.assertEqual(sum(o['status'] == 'ASSIGNED' for o in orders), 3)
            self.assertEqual(sum(o['status'] == 'QUEUED' for o in orders), 1)
            self.assertEqual(len({o['car_id'] for o in orders if o['car_id']}), 3)
            tasks = []
            for sock, file, car_id in cars:
                fields = file.readline().strip().split(',')
                self.assertEqual(fields[0], 'TASK_BUILDINGS')
                self.assertEqual(fields[7:], ['B0019', 'B0003', 'SIMNODE_0037', 'SIMNODE_0038'])
                tasks.append((sock, file, car_id, int(fields[6])))
            sock, file, car_id, order_id = tasks[0]
            sock.sendall(f'REPORT_BUILDING,PICKUP,{car_id},{order_id},B9999\n'.encode())
            self.assertEqual(file.readline().strip(), 'ERROR,BUILDING_ID_MISMATCH')
            for sock, file, car_id, order_id in tasks:
                sock.sendall(f'REPORT_BUILDING,PICKUP,{car_id},{order_id},B0019\nREPORT_BUILDING,ARRIVED,{car_id},{order_id},B0003\n'.encode())
            # Completing one of the first three jobs must dispatch the queued fourth.
            current = wait(lambda s: any(o['id'] == ids[3] and o['status'] == 'ASSIGNED' for o in s['orders']))
            fourth = next(o for o in current['orders'] if o['session'] == current['session'] and o['id'] == ids[3])
            sock, file, car_id = next(c for c in cars if c[2] == fourth['car_id'])
            task = file.readline().strip().split(',')
            self.assertEqual(int(task[6]), ids[3])
            sock.sendall(f'REPORT_BUILDING,PICKUP,{car_id},{ids[3]},B0019\nREPORT_BUILDING,ARRIVED,{car_id},{ids[3]},B0003\n'.encode())
            current = wait(lambda s: sum(o['id'] in ids and o['session'] == s['session'] and o['status'] == 'DELIVERED' for o in s['orders']) == 4)
            self.assertEqual(sum(o['food'] == '中文并发测试' and o['id'] in ids for o in current['orders']), 4)
        finally:
            for sock, file, _ in cars:
                file.close()
                sock.close()
        wait(lambda s: len(s['cars']) == 0)

if __name__ == '__main__':
    unittest.main()
