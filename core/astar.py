"""
Thuật toán A*. Đối tượng problem cần có:
    neighbors(state) -> các cặp (trạng thái kế, chi phí)
    heuristic(a, b)  -> ước lượng chi phí từ a đến b
"""

import heapq
import itertools
import math
import time
from dataclasses import dataclass, field


@dataclass
class SearchResult:
    found: bool
    path: list
    cost: float
    expanded: int               # số nút đã mở rộng
    generated: int              # số lần đưa nút vào OPEN
    max_frontier: int
    time_ms: float = 0.0
    g: dict = field(default_factory=dict, repr=False)
    parent: dict = field(default_factory=dict, repr=False)
    closed: set = field(default_factory=set, repr=False)


def reconstruct_path(parent, goal):
    path = []
    node = goal
    while node is not None:
        path.append(node)
        node = parent[node]
    path.reverse()
    return path


def astar_steps(problem, start, goal):
    """Chạy A* từng bước: yield (nút vừa mở rộng, các nút mới vào OPEN), return SearchResult."""
    counter = itertools.count()  # dùng khi f và h bằng nhau
    h_start = problem.heuristic(start, goal)

    # OPEN: (f, h, thứ tự, trạng thái), f bằng nhau thì ưu tiên h nhỏ hơn
    open_heap = [(h_start, h_start, next(counter), start)]
    g = {start: 0.0}
    parent = {start: None}
    closed = set()

    expanded = 0
    generated = 1
    max_frontier = 1

    while open_heap:
        _, _, _, node = heapq.heappop(open_heap)

        # bản cũ của nút đã xét, bỏ qua
        if node in closed:
            continue

        # kiểm tra đích khi lấy ra khỏi OPEN mới đảm bảo tối ưu
        if node == goal:
            return SearchResult(True, reconstruct_path(parent, goal), g[goal],
                                expanded, generated, max_frontier,
                                g=g, parent=parent, closed=closed)

        closed.add(node)
        expanded += 1

        opened = []
        for nxt, step_cost in problem.neighbors(node):
            if nxt in closed:
                continue
            new_g = g[node] + step_cost
            if new_g < g.get(nxt, math.inf):  # đường mới tốt hơn
                g[nxt] = new_g
                parent[nxt] = node
                h = problem.heuristic(nxt, goal)
                heapq.heappush(open_heap, (new_g + h, h, next(counter), nxt))
                generated += 1
                opened.append(nxt)

        if len(open_heap) > max_frontier:
            max_frontier = len(open_heap)

        yield node, opened

    return SearchResult(False, [], math.inf, expanded, generated, max_frontier,
                        g=g, parent=parent, closed=closed)


def astar(problem, start, goal):
    t0 = time.perf_counter()
    steps = astar_steps(problem, start, goal)
    while True:
        try:
            next(steps)
        except StopIteration as stop:
            result = stop.value
            break
    result.time_ms = (time.perf_counter() - t0) * 1000
    return result
