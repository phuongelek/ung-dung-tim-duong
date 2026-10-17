"""
Tải đường phố từ OpenStreetMap, lưu vào data/hcm_map.json (chạy một lần, cần mạng).

    python prepare_map.py
    python prepare_map.py --lat 10.7546 --lon 106.6631 --dist 2500
"""

import argparse
import json
import math
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.problems import haversine  # noqa: E402

MAJOR = {"motorway", "trunk", "primary", "motorway_link", "trunk_link", "primary_link"}
MIDDLE = {"secondary", "tertiary", "secondary_link", "tertiary_link"}


def road_class(highway):
    if isinstance(highway, list):
        return max(road_class(h) for h in highway)
    if highway in MAJOR:
        return 3
    if highway in MIDDLE:
        return 2
    return 1


def first(value):
    if isinstance(value, list):
        return value[0] if value else ""
    return value or ""


def convert_graph(G, meta):
    import networkx as nx

    # giữ thành phần liên thông mạnh lớn nhất để cặp điểm nào cũng có đường đi
    largest = max(nx.strongly_connected_components(G), key=len)
    G = G.subgraph(largest).copy()

    index = {}
    nodes = []
    for n, d in G.nodes(data=True):
        index[n] = len(nodes)
        nodes.append([round(d["y"], 7), round(d["x"], 7)])

    best = {}
    for u, v, d in G.edges(data=True):
        iu, iv = index[u], index[v]
        lat1, lon1 = nodes[iu]
        lat2, lon2 = nodes[iv]
        # độ dài không nhỏ hơn đường chim bay, để heuristic luôn chấp nhận được
        length = max(float(d.get("length", 0.0)), haversine(lat1, lon1, lat2, lon2))
        length = math.ceil(length * 100) / 100
        geom = d.get("geometry")
        coords = [[round(y, 7), round(x, 7)] for x, y in geom.coords] if geom is not None else None
        edge = [iu, iv, length, first(d.get("name")), road_class(d.get("highway")), coords]
        key = (iu, iv)
        if key not in best or length < best[key][2]:
            best[key] = edge

    meta = dict(meta, nodes=len(nodes), edges=len(best))
    return {"meta": meta, "nodes": nodes, "edges": list(best.values())}


def main():
    ap = argparse.ArgumentParser(description="Tải dữ liệu đường phố TP.HCM từ OpenStreetMap")
    ap.add_argument("--lat", type=float, default=10.7725, help="vĩ độ tâm (mặc định: chợ Bến Thành)")
    ap.add_argument("--lon", type=float, default=106.6980, help="kinh độ tâm")
    ap.add_argument("--dist", type=int, default=3000, help="bán kính (mét), mặc định 3000")
    ap.add_argument("--out", default=os.path.join("data", "hcm_map.json"))
    args = ap.parse_args()

    try:
        import osmnx as ox
    except ImportError:
        print("Chưa cài OSMnx. Hãy chạy:  pip install osmnx")
        sys.exit(1)

    print(f"Đang tải mạng lưới đường quanh ({args.lat}, {args.lon}), bán kính {args.dist} m ...")
    G = ox.graph_from_point((args.lat, args.lon), dist=args.dist,
                            network_type="drive", simplify=True)
    print(f"  Đã tải: {G.number_of_nodes()} giao lộ, {G.number_of_edges()} đoạn đường")

    data = convert_graph(G, {"center": [args.lat, args.lon], "dist": args.dist,
                             "source": "OpenStreetMap contributors (ODbL)",
                             "created": date.today().isoformat()})

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), args.out) \
        if not os.path.isabs(args.out) else args.out
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    size_mb = os.path.getsize(out) / 1e6
    print(f"  Sau khi lọc: {data['meta']['nodes']} giao lộ, {data['meta']['edges']} đoạn đường")
    print(f"Đã lưu {out} ({size_mb:.1f} MB). Giờ hãy chạy: python main.py")


if __name__ == "__main__":
    main()
