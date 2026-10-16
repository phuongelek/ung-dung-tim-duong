"""
Ứng dụng tìm đường trên bản đồ TP.HCM bằng thuật toán A*
(dữ liệu đường phố: OpenStreetMap).

Chạy:  python main.py
"""

import os
import sys

import pygame

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from ui.common import C  # noqa: E402
from ui.map_view import MapView  # noqa: E402

WIDTH, HEIGHT = 1240, 700
MAP_FILE = os.path.join(ROOT, "data", "hcm_map.json")


class App:
    def __init__(self):
        pygame.display.init()       # không cần âm thanh nên chỉ khởi tạo màn hình và phông chữ
        pygame.font.init()
        pygame.display.set_caption("Tìm đường bằng thuật toán A* – Bản đồ TP.HCM")
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()
        self.view = MapView(pygame.Rect(0, 0, WIDTH, HEIGHT), MAP_FILE)

    def frame(self):
        self.view.update()
        self.screen.fill(C["bg"])
        self.view.draw(self.screen)

    def run(self):
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    return
                self.view.handle_event(event)
            self.frame()
            pygame.display.flip()
            self.clock.tick(60)


if __name__ == "__main__":
    App().run()
    pygame.quit()
