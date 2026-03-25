#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import uuid
from urllib import request


def post_json(url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode('utf-8')
    req = request.Request(url, data=data, headers={'Content-Type': 'application/json'}, method='POST')
    with request.urlopen(req, timeout=60) as resp:
        body = resp.read().decode('utf-8')
        return json.loads(body)


def main() -> int:
    ap = argparse.ArgumentParser(description='Smoke test a remote MemOS server.')
    ap.add_argument('--base-url', required=True, help='e.g. http://<SERVER_IP>:8765')
    ap.add_argument('--user-id', default=None, help='logical user / cube id to use')
    args = ap.parse_args()

    base = args.base_url.rstrip('/')
    user_id = args.user_id or f'memos-smoke-{uuid.uuid4().hex[:8]}'
    fact = f'测试事实：user_id={user_id} 喜欢乌龙茶'

    add_res = post_json(
        f'{base}/product/add',
        {
            'user_id': user_id,
            'messages': [{'role': 'user', 'content': fact}],
            'async_mode': 'sync',
        },
    )
    if add_res.get('code') != 200:
        print(json.dumps({'step': 'add', 'ok': False, 'response': add_res}, ensure_ascii=False, indent=2))
        return 1

    search_res = post_json(
        f'{base}/product/search',
        {
            'user_id': user_id,
            'query': '喜欢什么茶',
        },
    )
    text_mem = (((search_res.get('data') or {}).get('text_mem') or [])[:1] or [{}])[0]
    memories = text_mem.get('memories') or []
    ok = search_res.get('code') == 200 and any('乌龙茶' in (m.get('memory') or '') for m in memories)

    print(
        json.dumps(
            {
                'ok': ok,
                'base_url': base,
                'user_id': user_id,
                'add_code': add_res.get('code'),
                'search_code': search_res.get('code'),
                'matched_memories': [m.get('memory') for m in memories[:3]],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if ok else 2


if __name__ == '__main__':
    raise SystemExit(main())
