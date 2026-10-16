"""
Thuật toán A* tổng quát cho bài toán tìm kiếm trong không gian trạng thái.

A* không cần biết bài toán là mê cung hay bản đồ. Nó chỉ cần một đối tượng
"problem" cung cấp hai phương thức:

    problem.neighbors(state)   -> lặp ra các cặp (trạng_thái_kế_tiếp, chi_phí)
    problem.heuristic(a, b)    -> ước lượng chi phí còn lại h(n) từ a đến b

Hàm đánh giá:   f(n) = g(n) + h(n)
    g(n): chi phí thực đã đi từ trạng thái đầu đến n
    h(n): ước lượng chi phí từ n đến đích (heuristic)

Nếu h(n) chấp nhận được (không bao giờ đánh giá quá chi phí thật) và nhất quán
(h(a) <= c(a, b) + h(b)), A* dạng tìm kiếm trên đồ thị (có tập CLOSED) luôn trả
về đường đi có chi phí nhỏ nhất.
"""

import heapq
import itertools
import math
import time
from dataclasses import dataclass, field


@dataclass
class SearchResult:
    found: bool                 # có tìm thấy đường hay không
    path: list                  # danh sách trạng thái từ đầu đến đích
    cost: float                 # tổng chi phí đường đi
    expanded: int               # số nút đã mở rộng (đưa vào CLOSED)
    generated: int              # số lần đưa nút vào OPEN
    max_frontier: int           # kích thước lớn nhất của hàng đợi OPEN
    time_ms: float = 0.0        # thời gian tính toán (mili giây)
    g: dict = field(default_factory=dict, repr=False)       # g(n) của mọi nút đã gặp
    parent: dict = field(default_factory=dict, repr=False)  # cha của từng nút
    closed: set = field(default_factory=set, repr=False)    # tập nút đã mở rộng


def reconstruct_path(parent, goal):
    """Lần ngược theo con trỏ cha để dựng lại đường đi."""
    path = []
    node = goal
    while node is not None:
        path.append(node)
        node = parent[node]
    path.reverse()
    return path


def astar_steps(problem, start, goal):
    """
    A* dạng generator để phục vụ mô phỏng từng bước.

    Mỗi lần mở rộng một nút, generator trả ra (nút_vừa_mở_rộng, [các_nút_mới_vào_OPEN]).
    Khi kết thúc, kết quả SearchResult nằm trong StopIteration.value.
    """
    counter = itertools.count()          # phá thế hòa ổn định khi f và h bằng nhau
    h_start = problem.heuristic(start, goal)

    # Mỗi phần tử OPEN: (f, h, thứ_tự, trạng_thái).
    # Khi f bằng nhau, ưu tiên nút có h nhỏ hơn (gần đích hơn) để giảm số nút xét.
    open_heap = [(h_start, h_start, next(counter), start)]
    g = {start: 0.0}
    parent = {start: None}
    closed = set()

    expanded = 0
    generated = 1
    max_frontier = 1

    while open_heap:
        _, _, _, node = heapq.heappop(open_heap)

        # Một nút có thể nằm trong OPEN nhiều lần (khi tìm được g tốt hơn).
        # Bản cũ hơn sẽ bị bỏ qua ở đây ("lazy deletion").
        if node in closed:
            continue

        # Kiểm tra đích khi LẤY RA khỏi OPEN (không phải khi sinh ra) -> đảm bảo tối ưu.
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
            if new_g < g.get(nxt, math.inf):          # tìm được đường tốt hơn đến nxt
                g[nxt] = new_g
                parent[nxt] = node
                h = problem.heuristic(nxt, goal)
                heapq.heappush(open_heap, (new_g + h, h, next(counter), nxt))
                generated += 1
                opened.append(nxt)

        if len(open_heap) > max_frontier:
            max_frontier = len(open_heap)

        yield node, opened

    # OPEN rỗng mà chưa gặp đích -> không có đường đi
    return SearchResult(False, [], math.inf, expanded, generated, max_frontier,
                        g=g, parent=parent, closed=closed)


def astar(problem, start, goal):
    """Chạy A* đến khi xong (không mô phỏng) và đo thời gian."""
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
