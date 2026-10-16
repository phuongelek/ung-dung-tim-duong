"""
Các thuật toán khác (BFS, DFS, UCS, Greedy) – CHỈ dùng trong compare.py để lấy
số liệu so sánh cho báo cáo. Ứng dụng chính chỉ dùng A*.
Mọi hàm đều trả về SearchResult giống A* để so sánh công bằng.
"""

import heapq
import itertools
import math
import time
from collections import deque

from .astar import SearchResult, astar, reconstruct_path


def _done(found, parent, g, goal, expanded, generated, max_frontier, t0, closed):
    if found:
        path = reconstruct_path(parent, goal)
        res = SearchResult(True, path, g[goal], expanded, generated, max_frontier,
                           g=g, parent=parent, closed=closed)
    else:
        res = SearchResult(False, [], math.inf, expanded, generated, max_frontier,
                           g=g, parent=parent, closed=closed)
    res.time_ms = (time.perf_counter() - t0) * 1000
    return res


def bfs(problem, start, goal):
    """Tìm kiếm theo chiều rộng: ít BƯỚC nhất, không xét chi phí."""
    t0 = time.perf_counter()
    parent, g = {start: None}, {start: 0.0}
    queue = deque([start])
    closed = set()
    expanded, generated, max_frontier = 0, 1, 1
    if start == goal:
        return _done(True, parent, g, goal, 0, 1, 1, t0, closed)
    while queue:
        node = queue.popleft()
        closed.add(node)
        expanded += 1
        for nxt, cost in problem.neighbors(node):
            if nxt in parent:
                continue
            parent[nxt] = node
            g[nxt] = g[node] + cost
            generated += 1
            if nxt == goal:                       # kiểm tra đích ngay khi sinh ra
                return _done(True, parent, g, goal, expanded, generated, max_frontier, t0, closed)
            queue.append(nxt)
        max_frontier = max(max_frontier, len(queue))
    return _done(False, parent, g, goal, expanded, generated, max_frontier, t0, closed)


def dfs(problem, start, goal):
    """Tìm kiếm theo chiều sâu (dạng đồ thị, dùng ngăn xếp)."""
    t0 = time.perf_counter()
    stack = [(start, None, 0.0)]
    parent, g, closed = {}, {}, set()
    expanded, generated, max_frontier = 0, 1, 1
    while stack:
        node, par, cost_so_far = stack.pop()
        if node in closed:
            continue
        parent[node] = par
        g[node] = cost_so_far
        if node == goal:
            return _done(True, parent, g, goal, expanded, generated, max_frontier, t0, closed)
        closed.add(node)
        expanded += 1
        for nxt, cost in reversed(list(problem.neighbors(node))):
            if nxt not in closed:
                stack.append((nxt, node, cost_so_far + cost))
                generated += 1
        max_frontier = max(max_frontier, len(stack))
    return _done(False, parent, g, goal, expanded, generated, max_frontier, t0, closed)


class _ZeroHeuristic:
    """Bọc bài toán với h(n) = 0  ->  A* trở thành UCS (Dijkstra)."""

    def __init__(self, problem):
        self.problem = problem

    def neighbors(self, n):
        return self.problem.neighbors(n)

    def heuristic(self, a, b):
        return 0.0


def ucs(problem, start, goal):
    """Tìm kiếm chi phí đồng nhất = A* với h(n) = 0."""
    return astar(_ZeroHeuristic(problem), start, goal)


def greedy(problem, start, goal):
    """Tham lam tốt nhất đầu tiên: chỉ dùng f(n) = h(n)."""
    t0 = time.perf_counter()
    counter = itertools.count()
    heap = [(problem.heuristic(start, goal), next(counter), start)]
    parent, g, closed = {start: None}, {start: 0.0}, set()
    expanded, generated, max_frontier = 0, 1, 1
    while heap:
        _, _, node = heapq.heappop(heap)
        if node in closed:
            continue
        if node == goal:
            return _done(True, parent, g, goal, expanded, generated, max_frontier, t0, closed)
        closed.add(node)
        expanded += 1
        for nxt, cost in problem.neighbors(node):
            if nxt in parent:                     # đã gặp rồi thì không cập nhật lại
                continue
            parent[nxt] = node
            g[nxt] = g[node] + cost
            heapq.heappush(heap, (problem.heuristic(nxt, goal), next(counter), nxt))
            generated += 1
        max_frontier = max(max_frontier, len(heap))
    return _done(False, parent, g, goal, expanded, generated, max_frontier, t0, closed)


ALGORITHMS = {"BFS": bfs, "DFS": dfs, "UCS": ucs, "Greedy": greedy, "A*": astar}
