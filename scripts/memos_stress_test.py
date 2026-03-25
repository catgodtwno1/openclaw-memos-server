#!/usr/bin/env python3
"""MemOS 壓測腳本 — 測試 /product/add 在持續寫入下的延遲穩定性

用法：
  python3 memos_stress_test.py                           # 預設 500 輪，本機
  python3 memos_stress_test.py --rounds 100              # 100 輪
  python3 memos_stress_test.py --url http://10.10.10.66:8765  # NAS
  python3 memos_stress_test.py --delay 0.5               # 每輪間隔 500ms
  python3 memos_stress_test.py --cleanup                 # 跑完後清理 Neo4j 測試數據

目的：
  驗證 core.py O(N) patch 是否生效 — patch 前 500 輪會從 90ms 升到 15s+，
  patch 後應維持穩定（無衰退 degradation ≤ 1.5x）。
"""

import requests, time, statistics, argparse, subprocess, sys

def main():
    parser = argparse.ArgumentParser(description="MemOS 壓測")
    parser.add_argument("--url", default="http://127.0.0.1:8765",
                        help="MemOS base URL (預設 http://127.0.0.1:8765)")
    parser.add_argument("--rounds", type=int, default=500,
                        help="測試輪次 (預設 500)")
    parser.add_argument("--delay", type=float, default=0.2,
                        help="每輪間隔秒數 (預設 0.2)")
    parser.add_argument("--user-id", default="stress-test",
                        help="測試用 user_id (預設 stress-test)")
    parser.add_argument("--cleanup", action="store_true",
                        help="測試後清理 Neo4j 測試數據")
    parser.add_argument("--neo4j-host", default=None,
                        help="Neo4j SSH host (清理用，預設從 URL 推斷)")
    parser.add_argument("--neo4j-password", default="openclaw2026",
                        help="Neo4j 密碼 (預設 openclaw2026)")
    args = parser.parse_args()

    url = f"{args.url.rstrip('/')}/product/add"
    marker = f"stress-test-{int(time.time())}"
    results = []
    errors = 0

    print(f"MemOS 壓測: {args.rounds} 輪 @ {args.url} (delay={args.delay}s)")
    print(f"Marker: {marker}")
    print()

    for i in range(args.rounds):
        t0 = time.time()
        try:
            r = requests.post(url, json={
                "user_id": args.user_id,
                "memory_content": f"{marker} #{i}"
            }, timeout=60)
            ms = (time.time() - t0) * 1000
            if r.status_code == 200:
                results.append(ms)
            else:
                errors += 1
                print(f"  #{i}: HTTP {r.status_code} ({ms:.0f}ms)")
        except Exception as e:
            errors += 1
            ms = (time.time() - t0) * 1000
            print(f"  #{i}: ERROR {e} ({ms:.0f}ms)")

        if i % 100 == 0:
            print(f"  Progress: {i}/{args.rounds} ({len(results)} ok, {errors} err)")

        time.sleep(args.delay)

    # Results
    print()
    print("=" * 50)
    print(f"  MemOS 壓測結果")
    print(f"  {len(results)} success / {errors} errors / {args.rounds} total")
    print("=" * 50)

    if results:
        s = sorted(results)
        n = len(s)
        print(f"  Avg:    {statistics.mean(results):.0f}ms")
        print(f"  Min:    {min(results):.0f}ms")
        print(f"  Max:    {max(results):.0f}ms")
        print(f"  Median: {statistics.median(results):.0f}ms")
        print(f"  P95:    {s[int(n * 0.95)]:.0f}ms")
        print(f"  P99:    {s[int(n * 0.99)]:.0f}ms")
        print()

        # Degradation check
        bucket = min(50, n // 4)
        if bucket > 0:
            first = statistics.mean(results[:bucket])
            last = statistics.mean(results[-bucket:])
            ratio = last / first if first > 0 else 0
            print(f"  First {bucket} avg: {first:.0f}ms")
            print(f"  Last {bucket} avg:  {last:.0f}ms")
            print(f"  Degradation:  {ratio:.1f}x", end="")
            if ratio <= 1.5:
                print("  ✅ 無衰退")
            elif ratio <= 3.0:
                print("  ⚠️ 輕微衰退")
            else:
                print("  ❌ 嚴重衰退 — patch 可能未生效")
    print()

    # Cleanup
    if args.cleanup:
        print("清理測試數據...")
        host = args.neo4j_host
        if not host:
            # Infer from URL
            from urllib.parse import urlparse
            parsed = urlparse(args.url)
            host = parsed.hostname
            if host in ("127.0.0.1", "localhost"):
                # Local Docker
                cmd = f'docker exec memos-neo4j cypher-shell -u neo4j -p {args.neo4j_password} "MATCH (n:Memory) WHERE n.memory CONTAINS \'{marker}\' DETACH DELETE n RETURN count(n) as deleted;"'
            else:
                # Remote (NAS)
                docker_path = "/share/CACHEDEV1_DATA/.qpkg/container-station/bin/docker"
                cmd = f'ssh openclaw@{host} "{docker_path} exec oc-neo4j cypher-shell -u neo4j -p {args.neo4j_password} \\"MATCH (n:Memory) WHERE n.memory CONTAINS \'{marker}\' DETACH DELETE n RETURN count(n) as deleted;\\""'
        try:
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
            print(f"  {r.stdout.strip()}")
        except Exception as e:
            print(f"  清理失敗: {e}")

    # Pass/fail verdict
    if errors == 0 and results:
        s = sorted(results)
        bucket = min(50, len(s) // 4)
        ratio = statistics.mean(results[-bucket:]) / statistics.mean(results[:bucket]) if bucket > 0 else 1
        if ratio <= 1.5:
            print("🎉 PASS — 零錯誤、無衰退")
            sys.exit(0)
        else:
            print(f"⚠️ WARN — 零錯誤但衰退 {ratio:.1f}x")
            sys.exit(1)
    elif errors > 0:
        print(f"❌ FAIL — {errors} errors")
        sys.exit(1)

if __name__ == "__main__":
    main()
