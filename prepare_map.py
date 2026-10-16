"""
Tải mạng lưới đường phố TP.HCM từ OpenStreetMap và lưu thành data/hcm_map.json.
Chỉ cần chạy MỘT LẦN (cần Internet). Sau đó ứng dụng chạy offline.

    pip install osmnx
    python prepare_map.py                       # mặc định: bán kính 3 km quanh chợ Bến Thành
    python prepare_map.py --dist 4000           # vùng rộng hơn
    python prepare_map.py --lat 10.7546 --lon 106.6631 --dist 2500   # đổi tâm (vd. khu Chợ Lớn)

Ghi chú: dùng "tâm + bán kính" thay vì tên quận vì sau đợt sắp xếp đơn vị hành chính
năm 2025, cấp quận đã bỏ nên truy vấn theo tên "Quận 1, Quận 5..." có thể không còn
khớp ranh giới trên OpenStreetMap.

Định dạng file JSON:
    nodes: [[lat, lon], ...]                       (chỉ số trong mảng = id giao lộ)
    edges: [[u, v, độ_dài_m, tên_đường, cấp_đường, hình_học | null], ...]
"""

import argparse
import json
import math
import os
import sys
import time
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
    """Chuyển đồ thị OSMnx (MultiDiGraph) thành dict gọn nhẹ để lưu JSON."""
    import networkx as nx

    # Chỉ giữ thành phần liên thông mạnh lớn nhất: từ bất kỳ giao lộ nào cũng đi được
    # đến mọi giao lộ khác (tránh chọn trúng điểm "kẹt" vì đường một chiều).
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
        # Độ dài không bao giờ nhỏ hơn đường chim bay -> heuristic Haversine luôn chấp nhận được
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


# Máy chủ Overpass chính và các máy chủ dự phòng (dùng lần lượt khi máy chủ trước bị quá tải)
OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api",
    "https://overpass.kumi.systems/api",
    "https://overpass.private.coffee/api",
    "https://maps.mail.ru/osm/tools/overpass/api",
]


def set_endpoint(ox, url):
    """Đặt máy chủ Overpass cho OSMnx (tên thiết lập khác nhau giữa bản 1.x và 2.x)."""
    if hasattr(ox.settings, "overpass_url"):          # OSMnx 2.x
        ox.settings.overpass_url = url
    else:                                             # OSMnx 1.x
        ox.settings.overpass_endpoint = url


def download_with_retry(ox, center, dist, endpoints, retries):
    """Thử lần lượt từng máy chủ, mỗi máy chủ thử lại vài lần, thời gian chờ tăng gấp đôi."""
    ox.settings.requests_timeout = 300
    for i, url in enumerate(endpoints):
        if i > 0:
            print("     Chuyển sang máy chủ dự phòng.")
        set_endpoint(ox, url)
        wait = 10
        for attempt in range(1, retries + 1):
            print(f"  -> Máy chủ {url} (lần {attempt}/{retries})")
            try:
                return ox.graph_from_point(center, dist=dist, network_type="drive", simplify=True)
            except Exception as ex:            # quá tải (502/504), hết thời gian, mất mạng...
                reason = str(ex).strip().splitlines()[0][:120] if str(ex).strip() else type(ex).__name__
                print(f"     Lỗi: {reason}")
                if attempt < retries:
                    print(f"     Chờ {wait} giây rồi thử lại...")
                    time.sleep(wait)
                    wait *= 2
    return None


def main():
    ap = argparse.ArgumentParser(description="Tải dữ liệu đường phố TP.HCM từ OpenStreetMap")
    ap.add_argument("--lat", type=float, default=10.7725, help="vĩ độ tâm (mặc định: chợ Bến Thành)")
    ap.add_argument("--lon", type=float, default=106.6980, help="kinh độ tâm")
    ap.add_argument("--dist", type=int, default=3000, help="bán kính (mét), mặc định 3000")
    ap.add_argument("--out", default=os.path.join("data", "hcm_map.json"))
    ap.add_argument("--endpoint", help="chỉ dùng một máy chủ Overpass cụ thể (URL kết thúc bằng /api)")
    ap.add_argument("--retries", type=int, default=3, help="số lần thử mỗi máy chủ (mặc định 3)")
    args = ap.parse_args()

    try:
        import osmnx as ox
    except ImportError:
        print("Chưa cài OSMnx. Hãy chạy:  pip install osmnx")
        sys.exit(1)

    print(f"Đang tải mạng lưới đường quanh ({args.lat}, {args.lon}), bán kính {args.dist} m ...")
    endpoints = [args.endpoint] if args.endpoint else OVERPASS_ENDPOINTS
    G = download_with_retry(ox, (args.lat, args.lon), args.dist, endpoints, args.retries)
    if G is None:
        print("\nTất cả máy chủ Overpass đều đang bận hoặc không kết nối được.")
        print("Hãy thử lại sau vài phút, hoặc kiểm tra kết nối Internet / tường lửa / VPN.")
        sys.exit(1)
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
