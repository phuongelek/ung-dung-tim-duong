"""Màu, font, nút bấm dùng chung."""

import pygame

C = {
    "bg": (244, 245, 248),
    "panel": (255, 255, 255),
    "border": (218, 222, 230),
    "text": (30, 34, 45),
    "muted": (112, 120, 138),
    "accent": (45, 98, 230),
    "accent_hover": (30, 80, 205),
    "button": (238, 241, 247),
    "button_hover": (225, 230, 240),
    "grid_line": (226, 229, 236),
    "empty": (255, 255, 255),
    "wall": (42, 47, 62),
    "start": (30, 165, 85),
    "goal": (222, 56, 56),
    "open": (176, 232, 196),
    "closed": (184, 207, 250),
    "current": (255, 145, 30),
    "path": (255, 200, 40),
    "path_line": (235, 110, 0),
    "map_bg": (236, 238, 232),
    "road_major": (255, 255, 255),
    "road_major_edge": (205, 196, 170),
    "road_mid": (252, 252, 250),
    "road_minor": (205, 208, 212),
    "explored": (70, 130, 240),
}

FONT_NAMES = "segoeui,arial,tahoma,dejavusans,notosans,liberationsans"
_font_cache = {}


def font(size, bold=False):
    key = (size, bold)
    if key not in _font_cache:
        _font_cache[key] = pygame.font.SysFont(FONT_NAMES, size, bold=bold)
    return _font_cache[key]


def draw_text(surf, text, pos, size=15, color=None, bold=False, anchor="topleft"):
    img = font(size, bold).render(str(text), True, color or C["text"])
    rect = img.get_rect(**{anchor: pos})
    surf.blit(img, rect)
    return rect


def wrap_text(text, size, max_width, bold=False):
    f = font(size, bold)
    lines, cur = [], ""
    for word in text.split(" "):
        trial = (cur + " " + word).strip()
        if f.size(trial)[0] <= max_width:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


class Button:
    def __init__(self, label, action, primary=False, height=32):
        self.label = label  # str hoặc hàm trả về str
        self.action = action
        self.primary = primary
        self.height = height
        self.rect = pygame.Rect(0, 0, 0, height)
        self.enabled = True

    def text(self):
        return self.label() if callable(self.label) else self.label

    def draw(self, surf):
        hover = self.enabled and self.rect.collidepoint(pygame.mouse.get_pos())
        if self.primary:
            bg = C["accent_hover"] if hover else C["accent"]
            fg = (255, 255, 255)
        else:
            bg = C["button_hover"] if hover else C["button"]
            fg = C["text"]
        if not self.enabled:
            bg, fg = C["button"], C["muted"]
        pygame.draw.rect(surf, bg, self.rect, border_radius=6)
        if not self.primary:
            pygame.draw.rect(surf, C["border"], self.rect, 1, border_radius=6)
        draw_text(surf, self.text(), self.rect.center, 14, fg,
                  bold=self.primary, anchor="center")

    def handle_event(self, event):
        if (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
                and self.enabled and self.rect.collidepoint(event.pos)):
            self.action()
            return True
        return False


def layout_buttons(buttons, x, y, width, gap=6, columns=1):
    col_w = (width - gap * (columns - 1)) // columns
    i = 0
    while i < len(buttons):
        row = buttons[i:i + columns]
        for j, b in enumerate(row):
            b.rect = pygame.Rect(x + j * (col_w + gap), y, col_w, b.height)
        y += row[0].height + gap
        i += columns
    return y


def draw_stat(surf, label, value, x, y, width, size=14):
    draw_text(surf, label, (x, y), size, C["muted"])
    draw_text(surf, value, (x + width, y), size, C["text"], bold=True, anchor="topright")
    return y + size + 8


def draw_legend_item(surf, color, label, x, y, round_=False):
    r = pygame.Rect(x, y + 2, 14, 14)
    if round_:
        pygame.draw.circle(surf, color, r.center, 7)
    else:
        pygame.draw.rect(surf, color, r, border_radius=3)
        pygame.draw.rect(surf, C["border"], r, 1, border_radius=3)
    draw_text(surf, label, (x + 20, y), 13, C["text"])


def format_number(n):
    return f"{n:,}".replace(",", ".")
