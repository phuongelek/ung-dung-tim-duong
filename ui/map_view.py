"""Tìm đường trên bản đồ đường phố TP.HCM (OpenStreetMap) bằng A*."""

import math
import os
import webbrowser
from collections import defaultdict

import pygame

from core.astar import astar, astar_steps
from core.problems import MapProblem
from ui.common import (C, Button, draw_legend_item, draw_stat, draw_text, font,
                       format_number, wrap_text)

SIDEBAR_W = 300
SPEEDS = [2, 10, 30, 100, 400, 0]          # số nút mở rộng mỗi khung hình; 0 = tức thì
SPEED_NAMES = ["Rất chậm", "Chậm", "Vừa", "Nhanh", "Rất nhanh", "Tức thì"]

# Độ rộng đường (mét thực tế) và giới hạn pixel theo cấp đường
ROAD_STYLE = {
    1: dict(color=C["road_minor"], meters=7, min_px=1, max_px=6),
    2: dict(color=C["road_mid"], meters=12, min_px=2, max_px=10),
    3: dict(color=C["road_major"], meters=18, min_px=3, max_px=14),
}

# Kiểu chữ tên đường theo cấp đường: (cỡ chữ, in đậm, màu)
LABEL_STYLE = {
    3: (13, True, (52, 56, 68)),
    2: (12, False, (60, 64, 76)),
    1: (11, False, (92, 98, 112)),
}
# Mức phóng to (so với lúc vừa khung) để bắt đầu hiện tên từng cấp đường
LABEL_MIN_ZOOM = {3: 0.0, 2: 1.5, 1: 4.0}


def _point_at(pts, cum, s):
    """Điểm nằm ở vị trí s (pixel) dọc theo đường gấp khúc pts."""
    for i in range(1, len(cum)):
        if cum[i] >= s:
            seg = cum[i] - cum[i - 1]
            t = 0 if seg == 0 else (s - cum[i - 1]) / seg
            (x0, y0), (x1, y1) = pts[i - 1], pts[i]
            return (x0 + (x1 - x0) * t, y0 + (y1 - y0) * t)
    return pts[-1]


class MapView:
    def __init__(self, rect, data_path):
        self.rect = rect
        self.side = pygame.Rect(rect.right - SIDEBAR_W, rect.top, SIDEBAR_W, rect.height)
        self.map_rect = pygame.Rect(rect.left, rect.top, rect.width - SIDEBAR_W, rect.height)
        self.data_path = data_path

        self.problem = None
        self.load_state = "pending"     # pending | loading | ok | missing | error
        self.error = ""

        self.start = None
        self.goal = None
        self.speed_idx = 2
        self.show_labels = True

        self.press_pos = None
        self.panning = False
        self.pan_offset = (0, 0)
        self.view_dirty = True
        self.base = None
        self.overlay = None
        self.road_labels = None
        self.route_labels = None
        self._label_cache = {}

        self._build_buttons()
        self.reset_search()

    # ------------------------------------------------------------------ nút bấm
    def _build_buttons(self):
        x = self.side.left + 16
        w = SIDEBAR_W - 32
        half = (w - 6) // 2
        y = self.side.top + 98
        self.btn_run = Button("Chạy A*   [Space]", self.run, primary=True, height=38)
        self.btn_run.rect = pygame.Rect(x, y, w, 38)
        y += 46
        row1 = [Button("Xóa kết quả [C]", self.reset_search),
                Button("Bỏ chọn [N]", self.clear_points)]
        row2 = [Button("Vừa khung [F]", self.fit_view),
                Button("Đảo chiều [V]", self.swap_points)]
        for row in (row1, row2):
            row[0].rect = pygame.Rect(x, y, half, 32)
            row[1].rect = pygame.Rect(x + half + 6, y, half, 32)
            y += 38
        self.btn_gmaps = Button("Mở trên Google Maps [G]", self.open_google_maps)
        self.btn_gmaps.rect = pygame.Rect(x, y, w, 32)
        y += 38
        self.btn_slower = Button("-", self.slower)
        self.btn_faster = Button("+", self.faster)
        self.btn_slower.rect = pygame.Rect(x, y, 36, 32)
        self.btn_faster.rect = pygame.Rect(x + w - 36, y, 36, 32)
        self.speed_label_pos = (x + w // 2, y + 16)
        self.controls_bottom = y + 32
        self.buttons = [self.btn_run, *row1, *row2, self.btn_gmaps,
                        self.btn_slower, self.btn_faster]

    # ------------------------------------------------------------------ dữ liệu
    def _load(self):
        if not os.path.exists(self.data_path):
            self.load_state = "missing"
            return
        try:
            self.problem = MapProblem.load(self.data_path)
            self._project()
            self._build_label_chains()
            self.fit_view()
            self.load_state = "ok"
        except Exception as ex:          # dữ liệu hỏng hoặc sai định dạng
            self.load_state = "error"
            self.error = str(ex)

    def _proj(self, lat, lon):
        """Chiếu (lat, lon) sang mặt phẳng (mét) quanh tâm bản đồ."""
        return ((lon - self.lon0) * self.kx, (lat - self.lat0) * self.ky)

    def _project(self):
        p = self.problem
        lats = [lat for lat, _ in p.nodes.values()]
        lons = [lon for _, lon in p.nodes.values()]
        self.lat0 = (min(lats) + max(lats)) / 2
        self.lon0 = (min(lons) + max(lons)) / 2
        self.kx = 111320.0 * math.cos(math.radians(self.lat0))
        self.ky = 110574.0

        self.xy = {n: self._proj(lat, lon) for n, (lat, lon) in p.nodes.items()}
        self.edge_pts = {}
        for (u, v), (_, _, _, geom) in p.edge_info.items():
            if geom:
                self.edge_pts[(u, v)] = [self._proj(lat, lon) for lat, lon in geom]
            else:
                self.edge_pts[(u, v)] = [self.xy[u], self.xy[v]]

        # Đường hai chiều chỉ cần vẽ nền một lần
        seen = set()
        self.roads = []
        for (u, v), (_, _, road_class, _) in p.edge_info.items():
            key = (min(u, v), max(u, v))
            if key in seen:
                continue
            seen.add(key)
            pts = self.edge_pts[(u, v)]
            self.roads.append((road_class, pts, *self._bbox(pts)))
        self.roads.sort(key=lambda r: r[0])

        xs = [q[0] for q in self.xy.values()]
        ys = [q[1] for q in self.xy.values()]
        self.bounds = (min(xs), min(ys), max(xs), max(ys))

    @staticmethod
    def _bbox(pts):
        xs = [q[0] for q in pts]
        ys = [q[1] for q in pts]
        return min(xs), min(ys), max(xs), max(ys)

    def _oriented_pts(self, a, b):
        """Hình học đoạn đường theo chiều a -> b."""
        if (a, b) in self.edge_pts:
            return self.edge_pts[(a, b)]
        return self.edge_pts[(b, a)][::-1]

    def _build_label_chains(self):
        """
        OSM chia một con đường thành nhiều đoạn ngắn giữa các giao lộ, quá ngắn để ghi chữ.
        Ở đây nối các đoạn liền nhau cùng tên thành một "chuỗi" dài để đặt nhãn tên đường.
        """
        by_name = defaultdict(dict)     # tên -> {(u, v) không hướng: cấp đường}
        for (u, v), (_, name, road_class, _) in self.problem.edge_info.items():
            if name:
                key = (min(u, v), max(u, v))
                by_name[name][key] = max(road_class, by_name[name].get(key, 0))

        self.label_chains = []          # (cấp, tên, điểm, xmin, ymin, xmax, ymax, độ dài)
        for name, edges in by_name.items():
            adj = defaultdict(list)
            for (u, v) in edges:
                adj[u].append(v)
                adj[v].append(u)
            used = set()

            def walk(a, b):
                pts = list(self._oriented_pts(a, b))
                cls = edges[(min(a, b), max(a, b))]
                used.add((min(a, b), max(a, b)))
                while len(adj[b]) == 2:            # đi tiếp khi giao lộ chỉ nối hai đoạn cùng tên
                    nxt = adj[b][0] if adj[b][0] != a else adj[b][1]
                    key = (min(b, nxt), max(b, nxt))
                    if key in used:
                        break
                    used.add(key)
                    cls = max(cls, edges[key])
                    pts.extend(self._oriented_pts(b, nxt)[1:])
                    a, b = b, nxt
                return cls, pts

            starts = [n for n in adj if len(adj[n]) != 2] + list(adj)
            for a in starts:
                for b in adj[a]:
                    if (min(a, b), max(a, b)) in used:
                        continue
                    cls, pts = walk(a, b)
                    length = sum(math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1))
                    self.label_chains.append((cls, name, pts, *self._bbox(pts), length))
        # Đường cấp cao và dài được ưu tiên đặt nhãn trước
        self.label_chains.sort(key=lambda c: (-c[0], -c[7]))

    # ------------------------------------------------------------------ khung nhìn
    def fit_view(self):
        if self.problem is None:
            return
        minx, miny, maxx, maxy = self.bounds
        w, h = self.map_rect.size
        self.cx = (minx + maxx) / 2
        self.cy = (miny + maxy) / 2
        self.fit_scale = min(w / max(1, maxx - minx), h / max(1, maxy - miny)) * 0.95
        self.scale = self.fit_scale
        self.view_dirty = True

    def to_local(self, x, y):
        w, h = self.map_rect.size
        return (w / 2 + (x - self.cx) * self.scale, h / 2 - (y - self.cy) * self.scale)

    def to_world(self, pos):
        w, h = self.map_rect.size
        lx = pos[0] - self.map_rect.left
        ly = pos[1] - self.map_rect.top
        return (self.cx + (lx - w / 2) / self.scale, self.cy - (ly - h / 2) / self.scale)

    def visible_world(self, margin_px=0):
        wx0, wy1 = self.to_world(self.map_rect.topleft)
        wx1, wy0 = self.to_world(self.map_rect.bottomright)
        m = margin_px / self.scale
        return wx0 - m, wy0 - m, wx1 + m, wy1 + m

    def zoom(self, factor, pos):
        wx, wy = self.to_world(pos)
        new_scale = min(max(self.scale * factor, self.fit_scale * 0.5), self.fit_scale * 40)
        if new_scale == self.scale:
            return
        self.scale = new_scale
        w, h = self.map_rect.size
        lx = pos[0] - self.map_rect.left
        ly = pos[1] - self.map_rect.top
        self.cx = wx - (lx - w / 2) / self.scale
        self.cy = wy + (ly - h / 2) / self.scale
        self.view_dirty = True

    def nearest_node(self, pos):
        wx, wy = self.to_world(pos)
        return min(self.xy, key=lambda n: (self.xy[n][0] - wx) ** 2 + (self.xy[n][1] - wy) ** 2)

    # ------------------------------------------------------------------ hành động
    def reset_search(self):
        self.state = "edit"       # edit | running | done
        self.steps = None
        self.explored = []        # các cạnh (u, v) A* đã xét, theo thứ tự
        self.current = None
        self.expanded_count = 0
        self.result = None
        self.timed = None
        self.overlay_dirty = True
        self.labels_dirty = True
        self.message = None       # (nội dung, màu)

    def clear_points(self):
        self.start = self.goal = None
        self.reset_search()

    def swap_points(self):
        if self.start is not None and self.goal is not None:
            was_done = self.state == "done"
            self.start, self.goal = self.goal, self.start
            if was_done:
                self.run(instant=True)
            else:
                self.reset_search()

    def slower(self):
        self.speed_idx = max(0, self.speed_idx - 1)

    def faster(self):
        self.speed_idx = min(len(SPEEDS) - 1, self.speed_idx + 1)

    def toggle_labels(self):
        self.show_labels = not self.show_labels
        self.labels_dirty = True

    def run(self, instant=False):
        if self.problem is None:
            return
        if self.start is None or self.goal is None:
            self.message = ("Hãy chọn đủ điểm đầu và điểm đích.", C["goal"])
            return
        self.reset_search()
        self.timed = astar(self.problem, self.start, self.goal)
        if instant or SPEEDS[self.speed_idx] == 0:
            self._show_result(self.timed)
            return
        self.steps = astar_steps(self.problem, self.start, self.goal)
        self.state = "running"

    def _show_result(self, res):
        res.time_ms = self.timed.time_ms
        self.result = res
        self.explored = [(p, n) for n, p in res.parent.items() if p is not None]
        self.overlay_dirty = True
        self.labels_dirty = True
        self.current = None
        self.steps = None
        self.state = "done"

    def open_google_maps(self):
        """Mở cùng điểm đầu/đích trên Google Maps (trình duyệt) để đối chiếu kết quả."""
        if self.problem is None or self.start is None or self.goal is None:
            self.message = ("Hãy chọn đủ điểm đầu và điểm đích trước.", C["goal"])
            return
        lat1, lon1 = self.problem.nodes[self.start]
        lat2, lon2 = self.problem.nodes[self.goal]
        url = ("https://www.google.com/maps/dir/?api=1"
               f"&origin={lat1:.6f},{lon1:.6f}&destination={lat2:.6f},{lon2:.6f}"
               "&travelmode=driving")
        try:
            webbrowser.open(url)
            self.message = ("Đã mở Google Maps trên trình duyệt.", C["accent"])
        except Exception:
            self.message = ("Không mở được trình duyệt.", C["goal"])

    def select(self, pos, which):
        node = self.nearest_node(pos)
        live = self.state == "done"
        if which == "goal":
            if node == self.start:
                return
            self.goal = node
        else:
            if self.start is None or self.goal is not None:
                if node == self.goal:
                    return
                self.start = node
            else:
                if node == self.start:
                    return
                self.goal = node
        if live and self.start is not None and self.goal is not None:
            self.run(instant=True)          # đã có kết quả -> tính lại ngay
        else:
            self.reset_search()

    # ------------------------------------------------------------------ sự kiện
    def handle_event(self, event):
        for b in self.buttons:
            if b.handle_event(event):
                return
        if self.load_state != "ok":
            return

        if event.type == pygame.KEYDOWN:
            keys = {
                pygame.K_SPACE: self.run, pygame.K_c: self.reset_search,
                pygame.K_n: self.clear_points, pygame.K_f: self.fit_view,
                pygame.K_v: self.swap_points, pygame.K_g: self.open_google_maps,
                pygame.K_l: self.toggle_labels,
                pygame.K_EQUALS: self.faster, pygame.K_PLUS: self.faster,
                pygame.K_KP_PLUS: self.faster, pygame.K_MINUS: self.slower,
                pygame.K_KP_MINUS: self.slower,
            }
            if event.key in keys:
                keys[event.key]()

        elif event.type == pygame.MOUSEWHEEL:
            pos = pygame.mouse.get_pos()
            if self.map_rect.collidepoint(pos) and not self.panning:
                self.zoom(1.25 ** event.y, pos)

        elif event.type == pygame.MOUSEBUTTONDOWN and self.map_rect.collidepoint(event.pos):
            if event.button == 1:
                self.press_pos = event.pos
                self.panning = False
            elif event.button == 3 and self.state != "running":
                self.select(event.pos, "goal")

        elif event.type == pygame.MOUSEMOTION and self.press_pos:
            dx = event.pos[0] - self.press_pos[0]
            dy = event.pos[1] - self.press_pos[1]
            if self.panning or abs(dx) + abs(dy) > 5:
                self.panning = True
                self.pan_offset = (dx, dy)

        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1 and self.press_pos:
            if self.panning:
                dx, dy = self.pan_offset
                self.cx -= dx / self.scale
                self.cy += dy / self.scale
                self.view_dirty = True
            elif self.state != "running":
                self.select(event.pos, "auto")
            self.press_pos = None
            self.panning = False
            self.pan_offset = (0, 0)

    # ------------------------------------------------------------------ cập nhật
    def update(self):
        if self.load_state == "loading":
            self._load()
            return
        if self.state != "running":
            return
        for _ in range(SPEEDS[self.speed_idx]):
            try:
                node, opened = next(self.steps)
            except StopIteration as stop:
                self._show_result(stop.value)
                return
            for nxt in opened:
                self.explored.append((node, nxt))
                if self.overlay is not None and not self.view_dirty and not self.overlay_dirty:
                    self._draw_explored_edge(node, nxt)
            self.expanded_count += 1
            self.current = node

    # ------------------------------------------------------------------ vẽ nền đường
    def _road_width(self, road_class):
        st = ROAD_STYLE[road_class]
        return int(min(max(st["meters"] * self.scale, st["min_px"]), st["max_px"]))

    def _render_base(self):
        w, h = self.map_rect.size
        self.base = pygame.Surface((w, h))
        self.base.fill(C["map_bg"])
        wx0, wy0, wx1, wy1 = self.visible_world(margin_px=300)   # chừa thêm cho lúc kéo
        visible = [r for r in self.roads
                   if r[4] >= wx0 and r[2] <= wx1 and r[5] >= wy0 and r[3] <= wy1]
        # Viền cho đường lớn trước, rồi lần lượt các cấp đường (nhỏ dưới, lớn trên)
        major_w = self._road_width(3)
        for road_class, pts, *_ in visible:
            if road_class == 3:
                spts = [self.to_local(x, y) for x, y in pts]
                pygame.draw.lines(self.base, C["road_major_edge"], False, spts, major_w + 2)
        for road_class, pts, *_ in visible:
            spts = [self.to_local(x, y) for x, y in pts]
            pygame.draw.lines(self.base, ROAD_STYLE[road_class]["color"], False, spts,
                              self._road_width(road_class))

    def _draw_explored_edge(self, u, v):
        spts = [self.to_local(x, y) for x, y in self.edge_pts[(u, v)]]
        pygame.draw.lines(self.overlay, C["explored"], False, spts, self._explored_w)

    def _render_overlay(self):
        self.overlay = pygame.Surface(self.map_rect.size, pygame.SRCALPHA)
        self._explored_w = max(2, min(5, int(5 * self.scale)))
        for u, v in self.explored:
            self._draw_explored_edge(u, v)
        self.overlay_dirty = False

    # ------------------------------------------------------------------ tên đường
    def _label_image(self, text, style):
        """Ảnh chữ (đã cache). style: cấp đường 1-3, hoặc "route" cho nhãn trên lộ trình."""
        key = (text, style)
        img = self._label_cache.get(key)
        if img is not None:
            return img
        if style == "route":
            f = font(13, True)
            txt = f.render(text, True, (255, 255, 255))
            w, h = txt.get_size()
            img = pygame.Surface((w + 14, h + 4), pygame.SRCALPHA)
            pygame.draw.rect(img, C["path_line"], img.get_rect(), border_radius=(h + 4) // 2)
            img.blit(txt, (7, 2))
        else:
            size, bold, color = LABEL_STYLE[style]
            f = font(size, bold)
            fg = f.render(text, True, color)
            halo = f.render(text, True, C["map_bg"])
            w, h = fg.get_size()
            img = pygame.Surface((w + 4, h + 4), pygame.SRCALPHA)
            for dx in (-2, -1, 0, 1, 2):          # viền sáng quanh chữ cho dễ đọc
                for dy in (-2, -1, 0, 1, 2):
                    if dx or dy:
                        img.blit(halo, (2 + dx, 2 + dy))
            img.blit(fg, (2, 2))
        self._label_cache[key] = img
        return img

    def _place_labels(self, target, pts, img, placed, max_count, gap, straightness):
        """
        Đặt tối đa max_count nhãn dọc đường gấp khúc pts (tọa độ màn hình).
        Nhãn được xoay theo hướng đường, chỉ đặt ở khúc đủ thẳng và không đè nhãn khác.
        """
        cum = [0.0]
        for i in range(1, len(pts)):
            cum.append(cum[-1] + math.dist(pts[i - 1], pts[i]))
        total = cum[-1]
        need = img.get_width() + 10
        if total < need:
            return 0
        w, h = self.map_rect.size
        bounds = pygame.Rect(4, 4, w - 8, h - 8)

        # Thử từ giữa đường ra hai phía, cách nhau một khoảng gap
        step = need + gap
        candidates = [total / 2]
        k = 1
        while total / 2 - k * step >= need / 2 or total / 2 + k * step <= total - need / 2:
            candidates += [total / 2 - k * step, total / 2 + k * step]
            k += 1
        count = 0
        for s in candidates:
            if s < need / 2 or s > total - need / 2:
                continue
            a = _point_at(pts, cum, s - need / 2)
            b = _point_at(pts, cum, s + need / 2)
            if math.dist(a, b) < need * straightness:      # khúc quá cong
                continue
            angle = math.degrees(math.atan2(-(b[1] - a[1]), b[0] - a[0]))
            if angle > 90:                                  # không để chữ bị lộn ngược
                angle -= 180
            elif angle < -90:
                angle += 180
            rotated = pygame.transform.rotozoom(img, angle, 1)
            rect = rotated.get_rect(center=((a[0] + b[0]) / 2, (a[1] + b[1]) / 2))
            if not bounds.contains(rect):
                continue
            hit = rect.inflate(-rect.width * 0.15, -rect.height * 0.15)
            if hit.collidelist(placed) != -1:
                continue
            target.blit(rotated, rect)
            placed.append(rect)
            count += 1
            if count >= max_count:
                break
        return count

    def _route_runs(self):
        """Chia lộ trình thành các đoạn liên tiếp cùng tên đường."""
        runs = []
        path = self.result.path
        for u, v in zip(path, path[1:]):
            name = self.problem.edge_info[(u, v)][1]
            pts = self.edge_pts[(u, v)]
            if runs and runs[-1][0] == name:
                runs[-1][1].extend(pts[1:])
            else:
                runs.append((name, list(pts)))
        return [(name, pts) for name, pts in runs if name]

    def _render_labels(self):
        size = self.map_rect.size
        self.road_labels = pygame.Surface(size, pygame.SRCALPHA)
        self.route_labels = pygame.Surface(size, pygame.SRCALPHA)
        self.labels_dirty = False
        if not self.show_labels:
            return
        placed = []

        # 1) Tên đường dọc lộ trình A* tìm được: ưu tiên cao nhất
        if self.result is not None and self.result.found:
            for name, wpts in self._route_runs():
                spts = [self.to_local(x, y) for x, y in wpts]
                self._place_labels(self.route_labels, spts, self._label_image(name, "route"),
                                   placed, max_count=2, gap=500, straightness=0.75)

        # 2) Tên các đường khác, tùy mức phóng to
        zoom = self.scale / self.fit_scale
        wx0, wy0, wx1, wy1 = self.visible_world()
        for cls, name, wpts, x0, y0, x1, y1, length in self.label_chains:
            if zoom < LABEL_MIN_ZOOM[cls]:
                continue
            if x1 < wx0 or x0 > wx1 or y1 < wy0 or y0 > wy1:
                continue
            if length * self.scale < 60:               # quá ngắn trên màn hình
                continue
            spts = [self.to_local(x, y) for x, y in wpts]
            self._place_labels(self.road_labels, spts, self._label_image(name, cls),
                               placed, max_count=3, gap=320, straightness=0.9)

    # ------------------------------------------------------------------ vẽ tổng thể
    def _nice_scale_bar(self):
        target = 110 / self.scale       # khoảng 110 px tính ra mét
        for m in (20, 50, 100, 200, 500, 1000, 2000, 5000, 10000):
            if m >= target * 0.6:
                return m
        return 10000

    def draw(self, surf):
        pygame.draw.rect(surf, C["bg"], self.rect)
        pygame.draw.rect(surf, C["map_bg"], self.map_rect)

        if self.load_state == "pending":
            self.load_state = "loading"     # tải ở khung hình kế tiếp, sau khi đã vẽ chữ
        if self.load_state in ("pending", "loading"):
            draw_text(surf, "Đang tải dữ liệu bản đồ...", self.map_rect.center, 18,
                      C["muted"], anchor="center")
        elif self.load_state in ("missing", "error"):
            self._draw_missing(surf)
        else:
            self._draw_map(surf)
        self._draw_sidebar(surf)

    def _draw_missing(self, surf):
        cx, cy = self.map_rect.center
        if self.load_state == "missing":
            lines = [("Chưa có dữ liệu bản đồ", 20, True, C["text"]),
                     ("Chạy lệnh sau một lần (cần Internet) để tải đường phố TP.HCM:", 15, False, C["muted"]),
                     ("python prepare_map.py", 17, True, C["accent"]),
                     ("rồi mở lại ứng dụng.", 15, False, C["muted"])]
        else:
            lines = [("Không đọc được file bản đồ", 20, True, C["goal"]),
                     (self.error[:90], 14, False, C["muted"]),
                     ("Hãy chạy lại: python prepare_map.py", 15, False, C["text"])]
        y = cy - len(lines) * 16
        for text, size, bold, color in lines:
            draw_text(surf, text, (cx, y), size, color, bold=bold, anchor="center")
            y += size + 16

    def _draw_map(self, surf):
        if self.view_dirty:
            self._render_base()
            self.overlay_dirty = True
            self.labels_dirty = True
            self.view_dirty = False
        if self.overlay_dirty:
            self._render_overlay()
        if self.labels_dirty:
            self._render_labels()

        ox = self.map_rect.left + self.pan_offset[0]
        oy = self.map_rect.top + self.pan_offset[1]
        surf.set_clip(self.map_rect)
        surf.blit(self.base, (ox, oy))
        surf.blit(self.overlay, (ox, oy))
        surf.blit(self.road_labels, (ox, oy))

        def scr(n):
            x, y = self.to_local(*self.xy[n])
            return (x + ox, y + oy)

        # Đường đi tìm được
        if self.result and self.result.found and len(self.result.path) > 1:
            pts = []
            for u, v in zip(self.result.path, self.result.path[1:]):
                for x, y in self.edge_pts[(u, v)]:
                    lx, ly = self.to_local(x, y)
                    pts.append((lx + ox, ly + oy))
            width = max(4, min(8, int(9 * self.scale)))
            pygame.draw.lines(surf, (255, 255, 255), False, pts, width + 4)
            pygame.draw.lines(surf, C["path_line"], False, pts, width)
            for p in pts[1:-1]:
                pygame.draw.circle(surf, C["path_line"], p, width // 2)
            surf.blit(self.route_labels, (ox, oy))

        if self.current is not None:
            pygame.draw.circle(surf, C["current"], scr(self.current), 6)

        for node, color, label in ((self.start, C["start"], "S"), (self.goal, C["goal"], "G")):
            if node is None:
                continue
            p = scr(node)
            pygame.draw.circle(surf, (255, 255, 255), p, 13)
            pygame.draw.circle(surf, color, p, 11)
            draw_text(surf, label, p, 13, (255, 255, 255), bold=True, anchor="center")

        # Thước tỉ lệ + ghi công nguồn dữ liệu
        meters = self._nice_scale_bar()
        px = meters * self.scale
        bx, by = self.map_rect.left + 16, self.map_rect.bottom - 18
        pygame.draw.rect(surf, (255, 255, 255), (bx - 6, by - 22, px + 12, 30), border_radius=4)
        pygame.draw.line(surf, C["text"], (bx, by), (bx + px, by), 3)
        pygame.draw.line(surf, C["text"], (bx, by - 6), (bx, by), 2)
        pygame.draw.line(surf, C["text"], (bx + px, by - 6), (bx + px, by), 2)
        label = f"{meters // 1000} km" if meters >= 1000 else f"{meters} m"
        draw_text(surf, label, (bx + px / 2, by - 6), 12, anchor="midbottom")
        draw_text(surf, "© OpenStreetMap contributors",
                  (self.map_rect.right - 8, self.map_rect.bottom - 6), 12, C["muted"],
                  anchor="bottomright")
        surf.set_clip(None)

    def _draw_sidebar(self, surf):
        s = self.side
        pygame.draw.rect(surf, C["panel"], s)
        pygame.draw.line(surf, C["border"], s.topleft, s.bottomleft)
        x, w = s.left + 16, SIDEBAR_W - 32

        draw_text(surf, "Tìm đường bằng A*", (x, s.top + 14), 19, bold=True)
        draw_text(surf, "Bản đồ TP.HCM · dữ liệu OpenStreetMap", (x, s.top + 40), 13, C["muted"])
        if self.problem:
            info = (f"{format_number(len(self.problem.nodes))} giao lộ · "
                    f"{format_number(len(self.problem.edge_info))} đoạn đường")
            draw_text(surf, info, (x, s.top + 58), 13, C["muted"])
        draw_text(surf, "heuristic: khoảng cách chim bay (Haversine)", (x, s.top + 76), 12, C["muted"])

        ready = self.load_state == "ok"
        self.btn_run.enabled = ready and self.state != "running"
        self.btn_gmaps.enabled = ready and self.start is not None and self.goal is not None
        for b in self.buttons:
            b.draw(surf)
        draw_text(surf, f"Tốc độ: {SPEED_NAMES[self.speed_idx]}", self.speed_label_pos, 14,
                  anchor="center")

        y = self.controls_bottom + 12
        # Hướng dẫn chọn điểm
        if ready:
            if self.message:
                hint, color = self.message
            elif self.start is None:
                hint, color = "Click trái lên bản đồ để chọn ĐIỂM ĐẦU", C["start"]
            elif self.goal is None:
                hint, color = "Click lần nữa để chọn ĐIỂM ĐÍCH", C["goal"]
            elif self.state == "edit":
                hint, color = "Nhấn Space để chạy A*", C["accent"]
            else:
                hint, color = "Click trái: đổi điểm đầu · phải: đổi đích", C["muted"]
            draw_text(surf, hint, (x, y), 13, color, bold=True)
        y += 24

        draw_text(surf, "KẾT QUẢ", (x, y), 13, C["muted"], bold=True)
        y += 22
        res = self.result
        if self.state == "running":
            status = "Đang tìm..."
        elif res is None:
            status = "Chưa chạy"
        else:
            status = "Tìm thấy đường" if res.found else "Không có đường!"
        y = draw_stat(surf, "Trạng thái", status, x, y, w)

        if self.start is not None and self.goal is not None:
            straight = self.problem.heuristic(self.start, self.goal)
            y = draw_stat(surf, "Đường chim bay", f"{straight / 1000:.2f} km", x, y, w)
        else:
            y = draw_stat(surf, "Đường chim bay", "–", x, y, w)
        found = res is not None and res.found
        y = draw_stat(surf, "Quãng đường A*", f"{res.cost / 1000:.2f} km" if found else "–", x, y, w)
        y = draw_stat(surf, "Số giao lộ đi qua", format_number(len(res.path)) if found else "–", x, y, w)
        if self.state == "running":
            exp = format_number(self.expanded_count)
        else:
            exp = format_number(res.expanded) if res else "–"
        y = draw_stat(surf, "Nút đã mở rộng", exp, x, y, w)
        y = draw_stat(surf, "OPEN lớn nhất", format_number(res.max_frontier) if res else "–", x, y, w)
        y = draw_stat(surf, "Thời gian tính", f"{res.time_ms:.2f} ms" if res else "–", x, y, w)

        y += 4
        draw_text(surf, "LỘ TRÌNH", (x, y), 13, C["muted"], bold=True)
        y += 22
        if found:
            route = " → ".join(self.problem.street_names(res.path))
            lines = wrap_text(route, 13, w)
            max_lines = max(1, (s.bottom - 92 - y) // 18)
            if len(lines) > max_lines:
                lines = lines[:max_lines]
                lines[-1] += " ..."
            for line in lines:
                draw_text(surf, line, (x, y), 13)
                y += 18
        else:
            draw_text(surf, "–", (x, y), 13, C["muted"])

        # Chú thích + phím tắt ở đáy
        y = s.bottom - 86
        draw_legend_item(surf, C["explored"], "Đoạn A* đã xét", x, y)
        draw_legend_item(surf, C["path_line"], "Đường đi", x + w // 2 + 10, y)
        y += 26
        for line in ("Kéo chuột trái: di chuyển · Cuộn: phóng to",
                     "Click phải: chọn điểm đích · L: ẩn/hiện tên",
                     "+/-: tốc độ · Esc: thoát"):
            draw_text(surf, line, (x, y), 12, C["muted"])
            y += 18
