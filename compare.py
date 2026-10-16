"""
So sánh A* với BFS, DFS, UCS, Greedy trên bản đồ TP.HCM để lấy số liệu cho BÁO CÁO.
(Ứng dụng chính chỉ dùng A*; file này chỉ phục vụ phần so sánh trong báo cáo.)

    python compare.py                 # 30 cặp điểm cho mỗi nhóm khoảng cách
    python compare.py --trials 100 --seed 7

Cặp điểm đầu/đích được chọn ngẫu nhiên và chia theo khoảng cách chim bay:
    gần (0.5 - 1.5 km), trung bình (1.5 - 3 km), xa (trên 3 km)

Kết quả in ra màn hình và lưu vào results/compare_results.csv
"""

import argparse
import csv
import os
import random
import statistics
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from core.baselines import ALGORITHMS  # noqa: E402
from core.problems import MapProblem  # noqa: E402

BANDS = [("Gần (0.5 - 1.5 km)", 500, 1500),
         ("Trung bình (1.5 - 3 km)", 1500, 3000),
         ("Xa (trên 3 km)", 3000, float("inf"))]


def sample_pairs(prob, n, lo, hi, rng, max_tries=200000):
    nodes = list(prob.nodes)
    pairs = []
    for _ in range(max_tries):
        if len(pairs) >= n:
            break
        s, g = rng.choice(nodes), rng.choice(nodes)
        if lo <= prob.heuristic(s, g) < hi:
            pairs.append((s, g))
    return pairs


def run_band(name, prob, pairs):
    rows = {a: {"ratio": [], "expanded": [], "time": [], "found": 0, "optimal": 0}
            for a in ALGORITHMS}
    for s, g in pairs:
        results = {a: f(prob, s, g) for a, f in ALGORITHMS.items()}
        best = results["UCS"].cost                 # UCS luôn tối ưu -> làm chuẩn
        for a, res in results.items():
            r = rows[a]
            r["expanded"].append(res.expanded)
            r["time"].append(res.time_ms)
            if res.found:
                r["found"] += 1
                r["ratio"].append(res.cost / best if best > 0 else 1.0)
                if abs(res.cost - best) < 1e-6:
                    r["optimal"] += 1

    total = len(pairs)
    print(f"\n=== {name}: {total} cặp điểm ===")
    header = (f"{'Thuật toán':<11}{'Tìm thấy':>10}{'Tối ưu':>10}{'Q.đường / tối ưu':>19}"
              f"{'Nút mở rộng TB':>17}{'Thời gian TB (ms)':>19}")
    print(header)
    print("-" * len(header))
    out = []
    for a, r in rows.items():
        ratio = statistics.mean(r["ratio"]) if r["ratio"] else float("nan")
        exp = statistics.mean(r["expanded"])
        t = statistics.mean(r["time"])
        print(f"{a:<11}{r['found']:>6}/{total:<3}{r['optimal']:>6}/{total:<3}"
              f"{ratio:>19.3f}{exp:>17,.0f}{t:>19.3f}")
        out.append([name, a, total, r["found"], r["optimal"], round(ratio, 4),
                    round(exp, 1), round(t, 4)])
    return out


def main():
    ap = argparse.ArgumentParser(description="So sánh A* với BFS, DFS, UCS, Greedy trên bản đồ")
    ap.add_argument("--trials", type=int, default=30, help="số cặp điểm cho mỗi nhóm khoảng cách")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    map_file = os.path.join(ROOT, "data", "hcm_map.json")
    if not os.path.exists(map_file):
        print("Chưa có data/hcm_map.json. Hãy chạy trước:  python prepare_map.py")
        sys.exit(1)
    prob = MapProblem.load(map_file)
    print(f"Bản đồ: {len(prob.nodes)} giao lộ, {len(prob.edge_info)} đoạn đường")

    rng = random.Random(args.seed)
    table = []
    for name, lo, hi in BANDS:
        pairs = sample_pairs(prob, args.trials, lo, hi, rng)
        if not pairs:
            print(f"\n(Bỏ qua nhóm '{name}': vùng bản đồ quá nhỏ, không có cặp điểm phù hợp)")
            continue
        table += run_band(name, prob, pairs)

    os.makedirs(os.path.join(ROOT, "results"), exist_ok=True)
    path = os.path.join(ROOT, "results", "compare_results.csv")
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["Nhóm khoảng cách", "Thuật toán", "Số cặp điểm", "Tìm thấy", "Tối ưu",
                    "Quãng đường / tối ưu (TB)", "Nút mở rộng (TB)", "Thời gian (ms, TB)"])
        w.writerows(table)
    print(f"\nĐã lưu bảng số liệu: {path}")


if __name__ == "__main__":
    main()
