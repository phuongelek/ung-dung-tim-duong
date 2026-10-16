"""
Bài toán tìm đường trên bản đồ thật, dạng tìm kiếm trong không gian trạng thái:

MapProblem: mạng lưới đường thật lấy từ OpenStreetMap.
   - Trạng thái: một giao lộ (đỉnh của đồ thị có hướng).
   - Hành động: đi theo một đoạn đường (cạnh), tôn trọng đường một chiều.
   - Chi phí: độ dài đoạn đường tính bằng mét.
   - Heuristic: khoảng cách đường chim bay (công thức Haversine).
"""

import json
import math

EARTH_RADIUS_M = 6371008.8


# ---------------------------------------------------------------------------
# Bản đồ thật
# ---------------------------------------------------------------------------
def haversine(lat1, lon1, lat2, lon2):
    """Khoảng cách đường chim bay (mét) giữa hai điểm trên mặt cầu Trái Đất."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(a)))


class MapProblem:
    """
    nodes: {id: (lat, lon)}
    edges: danh sách [u, v, độ_dài_m, tên_đường, cấp_đường, hình_học]
           cấp_đường: 3 = đường lớn, 2 = đường vừa, 1 = đường nhỏ
           hình_học: [[lat, lon], ...] hoặc None (đoạn thẳng u -> v)
    """

    def __init__(self, nodes, edges, meta=None):
        self.nodes = nodes
        self.meta = meta or {}
        self.edge_info = {}   # (u, v) -> (length, name, road_class, geometry)
        for u, v, length, name, road_class, geom in edges:
            key = (u, v)
            old = self.edge_info.get(key)
            if old is None or length < old[0]:     # giữ đoạn ngắn nhất nếu trùng
                self.edge_info[key] = (length, name or "", road_class, geom)

        self.adj = {n: [] for n in nodes}
        for (u, v), (length, _, _, _) in self.edge_info.items():
            self.adj[u].append((v, length))

    @classmethod
    def load(cls, path):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        nodes = {i: (lat, lon) for i, (lat, lon) in enumerate(data["nodes"])}
        return cls(nodes, data["edges"], data.get("meta"))

    def neighbors(self, node):
        return self.adj.get(node, ())

    def heuristic(self, a, b):
        lat1, lon1 = self.nodes[a]
        lat2, lon2 = self.nodes[b]
        return haversine(lat1, lon1, lat2, lon2)

    def street_names(self, path):
        """Danh sách tên đường dọc lộ trình, gộp các đoạn liên tiếp cùng tên."""
        names = []
        for u, v in zip(path, path[1:]):
            name = self.edge_info[(u, v)][1] or "(đường không tên)"
            if not names or names[-1] != name:
                names.append(name)
        return names
