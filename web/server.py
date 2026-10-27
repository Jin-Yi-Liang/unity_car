#!/usr/bin/env python3
"""Local HTTP dashboard for the C++ dispatcher. Python standard library only."""
import argparse
import csv
import hashlib
import json
import socket
import sqlite3
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
TERMINAL = {'DELIVERED', 'REJECTED', 'INTERRUPTED'}


class Gateway:
    def __init__(self, backend_host, backend_port, database, catalog):
        self.backend = (backend_host, backend_port)
        self.lock = threading.RLock()
        self.submit_lock = threading.Lock()
        self.refresh_lock = threading.Lock()
        database.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(database, check_same_thread=False)
        self.db.execute('CREATE TABLE IF NOT EXISTS orders(session TEXT,id INTEGER,payload TEXT,PRIMARY KEY(session,id))')
        self.db.execute('CREATE TABLE IF NOT EXISTS requests(key TEXT PRIMARY KEY,digest TEXT,result TEXT)')
        self.db.commit()
        with catalog.open(encoding='utf-8', newline='') as stream:
            self.buildings = list(csv.DictReader(stream, delimiter='\t'))
        self.by_id = {b['stable_id']: b for b in self.buildings}
        self.current = {'session': None, 'cars': [], 'online': False, 'error': '等待后端连接'}
        self.last_ok = 0
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.poll, daemon=True)
        self.thread.start()

    def refresh(self):
        with self.refresh_lock:
            try:
                with socket.create_connection(self.backend, timeout=3) as sock:
                    sock.settimeout(3)
                    file = sock.makefile('r', encoding='utf-8')
                    sock.sendall(b'LOGIN,MONITOR\nSNAPSHOT\n')
                    if file.readline().strip() != 'WELCOME,MONITOR':
                        raise ValueError('后端不支持 MONITOR 协议，请重新编译并启动后端')
                    snapshot = json.loads(file.readline(8_000_000))
                with self.lock:
                    session = snapshot['session']
                    # A dispatcher restart cannot resume its former in-memory orders.
                    for old_session, order_id, raw in self.db.execute('SELECT session,id,payload FROM orders WHERE session<>?', (session,)).fetchall():
                        item = json.loads(raw)
                        if item['status'] not in TERMINAL:
                            item['status'] = 'INTERRUPTED'
                            self.db.execute('UPDATE orders SET payload=? WHERE session=? AND id=?', (json.dumps(item, ensure_ascii=False), old_session, order_id))
                    for item in snapshot['orders']:
                        item['session'] = session
                        item['key'] = f"{session}/{item['id']}"
                        for field, title in [('pickup_id', 'pickup_name'), ('delivery_id', 'delivery_name')]:
                            prefix = 'pickup' if field == 'pickup_id' else 'delivery'
                            coordinate = f"坐标 ({item[prefix + '_x']:.1f}, {item[prefix + '_y']:.1f})"
                            item[title] = self.by_id.get(item[field], {}).get('display_name', item[field] or coordinate)
                        self.db.execute('INSERT INTO orders VALUES(?,?,?) ON CONFLICT(session,id) DO UPDATE SET payload=excluded.payload', (session, item['id'], json.dumps(item, ensure_ascii=False)))
                    self.db.commit()
                    self.last_ok = time.time()
                    self.current = {'session': session, 'cars': snapshot['cars'], 'online': True, 'error': None}
            except (OSError, ValueError, KeyError) as error:
                with self.lock:
                    self.current['online'] = False
                    self.current['error'] = f'后端连接失败：{error}'
                    self.current['cars'] = []

    def poll(self):
        while not self.stop.is_set():
            self.refresh()
            self.stop.wait(.5)

    def state(self):
        with self.lock:
            orders = [json.loads(r[0]) for r in self.db.execute('SELECT payload FROM orders')]
            orders.sort(key=lambda item: (item['created_ms'], item['id']), reverse=True)
            return {**self.current, 'last_ok': self.last_ok, 'orders': orders, 'buildings': self.buildings}

    def submit(self, data):
        if not isinstance(data, dict):
            raise ValueError('请求必须是 JSON 对象')
        pickup, delivery = data.get('pickup_id'), data.get('delivery_id')
        for identifier in (pickup, delivery):
            building = self.by_id.get(identifier) if isinstance(identifier, str) else None
            if not building:
                raise ValueError(f'建筑不存在：{identifier}')
            if building['navigation_status'] != 'simulation_dock':
                raise ValueError(f'{identifier} 尚未配置停靠点，不能下单')
        if pickup == delivery:
            raise ValueError('取餐地点和送达地点必须不同')
        food, priority = data.get('food', '餐食'), data.get('priority', 0)
        if not isinstance(food, str) or not food.strip() or len(food) > 80 or any(c == ',' or ord(c) < 32 for c in food):
            raise ValueError('餐品名称需为 1～80 个字符，不能包含逗号或换行')
        if type(priority) is not int or priority not in (0, 1):
            raise ValueError('优先级必须为 0 或 1')
        request_key = data.get('request_key')
        if not isinstance(request_key, str) or not 8 <= len(request_key) <= 100:
            raise ValueError('缺少有效的 request_key')
        digest = hashlib.sha256(json.dumps([pickup, delivery, food.strip(), priority], ensure_ascii=False).encode()).hexdigest()
        with self.submit_lock:
            with self.lock:
                previous = self.db.execute('SELECT digest,result FROM requests WHERE key=?', (request_key,)).fetchone()
            if previous:
                if previous[0] != digest:
                    raise ValueError('同一个请求编号不能用于不同订单')
                return json.loads(previous[1])
            try:
                with socket.create_connection(self.backend, timeout=4) as sock:
                    sock.settimeout(4)
                    file = sock.makefile('r', encoding='utf-8')
                    sock.sendall(f'LOGIN,CLIENT\nORDER_BUILDINGS,{pickup},{delivery},{food.strip()},{priority}\n'.encode())
                    if file.readline().strip() != 'WELCOME,CLIENT':
                        raise OSError('后端握手失败')
                    line = file.readline().strip()
                    if not line.startswith('ORDER_ACCEPTED,'):
                        raise ValueError(f'后端拒绝订单：{line}')
                    order_id = int(line.split(',')[1])
            except OSError as error:
                raise ConnectionError(f'无法下单，请先启动 C++ 后端：{error}') from error
            self.refresh()
            with self.lock:
                result = {'id': order_id, 'session': self.current['session'], 'accepted': True}
                self.db.execute('INSERT INTO requests VALUES(?,?,?)', (request_key, digest, json.dumps(result)))
                self.db.commit()
            return result


def make_handler(gateway):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            if not self.path.startswith('/api/state'):
                super().log_message(format, *args)

        def reply(self, code, payload):
            raw = json.dumps(payload, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(raw)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            path = urlparse(self.path).path
            if path == '/api/state':
                return self.reply(200, gateway.state())
            if path == '/api/buildings':
                return self.reply(200, gateway.buildings)
            files = {'/': ('index.html', 'text/html'), '/app.js': ('app.js', 'text/javascript'), '/style.css': ('style.css', 'text/css')}
            if path not in files:
                return self.reply(404, {'error': 'Not found'})
            name, content_type = files[path]
            raw = (ROOT / 'web' / name).read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', content_type + '; charset=utf-8')
            self.send_header('Content-Length', str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_POST(self):
            if self.path != '/api/orders':
                return self.reply(404, {'error': 'Not found'})
            if self.headers.get('Content-Type', '').split(';')[0].strip() != 'application/json':
                return self.reply(415, {'error': '请使用 application/json'})
            origin = self.headers.get('Origin')
            if origin and urlparse(origin).netloc != self.headers.get('Host'):
                return self.reply(403, {'error': '不接受其他站点发起的下单请求'})
            try:
                length = int(self.headers.get('Content-Length', 0))
                if not 0 < length <= 16384:
                    raise ValueError('请求大小不正确')
                data = json.loads(self.rfile.read(length))
                return self.reply(201, gateway.submit(data))
            except ConnectionError as error:
                return self.reply(503, {'error': str(error)})
            except (ValueError, TypeError) as error:
                return self.reply(422, {'error': str(error)})
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8080)
    parser.add_argument('--backend-host', default='127.0.0.1')
    parser.add_argument('--backend-port', type=int, default=10000)
    parser.add_argument('--database', type=Path, default=ROOT / 'build/web-orders.sqlite3')
    parser.add_argument('--catalog', type=Path, default=ROOT / 'data/buildings.tsv')
    args = parser.parse_args()
    gateway = Gateway(args.backend_host, args.backend_port, args.database, args.catalog)
    server = ThreadingHTTPServer((args.host, args.port), make_handler(gateway))
    print(f'Web dashboard: http://{args.host}:{args.port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        gateway.stop.set()
        server.server_close()
        gateway.thread.join(timeout=5)

if __name__ == '__main__':
    main()
