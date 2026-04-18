
import math
import os
import random
import sys

import pygame


SCREEN_W = 1024
SCREEN_H = 640
TILE_SIZE = 32
FPS = 60

DIR_DOWN = 0
DIR_UP = 1
DIR_LEFT = 2
DIR_RIGHT = 3

ST_TITLE = "title"
ST_OVERWORLD = "overworld"
ST_MINIGAME = "minigame"
ST_ENDING = "ending"

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
DARK = (11, 10, 20)
TEXT_COL = (236, 231, 216)
ACCENT = (230, 188, 92)
GREEN = (78, 182, 96)
RED = (214, 82, 82)
SOAP_BLUE = (160, 205, 245)
SKY = (96, 164, 224)
MINT = (126, 208, 186)
PURPLE = (160, 104, 214)

ASSETS = os.path.join(os.path.dirname(__file__), "assets")

DEFAULT_SETTINGS = {
    "guided_mode": True,
    "input_assist": False,
    "reduce_motion": False,
    "large_text": False,
    "high_contrast": False,
    "instant_dialogue": False,
}

SETTINGS_INFO = [
    ("guided_mode", "Guided highlights", "Show arrows, glows, and objective markers."),
    ("input_assist", "Input assist", "Slows hazards and widens forgiving timing windows."),
    ("reduce_motion", "Reduce motion", "Calmer backgrounds, less pulsing, less drifting."),
    ("large_text", "Large text", "Makes dialogue and UI text easier to read."),
    ("high_contrast", "High contrast", "Boosts outlines and important gameplay zones."),
    ("instant_dialogue", "Instant dialogue", "Displays full dialogue lines immediately."),
]


# Small helper functions keep the game math readable everywhere else.
def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def calm_factor(anxiety):
    return clamp((100 - anxiety) / 88, 0.0, 1.0)


def load_img(name):
    return pygame.image.load(os.path.join(ASSETS, name)).convert_alpha()


def draw_box(surf, color, rect, radius=10):
    tmp = pygame.Surface((rect[2], rect[3]), pygame.SRCALPHA)
    pygame.draw.rect(tmp, color, (0, 0, rect[2], rect[3]), border_radius=radius)
    surf.blit(tmp, (rect[0], rect[1]))


def draw_glow_circle(surf, pos, radius, color, alpha=80):
    tmp = pygame.Surface((radius * 4, radius * 4), pygame.SRCALPHA)
    for i in range(3, 0, -1):
        r = radius + i * 10
        a = max(15, alpha // i)
        pygame.draw.circle(tmp, (*color, a), (radius * 2, radius * 2), r)
    surf.blit(tmp, (pos[0] - radius * 2, pos[1] - radius * 2))


def draw_vignette(surf, center, radius, alpha):
    overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
    overlay.fill((3, 2, 10, alpha))
    # Punch out a clearer center so the dark border feels focused instead of muddy.
    for ring_radius, ring_alpha in (
        (radius + 70, max(0, alpha - 34)),
        (radius + 28, max(0, alpha - 68)),
        (radius, 0),
    ):
        pygame.draw.circle(overlay, (3, 2, 10, ring_alpha), center, max(8, ring_radius))
    surf.blit(overlay, (0, 0))


def wrap(text, font, max_w):
    words = text.split()
    lines = []
    current = ""
    for word in words:
        test = (current + " " + word).strip()
        if font.size(test)[0] <= max_w:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


class AnimSprite:
    FW = 48
    FH = 48
    COLS = 4

    def __init__(self, sheet, scale=2.0):
        self.scale = scale
        self.frames = {}
        for row in range(4):
            row_frames = []
            for col in range(self.COLS):
                # Slice one frame out of the sprite sheet, then upscale it once.
                raw = sheet.subsurface(pygame.Rect(col * self.FW, row * self.FH, self.FW, self.FH)).copy()
                row_frames.append(
                    pygame.transform.scale(raw, (int(self.FW * scale), int(self.FH * scale)))
                )
            self.frames[row] = row_frames
        self.dir = DIR_DOWN
        self.frame = 0
        self.timer = 0
        self.moving = False
        self.spd = 140

    def update(self, dt):
        if self.moving:
            self.timer += dt
            if self.timer >= self.spd:
                self.timer = 0
                self.frame = (self.frame + 1) % self.COLS
        else:
            self.frame = 0
            self.timer = 0

    def get(self):
        return self.frames[self.dir][self.frame]

    @property
    def w(self):
        return int(self.FW * self.scale)

    @property
    def h(self):
        return int(self.FH * self.scale)


class Player:
    SPD = 155

    def __init__(self, sheet, x, y):
        self.anim = AnimSprite(sheet)
        self.x = float(x)
        self.y = float(y)

    @property
    def rect(self):
        return pygame.Rect(
            int(self.x - self.anim.w // 2),
            int(self.y - self.anim.h // 2),
            self.anim.w,
            self.anim.h,
        )

    def move(self, dx, dy, dt, walls):
        if dx == 0 and dy == 0:
            self.anim.moving = False
            return
        self.anim.moving = True
        if abs(dx) >= abs(dy):
            self.anim.dir = DIR_RIGHT if dx > 0 else DIR_LEFT
        else:
            self.anim.dir = DIR_DOWN if dy > 0 else DIR_UP
        mag = math.hypot(dx, dy)
        nx = dx / mag
        ny = dy / mag
        step = self.SPD * dt / 1000

        # Move on each axis separately so the player can slide along walls.
        nx_p = self.x + nx * step
        test = pygame.Rect(int(nx_p - self.anim.w // 2), int(self.y - self.anim.h // 2), self.anim.w, self.anim.h)
        if not any(test.colliderect(w) for w in walls):
            self.x = nx_p

        ny_p = self.y + ny * step
        test = pygame.Rect(int(self.x - self.anim.w // 2), int(ny_p - self.anim.h // 2), self.anim.w, self.anim.h)
        if not any(test.colliderect(w) for w in walls):
            self.y = ny_p

    def update(self, dt):
        self.anim.update(dt)

    def draw(self, surf, cx, cy):
        surf.blit(self.anim.get(), (int(self.x - cx - self.anim.w // 2), int(self.y - cy - self.anim.h // 2)))


class NPC:
    def __init__(self, name, x, y, body_col, head_col=None, size=56):
        self.name = name
        self.x = x
        self.y = y
        self.col = body_col
        self.hcol = head_col or body_col
        self.size = size
        self.bob = 0.0

    @property
    def rect(self):
        return pygame.Rect(self.x - self.size // 2, self.y - self.size // 2, self.size, self.size)

    @property
    def talk_rect(self):
        box = self.rect.copy()
        # Talking areas are bigger than the sprite so interactions feel forgiving.
        box.inflate_ip(55, 55)
        return box

    @property
    def draw_layer(self):
        return self.rect.bottom

    def update(self, dt, reduced_motion=False):
        rate = 0.0012 if reduced_motion else 0.0018
        amp = 2 if reduced_motion else 4
        self.bob = math.sin(pygame.time.get_ticks() * rate) * amp

    def draw(self, surf, cx, cy, font, highlight=False):
        sx = self.x - cx - self.size // 2
        sy = self.y - cy - self.size // 2 + int(self.bob)
        size = self.size
        if highlight:
            draw_glow_circle(surf, (sx + size // 2, sy + size // 2), 26, ACCENT, 100)
            arrow_y = sy - 28 + int(math.sin(pygame.time.get_ticks() * 0.008) * 4)
            pygame.draw.polygon(
                surf,
                ACCENT,
                [(sx + size // 2, arrow_y), (sx + size // 2 - 10, arrow_y - 18), (sx + size // 2 + 10, arrow_y - 18)],
            )
        pygame.draw.ellipse(surf, self.col, (sx + 8, sy + 20, size - 16, size - 20))
        pygame.draw.circle(surf, self.hcol, (sx + size // 2, sy + 12), 14)
        pygame.draw.circle(surf, DARK, (sx + size // 2 - 5, sy + 10), 2)
        pygame.draw.circle(surf, DARK, (sx + size // 2 + 5, sy + 10), 2)
        lbl = font.render(self.name, True, TEXT_COL)
        surf.blit(lbl, (sx + size // 2 - lbl.get_width() // 2, sy - 22))


class Obj:
    def __init__(self, name, x, y, w, h, style, color=(160, 130, 90), interactable=True, solid=True):
        self.name = name
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.style = style
        self.color = color
        self.interactable = interactable
        self.solid = solid
        self.pulse = random.uniform(0, math.pi * 2)

    @property
    def rect(self):
        return pygame.Rect(self.x, self.y, self.w, self.h)

    @property
    def near_rect(self):
        box = self.rect.copy()
        # Objects also get a generous interaction halo for easier play.
        box.inflate_ip(56, 56)
        return box

    @property
    def draw_layer(self):
        return self.y + self.h

    @property
    def collision_rect(self):
        if not self.solid:
            return None
        # Smaller footprints make tall props feel solid without turning wall decor
        # into giant invisible boxes.
        footprint = {
            "sink": pygame.Rect(self.x + 8, self.y + self.h - 26, self.w - 16, 22),
            "fridge": pygame.Rect(self.x + 6, self.y + self.h - 24, self.w - 12, 22),
            "table": pygame.Rect(self.x + 12, self.y + self.h - 26, self.w - 24, 26),
            "bed": pygame.Rect(self.x + 10, self.y + self.h - 26, self.w - 20, 24),
            "mirror": pygame.Rect(self.x + 8, self.y + self.h - 18, self.w - 16, 14),
            "plant": pygame.Rect(self.x + self.w // 2 - 14, self.y + self.h - 22, 28, 18),
            "bookshelf": pygame.Rect(self.x + 5, self.y + self.h - 22, self.w - 10, 20),
            "couch": pygame.Rect(self.x + 8, self.y + self.h - 24, self.w - 16, 22),
            "desk": pygame.Rect(self.x + 10, self.y + self.h - 24, self.w - 20, 22),
            "lamp": pygame.Rect(self.x + self.w // 2 - 12, self.y + self.h - 18, 24, 16),
            "door": pygame.Rect(self.x + 8, self.y + self.h - 14, self.w - 16, 12),
        }
        return footprint.get(self.style, self.rect.inflate(-12, -12))

    def update(self, dt, reduced_motion=False):
        mult = 0.0012 if reduced_motion else 0.0032
        self.pulse = (self.pulse + dt * mult) % (math.pi * 2)

    def _draw_shadow(self, surf, rx, ry):
        shadow = pygame.Surface((self.w + 24, 24), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0, 0, 0, 76), (0, 4, self.w + 24, 16))
        surf.blit(shadow, (rx - 12, ry + self.h - 14))

    def _draw_door(self, surf, rx, ry):
        pygame.draw.rect(surf, (118, 82, 52), (rx, ry, self.w, self.h), border_radius=4)
        pygame.draw.rect(surf, (165, 125, 74), (rx + 8, ry + 8, self.w - 16, self.h - 12), border_radius=4)
        pygame.draw.circle(surf, ACCENT, (rx + self.w - 12, ry + self.h // 2), 4)

    def _draw_sink(self, surf, rx, ry):
        pygame.draw.rect(surf, (210, 225, 235), (rx, ry + 8, self.w, self.h - 8), border_radius=8)
        pygame.draw.rect(surf, (155, 190, 212), (rx + 8, ry + 14, self.w - 16, self.h - 20), border_radius=8)
        pygame.draw.rect(surf, (132, 154, 176), (rx + 4, ry + self.h - 18, self.w - 8, 12), border_radius=6)
        pygame.draw.rect(surf, (150, 150, 160), (rx + self.w // 2 - 10, ry, 20, 12), border_radius=4)
        pygame.draw.arc(surf, WHITE, (rx + self.w // 2 - 12, ry - 6, 24, 24), math.pi, math.pi * 2, 3)

    def _draw_fridge(self, surf, rx, ry):
        pygame.draw.rect(surf, (205, 214, 220), (rx, ry, self.w, self.h), border_radius=6)
        pygame.draw.line(surf, (165, 175, 180), (rx, ry + self.h // 2), (rx + self.w, ry + self.h // 2), 2)
        pygame.draw.rect(surf, (172, 182, 188), (rx + 4, ry + self.h - 18, self.w - 8, 12), border_radius=5)
        pygame.draw.rect(surf, (150, 160, 170), (rx + self.w - 10, ry + 12, 4, 18), border_radius=2)
        pygame.draw.rect(surf, (150, 160, 170), (rx + self.w - 10, ry + self.h // 2 + 10, 4, 18), border_radius=2)

    def _draw_table(self, surf, rx, ry):
        pygame.draw.rect(surf, (163, 112, 70), (rx, ry + 10, self.w, self.h - 16), border_radius=8)
        pygame.draw.rect(surf, (194, 146, 95), (rx + 6, ry, self.w - 12, 16), border_radius=8)
        pygame.draw.rect(surf, (126, 84, 52), (rx + 4, ry + self.h - 18, self.w - 8, 12), border_radius=6)
        for lx in (10, self.w - 18):
            pygame.draw.rect(surf, (108, 76, 52), (rx + lx, ry + self.h - 8, 8, 20), border_radius=2)

    def _draw_bed(self, surf, rx, ry):
        pygame.draw.rect(surf, (150, 116, 90), (rx, ry + self.h - 12, self.w, 12))
        pygame.draw.rect(surf, (183, 140, 198), (rx + 6, ry + 14, self.w - 12, self.h - 20), border_radius=8)
        pygame.draw.rect(surf, (132, 94, 120), (rx + 6, ry + self.h - 22, self.w - 12, 10), border_radius=5)
        pygame.draw.rect(surf, (238, 225, 230), (rx + 8, ry + 6, 24, 18), border_radius=5)
        pygame.draw.rect(surf, (238, 225, 230), (rx + self.w - 32, ry + 6, 24, 18), border_radius=5)

    def _draw_mirror(self, surf, rx, ry):
        pygame.draw.rect(surf, (122, 88, 60), (rx, ry, self.w, self.h), border_radius=6)
        pygame.draw.rect(surf, (195, 225, 244), (rx + 6, ry + 6, self.w - 12, self.h - 12), border_radius=6)

    def _draw_plant(self, surf, rx, ry):
        pygame.draw.ellipse(surf, (108, 70, 48), (rx + self.w // 2 - 14, ry + self.h - 18, 28, 18))
        pygame.draw.rect(surf, (108, 70, 48), (rx + self.w // 2 - 12, ry + self.h - 20, 24, 10), border_radius=4)
        for angle in (-40, -15, 10, 35):
            length = 22
            ex = rx + self.w // 2 + int(math.cos(math.radians(angle)) * length)
            ey = ry + self.h // 2 + int(math.sin(math.radians(angle)) * length)
            pygame.draw.line(surf, (48, 140, 82), (rx + self.w // 2, ry + self.h - 18), (ex, ey), 4)
            pygame.draw.circle(surf, (70, 180, 110), (ex, ey), 8)

    def _draw_bookshelf(self, surf, rx, ry):
        pygame.draw.rect(surf, (125, 92, 62), (rx, ry, self.w, self.h), border_radius=4)
        pygame.draw.rect(surf, (94, 68, 46), (rx + 2, ry + self.h - 16, self.w - 4, 10), border_radius=4)
        for i in range(1, 3):
            yy = ry + i * self.h // 3
            pygame.draw.line(surf, (87, 60, 38), (rx + 4, yy), (rx + self.w - 4, yy), 3)
        for col in range(4):
            for row in range(3):
                bx = rx + 6 + col * 12
                by = ry + 6 + row * self.h // 3
                pygame.draw.rect(
                    surf,
                    random.choice([(190, 92, 92), (80, 140, 200), (205, 180, 84), (90, 170, 120)]),
                    (bx, by, 8, 18),
                    border_radius=2,
                )

    def _draw_couch(self, surf, rx, ry):
        pygame.draw.rect(surf, (150, 170, 198), (rx, ry + 18, self.w, self.h - 18), border_radius=8)
        pygame.draw.rect(surf, (192, 204, 220), (rx + 10, ry, self.w - 20, 24), border_radius=8)
        pygame.draw.rect(surf, (108, 126, 154), (rx + 8, ry + self.h - 20, self.w - 16, 12), border_radius=6)
        pygame.draw.rect(surf, (132, 150, 175), (rx + 8, ry + 20, 18, self.h - 16), border_radius=6)
        pygame.draw.rect(surf, (132, 150, 175), (rx + self.w - 26, ry + 20, 18, self.h - 16), border_radius=6)

    def _draw_desk(self, surf, rx, ry):
        pygame.draw.rect(surf, (131, 96, 65), (rx, ry + 10, self.w, 18), border_radius=5)
        pygame.draw.rect(surf, (112, 78, 54), (rx + 8, ry + 28, self.w - 16, self.h - 20), border_radius=5)
        pygame.draw.rect(surf, (84, 58, 40), (rx + 8, ry + self.h - 18, self.w - 16, 10), border_radius=5)
        pygame.draw.rect(surf, (75, 90, 105), (rx + self.w // 2 - 18, ry - 10, 36, 20), border_radius=3)
        pygame.draw.rect(surf, (145, 220, 250), (rx + self.w // 2 - 14, ry - 7, 28, 14), border_radius=2)

    def _draw_rug(self, surf, rx, ry):
        pygame.draw.rect(surf, (205, 175, 85), (rx, ry, self.w, self.h), border_radius=10)
        pygame.draw.rect(surf, (80, 100, 180), (rx + 8, ry + 8, self.w - 16, self.h - 16), border_radius=8)
        pygame.draw.rect(surf, (205, 175, 85), (rx + 18, ry + 18, self.w - 36, self.h - 36), border_radius=6)

    def _draw_lamp(self, surf, rx, ry):
        pygame.draw.rect(surf, (145, 130, 118), (rx + self.w // 2 - 3, ry + 10, 6, self.h - 18))
        pygame.draw.rect(surf, (108, 94, 82), (rx + self.w // 2 - 11, ry + self.h - 12, 22, 10), border_radius=3)
        pygame.draw.polygon(
            surf,
            (235, 220, 175),
            [(rx + self.w // 2, ry), (rx + self.w // 2 - 18, ry + 20), (rx + self.w // 2 + 18, ry + 20)],
        )

    def draw(self, surf, cx, cy, font, highlight=False, prompt=False):
        rx = self.x - cx
        ry = self.y - cy
        self._draw_shadow(surf, rx, ry)
        if highlight:
            glow_alpha = 40 + int(25 * (1 + math.sin(self.pulse * 2.5)))
            draw_box(surf, (*ACCENT, glow_alpha), (rx - 10, ry - 10, self.w + 20, self.h + 20), 16)
        # Each object style draws itself like a tiny custom sprite.
        if self.style == "door":
            self._draw_door(surf, rx, ry)
        elif self.style == "sink":
            self._draw_sink(surf, rx, ry)
        elif self.style == "fridge":
            self._draw_fridge(surf, rx, ry)
        elif self.style == "table":
            self._draw_table(surf, rx, ry)
        elif self.style == "bed":
            self._draw_bed(surf, rx, ry)
        elif self.style == "mirror":
            self._draw_mirror(surf, rx, ry)
        elif self.style == "plant":
            self._draw_plant(surf, rx, ry)
        elif self.style == "bookshelf":
            self._draw_bookshelf(surf, rx, ry)
        elif self.style == "couch":
            self._draw_couch(surf, rx, ry)
        elif self.style == "desk":
            self._draw_desk(surf, rx, ry)
        elif self.style == "rug":
            self._draw_rug(surf, rx, ry)
        elif self.style == "lamp":
            self._draw_lamp(surf, rx, ry)
        else:
            pygame.draw.rect(surf, self.color, (rx, ry, self.w, self.h), border_radius=8)
        if self.interactable:
            label = font.render(self.name, True, ACCENT)
            surf.blit(label, (rx + self.w // 2 - label.get_width() // 2, ry - 22))
            if prompt:
                prompt_lbl = font.render("[E] interact", True, WHITE)
                draw_box(
                    surf,
                    (0, 0, 0, 170),
                    (rx + self.w // 2 - prompt_lbl.get_width() // 2 - 5, ry - 46, prompt_lbl.get_width() + 10, 22),
                    5,
                )
                surf.blit(prompt_lbl, (rx + self.w // 2 - prompt_lbl.get_width() // 2, ry - 44))


class DialogueBox:
    def __init__(self, fb, fs, settings):
        self.fb = fb
        self.fs = fs
        self.settings = settings
        self.active = False
        self.lines = []
        self.source_lines = []
        self.idx = 0
        self.ci = 0
        self.timer = 0
        self.spd = 28
        self.on_done = None

    def refresh_fonts(self, fb, fs):
        # Re-wrap text after a font size change so pages still fit.
        self.fb = fb
        self.fs = fs
        if self.source_lines:
            self.lines = self._paginate_lines(self.source_lines)
            if self.lines:
                self.idx = clamp(self.idx, 0, len(self.lines) - 1)
                self.ci = min(self.ci, len(self.lines[self.idx]["text"]))

    def _paginate_lines(self, lines):
        max_w = SCREEN_W - 116
        max_lines = 3 if self.settings["large_text"] else 4
        paged = []
        for line in lines:
            wrapped = wrap(line["text"], self.fb, max_w) or [""]
            # Split long dialogue into readable pages so it always stays in the box.
            for start in range(0, len(wrapped), max_lines):
                paged.append({"speaker": line.get("speaker", ""), "text": " ".join(wrapped[start : start + max_lines])})
        return paged

    def start(self, lines, on_complete=None):
        # Keep the original lines around so they can be re-paginated later.
        self.source_lines = [dict(line) for line in lines]
        self.lines = self._paginate_lines(self.source_lines)
        self.idx = 0
        self.ci = len(self.lines[0]["text"]) if self.settings["instant_dialogue"] else 0
        self.timer = 0
        self.on_done = on_complete
        self.active = True

    def advance(self):
        if not self.active:
            return
        full = self.lines[self.idx]["text"]
        # First press finishes the current line, next press moves to the next page.
        if self.ci < len(full):
            self.ci = len(full)
        else:
            self.idx += 1
            self.timer = 0
            if self.idx >= len(self.lines):
                self.active = False
                if self.on_done:
                    cb = self.on_done
                    self.on_done = None
                    cb()
            else:
                next_text = self.lines[self.idx]["text"]
                self.ci = len(next_text) if self.settings["instant_dialogue"] else 0

    def update(self, dt):
        if not self.active or self.settings["instant_dialogue"]:
            if self.active:
                self.ci = len(self.lines[self.idx]["text"])
            return
        full = self.lines[self.idx]["text"]
        if self.ci < len(full):
            self.timer += dt
            add = int(self.timer / self.spd)
            if add:
                self.timer -= add * self.spd
                self.ci = min(self.ci + add, len(full))

    def draw(self, surf):
        if not self.active:
            return
        bw = SCREEN_W - 60
        bh = 224 if self.settings["large_text"] else 206
        bx = 30
        by = SCREEN_H - bh - 18
        draw_box(surf, (12, 10, 28, 228), (bx, by, bw, bh), 14)
        pygame.draw.rect(surf, ACCENT, (bx, by, bw, bh), 2, border_radius=14)
        line = self.lines[self.idx]
        speaker = line.get("speaker", "")
        text = line["text"][: self.ci]
        if speaker:
            speaker_lbl = self.fs.render(speaker, True, ACCENT)
            surf.blit(speaker_lbl, (bx + 18, by + 12))
        max_lines = 3 if self.settings["large_text"] else 4
        for i, wrapped in enumerate(wrap(text, self.fb, bw - 40)[:max_lines]):
            tl = self.fb.render(wrapped, True, TEXT_COL)
            surf.blit(tl, (bx + 18, by + 48 + i * (self.fb.get_linesize() + 2)))
        if self.ci >= len(line["text"]) and int(pygame.time.get_ticks() / 450) % 2 == 0:
            hint = self.fb.render("ENTER to continue", True, ACCENT)
            surf.blit(hint, (bx + bw - hint.get_width() - 18, by + bh - hint.get_height() - 14))


class Camera:
    def __init__(self, w, h):
        self.w = w
        self.h = h
        self.x = 0.0
        self.y = 0.0

    def update(self, tx, ty):
        # Ease toward the player instead of snapping so movement feels softer.
        self.x += (tx - SCREEN_W / 2 - self.x) * 0.12
        self.y += (ty - SCREEN_H / 2 - self.y) * 0.12
        self.x = clamp(self.x, 0, max(0, self.w - SCREEN_W))
        self.y = clamp(self.y, 0, max(0, self.h - SCREEN_H))

    @property
    def xi(self):
        return int(self.x)

    @property
    def yi(self):
        return int(self.y)


class Fader:
    def __init__(self):
        self.alpha = 255.0
        self.dir = -1
        self.active = False
        self.speed = 460
        self.cb = None

    def fade_in(self):
        self.alpha = 255.0
        self.dir = -1
        self.active = True
        self.cb = None

    def fade_out(self, cb=None):
        # A callback lets room swaps happen exactly when the screen is fully black.
        self.alpha = 0.0
        self.dir = 1
        self.active = True
        self.cb = cb

    def update(self, dt):
        if not self.active:
            return
        delta = self.speed * dt / 1000
        if self.dir > 0:
            self.alpha = min(255.0, self.alpha + delta)
            if self.alpha >= 255.0:
                self.active = False
                if self.cb:
                    cb = self.cb
                    self.cb = None
                    cb()
        else:
            self.alpha = max(0.0, self.alpha - delta)
            if self.alpha <= 0:
                self.active = False

    def draw(self, surf):
        if self.alpha <= 0:
            return
        overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, int(self.alpha)))
        surf.blit(overlay, (0, 0))


class Room:
    def __init__(self, name, tw, th, floor_col, wall_col, accent):
        self.name = name
        self.tw = tw
        self.th = th
        self.fc = floor_col
        self.wc = wall_col
        self.accent = accent
        self.objects = []
        self.npcs = []
        width = tw * TILE_SIZE
        height = th * TILE_SIZE
        thick = TILE_SIZE
        self.walls = [
            pygame.Rect(0, 0, width, thick),
            pygame.Rect(0, height - thick, width, thick),
            pygame.Rect(0, 0, thick, height),
            pygame.Rect(width - thick, 0, thick, height),
        ]

    @property
    def collision_rects(self):
        # The room combines map borders with object footprints into one collision list.
        rects = list(self.walls)
        rects.extend(obj.collision_rect for obj in self.objects if obj.collision_rect)
        return rects

    @property
    def pw(self):
        return self.tw * TILE_SIZE

    @property
    def ph(self):
        return self.th * TILE_SIZE

    def find_target(self, name):
        for obj in self.objects:
            if obj.name == name:
                return obj
        for npc in self.npcs:
            if npc.name == name:
                return npc
        return None

    def draw(self, surf, cx, cy, font, player_rect, highlight_target=None, draw_entities=True):
        # The checker pattern gives flat rooms a little texture without extra art assets.
        dark = tuple(max(0, c - 20) for c in self.fc)
        for tx in range(self.tw):
            for ty in range(self.th):
                col = dark if (tx + ty) % 2 == 0 else self.fc
                pygame.draw.rect(surf, col, (tx * TILE_SIZE - cx, ty * TILE_SIZE - cy, TILE_SIZE, TILE_SIZE))
        for gy in range(0, self.th * TILE_SIZE, 96):
            pygame.draw.line(surf, (*self.accent, 36), (0 - cx, gy - cy), (self.tw * TILE_SIZE - cx, gy - cy), 1)
        for wall in self.walls:
            rect = wall.move(-cx, -cy)
            pygame.draw.rect(surf, self.wc, rect)
            pygame.draw.rect(surf, tuple(min(255, c + 35) for c in self.wc), rect, 2)
        if not draw_entities:
            return

        for obj in self.objects:
            nearby = obj.interactable and obj.near_rect.colliderect(player_rect)
            obj.draw(surf, cx, cy, font, highlight=(obj.name == highlight_target), prompt=nearby)
        for npc in self.npcs:
            nearby = npc.talk_rect.colliderect(player_rect)
            npc.draw(surf, cx, cy, font, highlight=(npc.name == highlight_target))
            if nearby:
                lbl = font.render("[E] talk", True, ACCENT)
                sx = npc.x - cx - lbl.get_width() // 2
                sy = npc.y - cy - npc.size // 2 - 38
                draw_box(surf, (0, 0, 0, 165), (sx - 4, sy - 2, lbl.get_width() + 8, lbl.get_height() + 4), 4)
                surf.blit(lbl, (sx, sy))


class SettingsOverlay:
    def __init__(self, game):
        self.game = game
        self.open = False
        self.button_rect = pygame.Rect(SCREEN_W - 74, 16, 54, 36)

    def toggle(self):
        self.open = not self.open

    def handle_event(self, ev):
        # Returning True tells the main loop "the menu already handled this input".
        if ev.type == pygame.KEYDOWN and ev.key == pygame.K_TAB:
            self.toggle()
            return True
        if ev.type == pygame.MOUSEBUTTONDOWN and self.button_rect.collidepoint(ev.pos):
            self.toggle()
            return True
        if not self.open:
            return False
        if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
            self.open = False
            return True
        if ev.type == pygame.KEYDOWN and pygame.K_1 <= ev.key <= pygame.K_6:
            idx = ev.key - pygame.K_1
            if idx < len(SETTINGS_INFO):
                self.game.toggle_setting(SETTINGS_INFO[idx][0])
            return True
        if ev.type == pygame.MOUSEBUTTONDOWN:
            panel = self._panel_rect()
            if not panel.collidepoint(ev.pos):
                self.open = False
                return True
            for idx, (key, _, _) in enumerate(SETTINGS_INFO):
                row = self._option_rect(idx)
                if row.collidepoint(ev.pos):
                    self.game.toggle_setting(key)
                    return True
        return self.open

    def _panel_rect(self):
        return pygame.Rect(168, 86, SCREEN_W - 336, SCREEN_H - 172)

    def _option_rect(self, idx):
        panel = self._panel_rect()
        return pygame.Rect(panel.x + 30, panel.y + 88 + idx * 58, panel.w - 60, 46)

    def draw_button(self, surf, font):
        draw_box(surf, (18, 18, 32, 210), self.button_rect, 10)
        pygame.draw.rect(surf, ACCENT, self.button_rect, 2, border_radius=10)
        cx = self.button_rect.centerx
        cy = self.button_rect.centery
        pygame.draw.circle(surf, ACCENT, (cx, cy), 8, 2)
        for ang in range(0, 360, 45):
            ex = cx + int(math.cos(math.radians(ang)) * 14)
            ey = cy + int(math.sin(math.radians(ang)) * 14)
            pygame.draw.line(surf, ACCENT, (cx, cy), (ex, ey), 2)
        lbl = font.render("TAB", True, TEXT_COL)
        surf.blit(lbl, (self.button_rect.x - lbl.get_width() - 8, self.button_rect.y + 9))

    def draw(self, surf, ft, fb):
        if not self.open:
            return
        veil = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        veil.fill((5, 5, 10, 160))
        surf.blit(veil, (0, 0))
        panel = self._panel_rect()
        draw_box(surf, (16, 14, 28, 245), panel, 18)
        pygame.draw.rect(surf, ACCENT, panel, 2, border_radius=18)
        title = ft.render("Settings & Accessibility", True, ACCENT)
        surf.blit(title, (panel.x + 28, panel.y + 22))
        subtitle = fb.render("Click options or press 1-6 while this menu is open.", True, TEXT_COL)
        surf.blit(subtitle, (panel.x + 30, panel.y + 58))
        for idx, (key, title_txt, desc) in enumerate(SETTINGS_INFO):
            row = self._option_rect(idx)
            active = self.game.settings[key]
            fill = (40, 88, 65, 205) if active else (40, 34, 56, 205)
            draw_box(surf, fill, row, 12)
            pygame.draw.rect(surf, ACCENT if active else (105, 100, 130), row, 2, border_radius=12)
            badge = fb.render(str(idx + 1), True, ACCENT)
            surf.blit(badge, (row.x + 12, row.y + 12))
            toggle = pygame.Rect(row.right - 72, row.y + 8, 52, 28)
            draw_box(surf, (12, 12, 18, 220), toggle, 14)
            knob_x = toggle.x + 14 if not active else toggle.right - 14
            pygame.draw.circle(surf, GREEN if active else TEXT_COL, (knob_x, toggle.centery), 10)
            title_lbl = fb.render(title_txt, True, WHITE)
            surf.blit(title_lbl, (row.x + 42, row.y + 8))
            desc_lbl = self.game.fsm.render(desc, True, (194, 191, 214))
            surf.blit(desc_lbl, (row.x + 42, row.y + 26))


class Particle:
    def __init__(self, x, y, col):
        self.x = float(x)
        self.y = float(y)
        self.vx = random.uniform(-0.4, 0.4)
        self.vy = random.uniform(-1.2, -0.4)
        self.col = col
        self.age = 0
        self.lt = random.randint(900, 1400)
        self.r = random.randint(3, 6)

    def update(self, dt):
        self.x += self.vx * dt * 0.055
        self.y += self.vy * dt * 0.055
        self.age += dt

    def dead(self):
        return self.age >= self.lt

    def draw(self, surf, cx, cy):
        # Draw on a temporary alpha surface so particles can fade smoothly.
        alpha = max(0, 255 - int(255 * self.age / self.lt))
        radius = max(1, int(self.r * (1 - self.age / self.lt * 0.5)))
        tmp = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
        pygame.draw.circle(tmp, (*self.col, alpha), (radius, radius), radius)
        surf.blit(tmp, (int(self.x - cx - radius), int(self.y - cy - radius)))


class MinigameFlowMixin:
    # Every minigame reuses the same "instructions -> countdown -> GO" flow.
    def _init_flow(self, title, instructions, countdown=3):
        self.flow_title = title
        self.flow_instructions = instructions
        self.flow_count = countdown
        self.flow_state = "instructions"
        self.flow_timer = 0
        self.flow_value = countdown

    def _flow_accepts_input(self):
        return self.flow_state == "active"

    def _handle_flow_event(self, ev):
        if self.done:
            return True
        if self.flow_state == "instructions" and ev.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
            self.flow_state = "countdown"
            self.flow_timer = 0
            self.flow_value = self.flow_count
            return True
        return self.flow_state != "active"

    def _update_flow(self, dt):
        if self.flow_state == "instructions":
            return False
        if self.flow_state == "countdown":
            self.flow_timer += dt
            if self.flow_timer >= 1000:
                self.flow_timer -= 1000
                self.flow_value -= 1
                if self.flow_value <= 0:
                    self.flow_state = "go"
                    self.flow_timer = 300
            return False
        if self.flow_state == "go":
            self.flow_timer -= dt
            if self.flow_timer <= 0:
                self.flow_state = "active"
            return False
        return True

    def draw_flow_overlay(self, surf):
        if self.flow_state == "active":
            return
        veil = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        veil.fill((4, 4, 10, 170))
        surf.blit(veil, (0, 0))
        if self.flow_state == "instructions":
            panel = pygame.Rect(122, 110, SCREEN_W - 244, SCREEN_H - 220)
            draw_box(surf, (14, 14, 26, 242), panel, 20)
            pygame.draw.rect(surf, ACCENT, panel, 2, border_radius=20)
            title = self.ft.render(self.flow_title, True, ACCENT)
            surf.blit(title, (SCREEN_W // 2 - title.get_width() // 2, panel.y + 24))
            for idx, line in enumerate(self.flow_instructions):
                label = self.fb.render(line, True, TEXT_COL)
                surf.blit(label, (panel.x + 34, panel.y + 88 + idx * 34))
            prompt = self.fb.render("Press any key or click to start the countdown.", True, WHITE)
            surf.blit(prompt, (SCREEN_W // 2 - prompt.get_width() // 2, panel.bottom - 46))
        else:
            label = "GO" if self.flow_state == "go" else str(self.flow_value)
            text = self.ft.render(label, True, WHITE)
            glow = pygame.Surface((text.get_width() + 60, text.get_height() + 60), pygame.SRCALPHA)
            pygame.draw.circle(glow, (*ACCENT, 60), (glow.get_width() // 2, glow.get_height() // 2), glow.get_width() // 2 - 6)
            surf.blit(glow, (SCREEN_W // 2 - glow.get_width() // 2, SCREEN_H // 2 - glow.get_height() // 2))
            surf.blit(text, (SCREEN_W // 2 - text.get_width() // 2, SCREEN_H // 2 - text.get_height() // 2))


class WashMinigame(MinigameFlowMixin):
    def __init__(self, fb, ft, settings, variant, stage, anxiety=100):
        self.fb = fb
        self.ft = ft
        self.settings = settings
        self.variant = variant
        self.stage = stage
        self.calm = calm_factor(anxiety)
        self.done = False
        self.success = False
        self.tick = 0
        self.cursor = [SCREEN_W // 2, SCREEN_H // 2]
        self.score = 0
        self.combo = 0
        self.floaters = []
        self.spawn_t = 0
        self.progress = 0
        self.target = max(6, 10 + stage * 2 - int(self.calm * 4))
        self.clean_spots = []
        self.flash = 0
        self.hand_points = [
            (SCREEN_W // 2 - 180, SCREEN_H // 2 + 20),
            (SCREEN_W // 2 - 50, SCREEN_H // 2 + 15),
            (SCREEN_W // 2 + 45, SCREEN_H // 2 + 18),
            (SCREEN_W // 2 + 176, SCREEN_H // 2 + 22),
        ]
        # One class powers three washing minigames; the variant picks the rules.
        intro = {
            "pop": [
                "Pop the blue soap bubbles.",
                "Leave the green germ bubbles alone.",
                "Mouse click or SPACE lets you pop quickly.",
            ],
            "scrub": [
                "Move the sponge over every dirty patch.",
                "Keep brushing until each mark disappears.",
                "Mouse or movement keys both steer the sponge.",
            ],
            "rhythm": [
                "Watch each lane and wait for the ring.",
                "Press the matching arrow right on the target.",
                "Missing is okay. Reset and catch the next note.",
            ],
        }
        self._init_flow("Wash Up", intro[variant])
        if variant == "scrub":
            self.target = max(6, 10 + stage * 2 - int(self.calm * 4))
            for _ in range(self.target):
                anchor = random.choice(self.hand_points)
                self.clean_spots.append(
                    {
                        "x": anchor[0] + random.randint(-35, 35),
                        "y": anchor[1] + random.randint(-45, 45),
                        "hp": 100,
                    }
                )
        elif variant == "rhythm":
            self._init_rhythm()

    def _assist_scale(self):
        return 0.8 if self.settings["input_assist"] else 1.0

    def _motion_scale(self):
        return 0.55 if self.settings["reduce_motion"] else 1.0

    def _spawn_pop_bubble(self):
        clean = random.random() > 0.22 - min(0.08, self.stage * 0.02) - self.calm * 0.08
        self.floaters.append(
            {
                "x": random.randint(60, SCREEN_W - 60),
                "y": SCREEN_H + 30,
                "vx": random.uniform(-16, 16),
                "vy": -random.uniform(70, 108 + self.stage * 10) * self._assist_scale() * (1.0 - self.calm * 0.12),
                "r": random.randint(22, 34),
                "clean": clean,
                "alive": True,
            }
        )

    def _init_rhythm(self):
        self.lanes = [
            {"keys": (pygame.K_d, pygame.K_LEFT), "label": "D", "col": PURPLE, "xf": 0.27},
            {"keys": (pygame.K_f, pygame.K_DOWN), "label": "F", "col": SKY, "xf": 0.42},
            {"keys": (pygame.K_j, pygame.K_UP), "label": "J", "col": GREEN, "xf": 0.57},
            {"keys": (pygame.K_k, pygame.K_RIGHT), "label": "K", "col": (255, 155, 85), "xf": 0.72},
        ]
        self.notes = []
        self.hit_f = {}
        self.miss_f = {}
        self.hit_y = 510
        # Anxiety and accessibility both tune the rhythm window and note speed.
        self.hit_win = (72 if self.settings["input_assist"] else 58) + int(self.calm * 12)
        self.note_spd = max(230, 320 + self.stage * 24 - int(self.calm * 70))
        self.spawn_gap = 740 - self.stage * 28 + int(self.calm * 120)
        self.target = max(8, 12 + self.stage * 2 - int(self.calm * 4))
        self.spawn_t = 0

    def refresh_fonts(self, fb, ft):
        self.fb = fb
        self.ft = ft

    def handle_event(self, ev):
        if self._handle_flow_event(ev):
            return
        if self.done:
            return
        if self.variant == "pop":
            self._handle_pop_event(ev)
        elif self.variant == "scrub":
            self._handle_scrub_event(ev)
        else:
            self._handle_rhythm_event(ev)

    def _handle_pop_event(self, ev):
        if ev.type == pygame.MOUSEMOTION:
            self.cursor[0], self.cursor[1] = ev.pos
        if ev.type == pygame.MOUSEBUTTONDOWN:
            self._pop_at(ev.pos)
        if ev.type == pygame.KEYDOWN and ev.key == pygame.K_SPACE:
            self._pop_nearest()

    def _pop_at(self, pos):
        picked = None
        best = 999999
        for bubble in self.floaters:
            if not bubble["alive"]:
                continue
            dist = math.hypot(pos[0] - bubble["x"], pos[1] - bubble["y"])
            if dist <= bubble["r"] and dist < best:
                picked = bubble
                best = dist
        if picked:
            self._resolve_pop(picked)

    def _pop_nearest(self):
        picked = None
        best = 100
        for bubble in self.floaters:
            if not bubble["alive"]:
                continue
            dist = math.hypot(self.cursor[0] - bubble["x"], self.cursor[1] - bubble["y"])
            if dist < best:
                picked = bubble
                best = dist
        if picked:
            self._resolve_pop(picked)

    def _resolve_pop(self, bubble):
        bubble["alive"] = False
        if bubble["clean"]:
            self.progress += 1
            self.combo += 1
            self.score += 90 + self.combo * 6
            self.flash = 180
        else:
            self.combo = 0
            self.progress = max(0, self.progress - 1)
            self.flash = -220

    def _handle_scrub_event(self, ev):
        if ev.type == pygame.MOUSEMOTION:
            self.cursor[0], self.cursor[1] = ev.pos

    def _handle_rhythm_event(self, ev):
        if ev.type != pygame.KEYDOWN:
            return
        for i, lane in enumerate(self.lanes):
            if ev.key in lane["keys"]:
                best = None
                best_d = 9999
                for note in self.notes:
                    if not note["alive"] or note["lane"] != i:
                        continue
                    dist = abs(note["y"] - self.hit_y)
                    if dist < self.hit_win and dist < best_d:
                        best = note
                        best_d = dist
                if best:
                    best["alive"] = False
                    self.progress += 1
                    self.combo += 1
                    self.score += 110 + self.combo * 8
                    self.hit_f[i] = 220
                else:
                    self.combo = 0
                    self.miss_f[i] = 240

    def update(self, dt):
        if self.done:
            return
        if not self._update_flow(dt):
            return
        self.tick += dt
        self.flash = max(-240, min(240, self.flash - math.copysign(dt, self.flash) if self.flash else 0))
        keys = pygame.key.get_pressed()
        cursor_spd = 300 * self._assist_scale()
        if self.variant in ("pop", "scrub"):
            # Mouse and keyboard both control the same cursor for accessibility.
            dx = (keys[pygame.K_RIGHT] or keys[pygame.K_d]) - (keys[pygame.K_LEFT] or keys[pygame.K_a])
            dy = (keys[pygame.K_DOWN] or keys[pygame.K_s]) - (keys[pygame.K_UP] or keys[pygame.K_w])
            self.cursor[0] = clamp(self.cursor[0] + dx * cursor_spd * dt / 1000, 32, SCREEN_W - 32)
            self.cursor[1] = clamp(self.cursor[1] + dy * cursor_spd * dt / 1000, 90, SCREEN_H - 32)
        if self.variant == "pop":
            self._update_pop(dt)
        elif self.variant == "scrub":
            self._update_scrub(dt)
        else:
            self._update_rhythm(dt)
        if self.progress >= self.target:
            self.done = True
            self.success = True

    def _update_pop(self, dt):
        self.spawn_t += dt
        spawn_gap = max(300, 700 - self.stage * 45)
        while self.spawn_t >= spawn_gap:
            self.spawn_t -= spawn_gap
            self._spawn_pop_bubble()
        for bubble in self.floaters:
            if not bubble["alive"]:
                continue
            bubble["x"] += bubble["vx"] * dt / 1000 * self._motion_scale()
            bubble["y"] += bubble["vy"] * dt / 1000
            if bubble["y"] < 70:
                bubble["alive"] = False
                if bubble["clean"]:
                    self.progress = max(0, self.progress - 1)
                    self.combo = 0
        self.floaters = [b for b in self.floaters if b["alive"]]

    def _update_scrub(self, dt):
        scrub_radius = (46 if self.settings["input_assist"] else 36) + int(self.calm * 8)
        for spot in self.clean_spots:
            if spot["hp"] <= 0:
                continue
            if math.hypot(self.cursor[0] - spot["x"], self.cursor[1] - spot["y"]) <= scrub_radius:
                spot["hp"] -= dt * 0.12 * (1.25 if self.settings["input_assist"] else 1.0)
                if spot["hp"] <= 0:
                    self.progress += 1
                    self.score += 120
        self.clean_spots = [s for s in self.clean_spots if s["hp"] > 0]

    def _update_rhythm(self, dt):
        self.spawn_t += dt
        interval = max(340, self.spawn_gap - self.progress * 4)
        if self.spawn_t >= interval:
            self.spawn_t = 0
            lane = random.randint(0, 3)
            self.notes.append({"lane": lane, "y": -30.0, "alive": True})
            if self.stage >= 2 and random.random() < 0.28:
                self.notes.append({"lane": (lane + random.randint(1, 3)) % 4, "y": -30.0, "alive": True})
        for note in self.notes:
            if note["alive"]:
                note["y"] += self.note_spd * dt / 1000
                if note["y"] > self.hit_y + self.hit_win + 36:
                    note["alive"] = False
                    self.combo = 0
                    self.progress = max(0, self.progress - 1)
        for flashes in (self.hit_f, self.miss_f):
            for key in list(flashes):
                flashes[key] -= dt
                if flashes[key] <= 0:
                    del flashes[key]
        self.notes = [n for n in self.notes if n["alive"]]

    def _draw_wash_background(self, surf):
        surf.fill((10, 18, 30))
        wave = 8 if self.settings["reduce_motion"] else 18
        for y in range(0, SCREEN_H, 20):
            offset = int(math.sin((self.tick + y * 4) * 0.0025) * wave)
            pygame.draw.line(surf, (16, 40, 64), (offset, y), (SCREEN_W + offset, y))
        draw_box(surf, (205, 220, 235, 120), (120, 120, 784, 380), 24)
        pygame.draw.ellipse(surf, (250, 224, 200), (180, 240, 280, 160))
        pygame.draw.ellipse(surf, (250, 224, 200), (560, 240, 280, 160))

    def draw(self, surf):
        if self.variant == "pop":
            self._draw_pop(surf)
        elif self.variant == "scrub":
            self._draw_scrub(surf)
        else:
            self._draw_rhythm(surf)

    def _draw_header(self, surf, title, subtitle):
        title_lbl = self.ft.render(title, True, ACCENT)
        surf.blit(title_lbl, (SCREEN_W // 2 - title_lbl.get_width() // 2, 16))
        sub_lbl = self.fb.render(subtitle, True, TEXT_COL)
        surf.blit(sub_lbl, (SCREEN_W // 2 - sub_lbl.get_width() // 2, 60))
        stat = self.fb.render(f"Clean: {self.progress}/{self.target}   Score: {self.score}", True, ACCENT)
        surf.blit(stat, (20, 18))
        bw = 420
        bx = SCREEN_W // 2 - bw // 2
        by = SCREEN_H - 24
        pygame.draw.rect(surf, (35, 30, 60), (bx, by, bw, 12), border_radius=6)
        fill = int(bw * self.progress / max(1, self.target))
        pygame.draw.rect(surf, ACCENT, (bx, by, fill, 12), border_radius=6)

    def _draw_pop(self, surf):
        self._draw_wash_background(surf)
        self._draw_header(surf, "Bubble Burst Wash", "Pop the blue soap bubbles. Avoid the green germ bubbles.")
        for bubble in self.floaters:
            col = SOAP_BLUE if bubble["clean"] else (120, 220, 120)
            alpha = 220 if bubble["clean"] else 190
            temp = pygame.Surface((bubble["r"] * 2 + 8, bubble["r"] * 2 + 8), pygame.SRCALPHA)
            pygame.draw.circle(temp, (*col, alpha), (bubble["r"] + 4, bubble["r"] + 4), bubble["r"])
            pygame.draw.circle(temp, (255, 255, 255, 160), (bubble["r"] + 4, bubble["r"] + 4), bubble["r"], 2)
            surf.blit(temp, (bubble["x"] - bubble["r"] - 4, bubble["y"] - bubble["r"] - 4))
            if not bubble["clean"]:
                pygame.draw.circle(surf, DARK, (int(bubble["x"] - 6), int(bubble["y"] - 4)), 3)
                pygame.draw.circle(surf, DARK, (int(bubble["x"] + 6), int(bubble["y"] - 4)), 3)
                pygame.draw.arc(surf, DARK, (bubble["x"] - 8, bubble["y"] - 2, 16, 12), math.pi, math.pi * 2, 2)
        pygame.draw.circle(surf, WHITE, (int(self.cursor[0]), int(self.cursor[1])), 18, 2)
        pygame.draw.line(surf, WHITE, (self.cursor[0] - 24, self.cursor[1]), (self.cursor[0] + 24, self.cursor[1]), 1)
        pygame.draw.line(surf, WHITE, (self.cursor[0], self.cursor[1] - 24), (self.cursor[0], self.cursor[1] + 24), 1)

    def _draw_scrub(self, surf):
        self._draw_wash_background(surf)
        self._draw_header(surf, "Scrub Sweep", "Move the sponge over dirty spots until they disappear.")
        for spot in self.clean_spots:
            if spot["hp"] <= 0:
                continue
            radius = 18 + int((spot["hp"] / 100) * 10)
            pygame.draw.circle(surf, (82, 72, 60), (int(spot["x"]), int(spot["y"])), radius)
            pygame.draw.circle(surf, (130, 116, 95), (int(spot["x"]), int(spot["y"])), radius, 2)
        sponge = pygame.Rect(int(self.cursor[0] - 30), int(self.cursor[1] - 22), 60, 44)
        pygame.draw.rect(surf, (255, 214, 82), sponge, border_radius=10)
        pygame.draw.rect(surf, (120, 100, 20), sponge, 2, border_radius=10)
        for bx in range(sponge.x + 8, sponge.right - 6, 10):
            pygame.draw.line(surf, (255, 240, 170), (bx, sponge.y + 8), (bx, sponge.bottom - 8), 2)

    def _draw_rhythm(self, surf):
        surf.fill((8, 6, 18))
        for y in range(0, SCREEN_H, 6):
            pygame.draw.line(surf, (16, 12, 28), (0, y), (SCREEN_W, y))
        self._draw_header(surf, "Foam Flow", "Hit D F J K or the arrow keys when the notes reach the ring.")
        for i, lane in enumerate(self.lanes):
            cx = int(SCREEN_W * lane["xf"])
            col = lane["col"]
            lane_glow = pygame.Surface((6, SCREEN_H), pygame.SRCALPHA)
            lane_glow.fill((*col, 22))
            surf.blit(lane_glow, (cx - 3, 0))
            ring_col = col
            if i in self.hit_f:
                ring_col = MINT
            elif i in self.miss_f:
                ring_col = RED
            pygame.draw.circle(surf, ring_col, (cx, self.hit_y), 28, 3)
            key_lbl = self.fb.render(lane["label"], True, WHITE)
            surf.blit(key_lbl, (cx - key_lbl.get_width() // 2, self.hit_y - 12))
        for note in self.notes:
            lane = self.lanes[note["lane"]]
            cx = int(SCREEN_W * lane["xf"])
            cy = int(note["y"])
            pygame.draw.circle(surf, lane["col"], (cx, cy), 24)
            pygame.draw.circle(surf, WHITE, (cx, cy), 24, 2)


class DoorMinigame(MinigameFlowMixin):
    def __init__(self, fb, ft, settings, anxiety=100):
        self.fb = fb
        self.ft = ft
        self.settings = settings
        self.anxiety = anxiety
        scale = 0.8 if settings["input_assist"] else 1.0
        self.spd = (170 + anxiety * 1.25) * scale
        self.marker = 0.0
        self.dir = 1
        self.hits = 0
        self.needed = 3
        self.done = False
        self.success = False
        self.flash = 0
        self.fail_flash = 0
        self.zone_center = 0.5
        self.distracts = []
        self._init_flow(
            "Door Nerves",
            [
                "Let the marker slide into the green safe zone.",
                "Press SPACE or ENTER only when it lines up.",
                "Take the reset if you miss. You only need a few clean hits.",
            ],
        )
        for _ in range(int(anxiety * 0.18)):
            self.distracts.append(
                {
                    "text": random.choice(["germs", "dirty", "sick", "danger", "unclean"]),
                    "x": random.randint(0, SCREEN_W),
                    "y": random.randint(0, SCREEN_H),
                    "vx": random.uniform(-20, 20),
                    "vy": random.uniform(-12, 12),
                    "a": random.randint(70, 160),
                }
            )

    def refresh_fonts(self, fb, ft):
        self.fb = fb
        self.ft = ft

    def handle_event(self, ev):
        if self._handle_flow_event(ev):
            return
        if ev.type == pygame.KEYDOWN and ev.key in (pygame.K_SPACE, pygame.K_RETURN):
            width = 620
            bx = SCREEN_W // 2 - width // 2
            zone_w = max(58, 162 - self.hits * 18)
            center_px = bx + int(width * self.zone_center)
            zx = center_px - zone_w // 2
            marker_x = bx + int(self.marker / 400 * width)
            if zx <= marker_x <= zx + zone_w:
                self.hits += 1
                self.flash = 280
                # Move the safe zone after each success so the player cannot camp one spot.
                self.zone_center = clamp(random.uniform(0.22, 0.78), 0.15, 0.85)
                if self.hits >= self.needed:
                    self.done = True
                    self.success = True
            else:
                self.hits = max(0, self.hits - 1)
                self.fail_flash = 320

    def update(self, dt):
        if self.done:
            return
        if not self._update_flow(dt):
            return
        self.marker += self.spd * self.dir * dt / 1000
        if self.marker >= 400:
            self.marker = 400
            self.dir = -1
        if self.marker <= 0:
            self.marker = 0
            self.dir = 1
        self.flash = max(0, self.flash - dt)
        self.fail_flash = max(0, self.fail_flash - dt)
        if not self.settings["reduce_motion"]:
            for item in self.distracts:
                item["x"] = (item["x"] + item["vx"] * dt / 1000) % SCREEN_W
                item["y"] = (item["y"] + item["vy"] * dt / 1000) % SCREEN_H

    def draw(self, surf, small_font):
        surf.fill((22, 16, 38))
        # The drifting words add pressure visually, but they never block the real timing input.
        for item in self.distracts:
            label = small_font.render(item["text"], True, (200, 80, 80))
            label.set_alpha(item["a"])
            surf.blit(label, (int(item["x"]), int(item["y"])))
        title = self.ft.render("Door Nerves", True, ACCENT)
        surf.blit(title, (SCREEN_W // 2 - title.get_width() // 2, 34))
        info = self.fb.render("Press SPACE when the marker lands in the safe zone.", True, TEXT_COL)
        surf.blit(info, (SCREEN_W // 2 - info.get_width() // 2, 84))
        anxiety_lbl = self.fb.render(f"Anxiety: {self.anxiety}%", True, RED if self.anxiety > 55 else ACCENT)
        surf.blit(anxiety_lbl, (20, 20))
        door_rect = pygame.Rect(155, 150, 220, 330)
        pygame.draw.rect(surf, (102, 72, 48), door_rect, border_radius=10)
        pygame.draw.rect(surf, (145, 106, 72), (door_rect.x + 14, door_rect.y + 16, 192, 292), border_radius=8)
        knob_x = door_rect.right - 40
        knob_y = door_rect.centery + 10
        pygame.draw.circle(surf, ACCENT, (knob_x, knob_y), 8)

        bw = 620
        bh = 52
        bx = SCREEN_W // 2 - bw // 2
        by = 515
        pygame.draw.rect(surf, (46, 34, 72), (bx, by, bw, bh), border_radius=8)
        zone_w = max(58, 162 - self.hits * 18)
        center_px = bx + int(bw * self.zone_center)
        zx = center_px - zone_w // 2
        zone_col = (90, 255, 110) if self.flash > 0 else (52, 170, 74)
        pygame.draw.rect(surf, zone_col, (zx, by, zone_w, bh), border_radius=7)
        mx = bx + int(self.marker / 400 * bw)
        pygame.draw.rect(surf, WHITE, (mx - 6, by - 10, 12, bh + 20), border_radius=4)
        hint = self.fb.render(f"Precision hits: {self.hits}/{self.needed}", True, TEXT_COL)
        surf.blit(hint, (SCREEN_W // 2 - hint.get_width() // 2, by + bh + 18))
        if self.fail_flash > 0:
            fail = self.fb.render("Too early. Breathe and line it up again.", True, RED)
            surf.blit(fail, (SCREEN_W // 2 - fail.get_width() // 2, by + bh + 48))


class VeggieSliceMinigame(MinigameFlowMixin):
    PLATE_Y = SCREEN_H - 122

    def __init__(self, fb, ft, settings, anxiety=100):
        self.fb = fb
        self.ft = ft
        self.settings = settings
        self.anxiety = anxiety
        self.calm = calm_factor(anxiety)
        self.done = False
        self.success = False
        self.items = []
        self.spawn_t = 0
        self.score = 0
        self.combo = 0
        self.missed = 0
        self.target = max(8, 13 - int(self.calm * 4))
        self.cursor = [SCREEN_W // 2, SCREEN_H // 2]
        self.trail = []
        self.flash = 0
        self._init_flow(
            "Separate The Veggies",
            [
                "Slice the veggies before they fall into the plate.",
                "Swipe with the mouse or move the cursor and press SPACE.",
                "You are clearing the plate, not fighting the food.",
            ],
        )

    def refresh_fonts(self, fb, ft):
        self.fb = fb
        self.ft = ft

    def _spawn_item(self):
        variants = [
            {"name": "carrot", "col": (242, 144, 68), "accent": (110, 170, 80)},
            {"name": "broccoli", "col": (78, 180, 86), "accent": (48, 122, 60)},
            {"name": "pepper", "col": (210, 64, 64), "accent": (66, 148, 66)},
        ]
        style = random.choice(variants)
        spread = 230 + int((1 - self.calm) * 70)
        lift = 510 + int((1 - self.calm) * 90)
        self.items.append(
            {
                "x": float(random.randint(120, SCREEN_W - 120)),
                "y": float(SCREEN_H + 30),
                "vx": float(random.uniform(-spread, spread)),
                "vy": float(-random.uniform(lift - 70, lift)),
                "rot": random.uniform(-0.8, 0.8),
                "angle": 0.0,
                "alive": True,
                "sliced": False,
                **style,
            }
        )

    def _slice_line(self, start, end):
        # Check the whole swipe path, not just the cursor endpoint, so slicing feels fair.
        for item in self.items:
            if not item["alive"]:
                continue
            dist = self._distance_to_segment((item["x"], item["y"]), start, end)
            if dist <= 34:
                item["alive"] = False
                item["sliced"] = True
                self.score += 1
                self.combo += 1
                self.flash = 180

    def _distance_to_segment(self, point, start, end):
        px, py = point
        x1, y1 = start
        x2, y2 = end
        dx = x2 - x1
        dy = y2 - y1
        if dx == 0 and dy == 0:
            return math.hypot(px - x1, py - y1)
        t = clamp(((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy), 0, 1)
        proj_x = x1 + t * dx
        proj_y = y1 + t * dy
        return math.hypot(px - proj_x, py - proj_y)

    def handle_event(self, ev):
        if self._handle_flow_event(ev):
            return
        if ev.type == pygame.MOUSEMOTION:
            prev = tuple(self.cursor)
            self.cursor[0], self.cursor[1] = ev.pos
            self.trail.append((tuple(self.cursor), 120))
            self._slice_line(prev, tuple(self.cursor))
        elif ev.type == pygame.MOUSEBUTTONDOWN:
            self.cursor[0], self.cursor[1] = ev.pos
            self.trail.append((tuple(self.cursor), 150))
        elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_SPACE:
            self._slice_line((self.cursor[0] - 46, self.cursor[1] - 14), (self.cursor[0] + 46, self.cursor[1] + 14))
            self.trail.append((tuple(self.cursor), 160))

    def update(self, dt):
        if self.done:
            return
        if not self._update_flow(dt):
            return
        self.spawn_t += dt
        self.flash = max(0, self.flash - dt)
        keys = pygame.key.get_pressed()
        cursor_spd = 320 + int(self.calm * 45)
        dx = (keys[pygame.K_RIGHT] or keys[pygame.K_d]) - (keys[pygame.K_LEFT] or keys[pygame.K_a])
        dy = (keys[pygame.K_DOWN] or keys[pygame.K_s]) - (keys[pygame.K_UP] or keys[pygame.K_w])
        self.cursor[0] = clamp(self.cursor[0] + dx * cursor_spd * dt / 1000, 32, SCREEN_W - 32)
        self.cursor[1] = clamp(self.cursor[1] + dy * cursor_spd * dt / 1000, 80, SCREEN_H - 40)
        spawn_gap = 620 + int(self.calm * 120)
        while self.spawn_t >= spawn_gap:
            self.spawn_t -= spawn_gap
            self._spawn_item()
        for item in self.items:
            if not item["alive"]:
                continue
            item["vy"] += 780 * dt / 1000
            item["x"] += item["vx"] * dt / 1000
            item["y"] += item["vy"] * dt / 1000
            item["angle"] += item["rot"] * dt / 120
            if item["y"] >= self.PLATE_Y and 250 <= item["x"] <= SCREEN_W - 250:
                item["alive"] = False
                self.combo = 0
                self.missed += 1
            elif item["y"] > SCREEN_H + 60:
                item["alive"] = False
        self.items = [item for item in self.items if item["alive"]]
        self.trail = [(point, age - dt) for point, age in self.trail if age - dt > 0]
        if self.score >= self.target:
            self.done = True
            self.success = True

    def _draw_item(self, surf, item):
        x = int(item["x"])
        y = int(item["y"])
        if item["name"] == "carrot":
            pygame.draw.ellipse(surf, item["col"], (x - 16, y - 28, 32, 56))
            pygame.draw.polygon(surf, item["accent"], [(x, y - 36), (x - 10, y - 56), (x, y - 46), (x + 10, y - 56)])
        elif item["name"] == "broccoli":
            pygame.draw.rect(surf, item["accent"], (x - 6, y - 10, 12, 28), border_radius=4)
            pygame.draw.circle(surf, item["col"], (x, y - 18), 24)
            pygame.draw.circle(surf, item["col"], (x - 16, y - 12), 18)
            pygame.draw.circle(surf, item["col"], (x + 16, y - 12), 18)
        else:
            pygame.draw.ellipse(surf, item["col"], (x - 18, y - 28, 36, 56))
            pygame.draw.rect(surf, item["accent"], (x - 4, y - 42, 8, 18), border_radius=4)

    def draw(self, surf):
        top = (36, 30, 24)
        bottom = (86, 68, 52)
        for y in range(SCREEN_H):
            mix = y / SCREEN_H
            col = (
                int(top[0] * (1 - mix) + bottom[0] * mix),
                int(top[1] * (1 - mix) + bottom[1] * mix),
                int(top[2] * (1 - mix) + bottom[2] * mix),
            )
            pygame.draw.line(surf, col, (0, y), (SCREEN_W, y))
        counter = pygame.Rect(0, self.PLATE_Y - 8, SCREEN_W, SCREEN_H - self.PLATE_Y + 8)
        pygame.draw.rect(surf, (96, 80, 66), counter)
        pygame.draw.ellipse(surf, (214, 214, 222), (SCREEN_W // 2 - 180, self.PLATE_Y - 28, 360, 110))
        pygame.draw.ellipse(surf, (245, 245, 250), (SCREEN_W // 2 - 160, self.PLATE_Y - 14, 320, 78))
        title = self.ft.render("Plate Guard", True, WHITE)
        surf.blit(title, (SCREEN_W // 2 - title.get_width() // 2, 18))
        subtitle = self.fb.render("Slice the veggies before they drop into dinner.", True, TEXT_COL)
        surf.blit(subtitle, (SCREEN_W // 2 - subtitle.get_width() // 2, 56))
        left = self.fb.render(f"Cleared: {self.score}/{self.target}", True, ACCENT)
        right = self.fb.render(f"Slips: {self.missed}", True, RED if self.missed >= 2 else ACCENT)
        surf.blit(left, (24, 22))
        surf.blit(right, (SCREEN_W - 24 - right.get_width(), 22))
        combo = self.fb.render(f"Combo x{self.combo}", True, MINT if self.combo >= 2 else TEXT_COL)
        surf.blit(combo, (SCREEN_W // 2 - combo.get_width() // 2, 92))
        for item in self.items:
            self._draw_item(surf, item)
        if len(self.trail) >= 2:
            for idx in range(1, len(self.trail)):
                (x1, y1), age1 = self.trail[idx - 1]
                (x2, y2), age2 = self.trail[idx]
                alpha = max(30, min(age1, age2))
                line = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
                pygame.draw.line(line, (255, 244, 180, alpha), (x1, y1), (x2, y2), 5)
                surf.blit(line, (0, 0))
        pygame.draw.circle(surf, WHITE, (int(self.cursor[0]), int(self.cursor[1])), 14, 2)
        pygame.draw.line(surf, WHITE, (self.cursor[0] - 20, self.cursor[1]), (self.cursor[0] + 20, self.cursor[1]), 2)
        pygame.draw.line(surf, WHITE, (self.cursor[0], self.cursor[1] - 20), (self.cursor[0], self.cursor[1] + 20), 2)
        if self.flash > 0:
            hit = self.fb.render("Nice cut.", True, MINT)
            surf.blit(hit, (SCREEN_W // 2 - hit.get_width() // 2, 120))


# Older story code still refers to this minigame by its previous name.
CatFightMinigame = VeggieSliceMinigame


class TherapyMinigame(MinigameFlowMixin):
    TARGET = 10
    SPAWN = 850
    LIFE = 3000

    def __init__(self, fb, ft, settings, anxiety=100):
        self.fb = fb
        self.ft = ft
        self.settings = settings
        self.calm = calm_factor(anxiety)
        self.circles = []
        self.caught = 0
        self.missed = 0
        self.combo = 0
        self.score = 0
        self.spawn_t = 0
        self.done = False
        self.success = False
        self.tick = 0
        self._init_flow(
            "Therapy Focus",
            [
                "Click the circles before the thoughts fade away.",
                "SPACE also grabs the most recent thought in a pinch.",
                "A steady rhythm works better than rushing.",
            ],
        )
        self.target = max(7, self.TARGET - int(self.calm * 3))
        self._spawn()

    def refresh_fonts(self, fb, ft):
        self.fb = fb
        self.ft = ft

    def _spawn(self):
        x = random.randint(100, SCREEN_W - 100)
        y = random.randint(120, SCREEN_H - 120)
        col = random.choice([(220, 80, 120), (80, 160, 220), (100, 220, 120), (220, 160, 50), (160, 80, 220)])
        # Numbering the circles makes the "most recent thought" readable on screen.
        self.circles.append({"x": x, "y": y, "col": col, "age": 0, "alive": True, "num": self.caught + self.missed + 1})

    def handle_event(self, ev):
        if self._handle_flow_event(ev):
            return
        if ev.type == pygame.MOUSEBUTTONDOWN:
            for circle in self.circles:
                if not circle["alive"]:
                    continue
                prog = circle["age"] / self.LIFE
                radius = int(44 * (1 - prog * 0.55))
                if math.hypot(ev.pos[0] - circle["x"], ev.pos[1] - circle["y"]) <= radius:
                    circle["alive"] = False
                    self.caught += 1
                    self.combo += 1
                    self.score += int(300 * (1 - prog) * max(1, self.combo // 2))
        if ev.type == pygame.KEYDOWN and ev.key == pygame.K_SPACE:
            for circle in reversed(self.circles):
                if circle["alive"]:
                    circle["alive"] = False
                    self.caught += 1
                    self.combo += 1
                    self.score += 180
                    break

    def update(self, dt):
        if self.done:
            return
        if not self._update_flow(dt):
            return
        self.tick += dt
        self.spawn_t += dt
        interval = max(560, self.SPAWN - self.caught * 24 + int(self.calm * 140))
        if self.settings["input_assist"]:
            interval += 120
        if self.spawn_t >= interval:
            self.spawn_t = 0
            self._spawn()
        life = self.LIFE + int(self.calm * 650) + (500 if self.settings["input_assist"] else 0)
        for circle in self.circles:
            if not circle["alive"]:
                continue
            circle["age"] += dt
            if circle["age"] >= life:
                circle["alive"] = False
                self.missed += 1
                self.combo = 0
        self.circles = [c for c in self.circles if c["alive"]]
        if self.caught >= self.TARGET:
            self.done = True
            self.success = True

    def draw(self, surf):
        surf.fill((18, 14, 32))
        for gx in range(0, SCREEN_W, 60):
            for gy in range(0, SCREEN_H, 60):
                pygame.draw.circle(surf, (35, 30, 55), (gx, gy), 2)
        title = self.ft.render("Therapy Focus", True, ACCENT)
        surf.blit(title, (SCREEN_W // 2 - title.get_width() // 2, 16))
        subtitle = self.fb.render("Click the thought circles before they fade away.", True, TEXT_COL)
        surf.blit(subtitle, (SCREEN_W // 2 - subtitle.get_width() // 2, 58))
        stat = self.fb.render(f"Score: {self.score}   Combo: x{self.combo}   Hit: {self.caught}/{self.TARGET}", True, ACCENT)
        surf.blit(stat, (18, 16))
        life = self.LIFE + (500 if self.settings["input_assist"] else 0)
        for circle in self.circles:
            prog = circle["age"] / life
            radius = int(44 * (1 - prog * 0.55))
            alpha = int(255 * (1 - prog * 0.7))
            outer = int(radius + 28 * (1 - prog))
            tmp = pygame.Surface((outer * 2 + 4, outer * 2 + 4), pygame.SRCALPHA)
            pygame.draw.circle(tmp, (*circle["col"], max(30, int(alpha * 0.4))), (outer + 2, outer + 2), outer, 2)
            surf.blit(tmp, (circle["x"] - outer - 2, circle["y"] - outer - 2))
            orb = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
            pygame.draw.circle(orb, (*circle["col"], alpha), (radius, radius), radius)
            pygame.draw.circle(orb, (255, 255, 255, alpha), (radius, radius), radius, 2)
            surf.blit(orb, (circle["x"] - radius, circle["y"] - radius))
            num = self.fb.render(str(circle["num"]), True, WHITE)
            num.set_alpha(alpha)
            surf.blit(num, (circle["x"] - num.get_width() // 2, circle["y"] - num.get_height() // 2))


class BossMinigame(MinigameFlowMixin):
    SOUL_SPD = 178
    BX = SCREEN_W // 2 - 160
    BY = 265
    BW = 320
    BH = 160
    DURATION = 14000

    def __init__(self, fb, ft, settings, anxiety=100):
        self.fb = fb
        self.ft = ft
        self.settings = settings
        self.anxiety = anxiety
        self.calm = calm_factor(anxiety)
        self.sx = float(SCREEN_W // 2)
        self.sy = float(self.BY + self.BH // 2)
        self.hp = 4
        self.time = 0
        self.attacks = []
        self.atk_t = 0
        self.done = False
        self.success = False
        self.hit_cd = 0
        self.mouth_x = SCREEN_W // 2
        self.mouth_y = self.BY - 34
        self._init_flow(
            "Boss Breakdown",
            [
                "Stay inside the white box and dodge every spit shot.",
                "Move with arrows or WASD before the spread closes in.",
                "You are surviving the moment, not winning an argument.",
            ],
        )

    def refresh_fonts(self, fb, ft):
        self.fb = fb
        self.ft = ft

    def handle_event(self, ev):
        self._handle_flow_event(ev)

    def update(self, dt):
        if self.done:
            return
        if not self._update_flow(dt):
            return
        self.time += dt
        self.hit_cd = max(0, self.hit_cd - dt)
        keys = pygame.key.get_pressed()
        dx = (keys[pygame.K_RIGHT] or keys[pygame.K_d]) - (keys[pygame.K_LEFT] or keys[pygame.K_a])
        dy = (keys[pygame.K_DOWN] or keys[pygame.K_s]) - (keys[pygame.K_UP] or keys[pygame.K_w])
        speed = self.SOUL_SPD * (0.88 if self.settings["input_assist"] else 1.0)
        step = speed * dt / 1000
        self.sx = clamp(self.sx + dx * step, self.BX + 10, self.BX + self.BW - 10)
        self.sy = clamp(self.sy + dy * step, self.BY + 10, self.BY + self.BH - 10)
        self.atk_t += dt
        interval = max(360, 1120 - int(self.time / 1000) * 55 + int(self.calm * 70))
        if self.settings["input_assist"]:
            interval += 140
        if self.atk_t >= interval:
            self.atk_t = 0
            # Mixing attack patterns keeps the scene tense without needing complex enemy AI.
            kind = random.choice(["lr", "rl", "spit", "spit", "spread", "spread", "cross"])
            if kind == "lr":
                self.attacks.append({"x": float(self.BX - 10), "y": float(self.BY + random.randint(20, self.BH - 20)), "vx": 320, "vy": 0, "r": 9, "alive": True, "kind": "orb"})
            elif kind == "rl":
                self.attacks.append({"x": float(self.BX + self.BW + 10), "y": float(self.BY + random.randint(20, self.BH - 20)), "vx": -320, "vy": 0, "r": 9, "alive": True, "kind": "orb"})
            elif kind == "cross":
                self.attacks.append({"x": float(self.BX - 10), "y": float(self.BY + random.randint(20, self.BH - 20)), "vx": 330, "vy": 0, "r": 8, "alive": True, "kind": "orb"})
                self.attacks.append({"x": float(self.BX + self.BW + 10), "y": float(self.BY + random.randint(20, self.BH - 20)), "vx": -330, "vy": 0, "r": 8, "alive": True, "kind": "orb"})
            else:
                dx = self.sx - self.mouth_x
                dy = self.sy - self.mouth_y
                mag = max(1.0, math.hypot(dx, dy))
                spd = 165 if kind == "spread" else 190
                angles = (-0.2, 0, 0.2) if kind == "spread" else (0,)
                for ang in angles:
                    vx = (dx / mag) * spd
                    vy = (dy / mag) * spd
                    cos_a = math.cos(ang)
                    sin_a = math.sin(ang)
                    self.attacks.append(
                        {
                            "x": float(self.mouth_x),
                            "y": float(self.mouth_y),
                            "vx": vx * cos_a - vy * sin_a,
                            "vy": vx * sin_a + vy * cos_a,
                            "r": 8 if kind == "spread" else 10,
                            "alive": True,
                            "kind": "spit",
                        }
                    )
        for atk in self.attacks:
            if not atk["alive"]:
                continue
            atk["x"] += atk["vx"] * dt / 1000
            atk["y"] += atk["vy"] * dt / 1000
            if atk["x"] < self.BX - 20 or atk["x"] > self.BX + self.BW + 20 or atk["y"] < self.BY - 20 or atk["y"] > self.BY + self.BH + 20:
                atk["alive"] = False
            elif atk["alive"] and self.hit_cd <= 0 and math.hypot(atk["x"] - self.sx, atk["y"] - self.sy) < atk["r"] + 7:
                atk["alive"] = False
                self.hp -= 1
                self.hit_cd = 780
        self.attacks = [atk for atk in self.attacks if atk["alive"]]
        if self.hp <= 0:
            self.done = True
            self.success = False
        elif self.time >= self.DURATION:
            self.done = True
            self.success = True

    def draw(self, surf):
        surf.fill(DARK)
        draw_box(surf, (28, 22, 50, 210), (60, 38, SCREEN_W - 120, 195), 12)
        pygame.draw.rect(surf, ACCENT, (60, 38, SCREEN_W - 120, 195), 2, border_radius=12)
        lines = [
            'BOSS: "You are late again."',
            "Survive the confrontation. Dodge the red attacks.",
            "Move with WASD or arrows inside the white box.",
        ]
        for i, line in enumerate(lines):
            label = self.fb.render(line, True, ACCENT if i == 0 else TEXT_COL)
            surf.blit(label, (80, 54 + i * 42))
        draw_vignette(surf, (int(self.sx), int(self.sy)), 142, 130)
        pygame.draw.circle(surf, (150, 66, 66), (self.mouth_x, self.mouth_y - 38), 48)
        pygame.draw.circle(surf, (242, 210, 210), (self.mouth_x - 16, self.mouth_y - 48), 6)
        pygame.draw.circle(surf, (242, 210, 210), (self.mouth_x + 16, self.mouth_y - 48), 6)
        pygame.draw.ellipse(surf, (86, 18, 28), (self.mouth_x - 18, self.mouth_y - 22, 36, 20))
        pygame.draw.line(surf, (210, 240, 255), (self.mouth_x - 7, self.mouth_y - 4), (self.mouth_x - 11, self.mouth_y + 10), 2)
        pygame.draw.line(surf, (210, 240, 255), (self.mouth_x + 5, self.mouth_y - 2), (self.mouth_x + 10, self.mouth_y + 12), 2)
        pygame.draw.rect(surf, WHITE, (self.BX, self.BY, self.BW, self.BH), 3)
        soul_col = RED if self.hit_cd > 0 else (255, 60, 60)
        pts = [(self.sx, self.sy - 10), (self.sx + 10, self.sy), (self.sx, self.sy + 10), (self.sx - 10, self.sy)]
        pygame.draw.polygon(surf, soul_col, pts)
        pygame.draw.polygon(surf, WHITE, pts, 1)
        for atk in self.attacks:
            if atk.get("kind") == "spit":
                trail_x = atk["x"] - atk["vx"] * 0.03
                trail_y = atk["y"] - atk["vy"] * 0.03
                pygame.draw.circle(surf, (205, 236, 255), (int(trail_x), int(trail_y)), max(3, atk["r"] - 3))
                pygame.draw.circle(surf, (178, 222, 246), (int(atk["x"]), int(atk["y"])), atk["r"])
                pygame.draw.circle(surf, WHITE, (int(atk["x"]), int(atk["y"])), atk["r"], 1)
            else:
                pygame.draw.circle(surf, RED, (int(atk["x"]), int(atk["y"])), atk["r"])
                pygame.draw.circle(surf, WHITE, (int(atk["x"]), int(atk["y"])), atk["r"], 1)
        hp_lbl = self.fb.render(f"HP: {self.hp}/4", True, RED)
        surf.blit(hp_lbl, (self.BX, self.BY + self.BH + 16))
        remain = max(0, (self.DURATION - self.time) // 1000)
        timer_lbl = self.fb.render(f"Survive: {remain}s", True, ACCENT)
        surf.blit(timer_lbl, (self.BX + self.BW - timer_lbl.get_width(), self.BY + self.BH + 16))


STORY = [
    # The whole narrative is a simple event script that the Game class steps through.
    {"type": "dlg", "lines": [{"speaker": "Narrator", "text": "Day 1. Your apartment feels small, but the anxiety still fills every corner."}]},
    {"type": "dlg", "lines": [{"speaker": "MC (thinking)", "text": "I need to wash up, but I can feel the ritual trying to spiral again."}]},
    {"type": "task", "target": "Sink", "prompt": "Go to the sink."},
    {"type": "mg_wash", "variant": "pop"},
    {"type": "dlg", "lines": [{"speaker": "MC (thinking)", "text": "That helped for a second... but my face still doesn't feel clean enough."}]},
    {"type": "task", "target": "Mirror", "prompt": "Go to the mirror."},
    {"type": "mg_wash", "variant": "scrub"},
    {"type": "dlg", "lines": [{"speaker": "MC (thinking)", "text": "What if the soap missed something? I should run through the hand-washing rhythm one more time before I touch the door."}]},
    {"type": "task", "target": "Front Door", "prompt": "Go to the front door."},
    {"type": "mg_wash", "variant": "rhythm"},
    {"type": "dlg", "lines": [
        {"speaker": "MC (thinking)", "text": "I lost so much time again. I need to hurry."},
        {"speaker": "Narrator", "text": "You rush out and try to hold yourself together on the way to work."},
    ]},
    {"type": "room", "room": "work", "px": 480, "py": 460},
    {"type": "dlg", "lines": [
        {"speaker": "Narrator", "text": "The office feels too quiet. Your boss is already there, and the room suddenly seems much smaller."},
        {"speaker": "MC (thinking)", "text": "If he catches me freezing at that door, I am done. Just keep low, move carefully, and get there."},
    ]},
    {"type": "task", "target": "Work Door", "prompt": "Sneak around the boss and reach the work door."},
    {"type": "mg_door"},
    {"type": "dlg", "lines": [
        {"speaker": "Narrator", "text": "The handle sticks. The little click sounds enormous in the silent office."},
        {"speaker": "Boss", "text": "What exactly are you doing sneaking around my office?"}
    ]},
    {"type": "mg_boss"},
    {"type": "dlg", "lines": [
        {"speaker": "Boss", "text": "You are late again."},
        {"speaker": "MC", "text": "I know. I'm sorry. I really am trying."},
        {"speaker": "Boss", "text": "I need to see change, not just apologies."},
    ]},
    {"type": "task", "target": "Coworker", "prompt": "Talk to your coworker."},
    {"type": "dlg", "lines": [
        {"speaker": "Coworker", "text": "You look overwhelmed. Is this still about all the washing before work?"},
        {"speaker": "MC", "text": "Yeah. It keeps growing. Hands, surfaces, door handles, all of it."},
        {"speaker": "Coworker", "text": "I know a therapist who helps people with loops like that. Want the number?"},
        {"speaker": "MC", "text": "Please. I don't want to keep living like this."},
    ]},
    {"type": "room", "room": "therapy", "px": 300, "py": 420},
    {"type": "task", "target": "Couch", "prompt": "Walk into the office."},
    {"type": "dlg", "lines": [
        {"speaker": "Therapist", "text": "Take your time. You do not have to look composed to be welcome here."},
        {"speaker": "MC", "text": "It feels like if I stop washing, something bad will happen, and if I leave before it feels right I can't think about anything else."},
        {"speaker": "Therapist", "text": "That makes sense. The urge is trying to promise certainty, even though it keeps asking more from you."},
        {"speaker": "MC", "text": "Yeah. Even when I know it sounds irrational, my body still acts like the threat is real."},
        {"speaker": "Therapist", "text": "Then we start with the body. Less fighting it, more noticing it and practicing focus instead of panic."},
    ]},
    {"type": "mg_therapy"},
    {"type": "room", "room": "home", "px": 330, "py": 430},
    {"type": "dlg", "lines": [{"speaker": "Narrator", "text": "That evening, dinner becomes its own small test of control and self-care."}]},
    {"type": "task", "target": "Dinner Table", "prompt": "Go to the dinner table."},
    {"type": "mg_eat"},
    {"type": "dlg", "lines": [
        {"speaker": "MC (thinking)", "text": "That was weirdly fun. Maybe taking care of myself can feel strong instead of scared."},
        {"speaker": "Narrator", "text": "Day 2 arrives. The fear is still there, but now it has resistance."},
    ]},
    {"type": "task", "target": "Sink", "prompt": "Go to the sink."},
    {"type": "mg_wash", "variant": "rhythm"},
    {"type": "dlg", "lines": [{"speaker": "MC (thinking)", "text": "I can feel the urge to restart the whole routine. I need to interrupt it."}]},
    {"type": "task", "target": "Mirror", "prompt": "Check the mirror and keep moving."},
    {"type": "mg_wash", "variant": "scrub"},
    {"type": "dlg", "lines": [
        {"speaker": "MC (thinking)", "text": "I'm not ready for work today. I want help more than I want another spiral."},
        {"speaker": "Narrator", "text": "You choose therapy instead of forcing another bad morning."},
    ]},
    {"type": "room", "room": "therapy", "px": 300, "py": 420},
    {"type": "task", "target": "Therapist", "prompt": "Talk to the therapist."},
    {"type": "dlg", "lines": [
        {"speaker": "MC", "text": "I still slipped this morning, but I noticed it sooner."},
        {"speaker": "Therapist", "text": "That matters. Progress is not the absence of fear. It is noticing it and choosing differently anyway."},
        {"speaker": "MC", "text": "So even partial progress counts?"},
        {"speaker": "Therapist", "text": "Absolutely. Partial progress is how most real healing looks."},
        {"speaker": "MC", "text": "Sometimes I still feel embarrassed saying it out loud. Like I should be able to out-logic it by now."},
        {"speaker": "Therapist", "text": "You are not failing a logic test. You are retraining a fear system, and that takes repetition, patience, and self-respect."},
    ]},
    {"type": "mg_therapy"},
    {"type": "room", "room": "home", "px": 330, "py": 430},
    {"type": "task", "target": "Dinner Table", "prompt": "Head back to dinner."},
    {"type": "mg_eat"},
    {"type": "dlg", "lines": [
        {"speaker": "Narrator", "text": "Day 3. The apartment is the same, but your thoughts are not quite as loud."},
        {"speaker": "MC (thinking)", "text": "One wash. One careful check. Then I leave."},
    ]},
    {"type": "task", "target": "Sink", "prompt": "Go to the sink."},
    {"type": "mg_wash", "variant": "pop"},
    {"type": "dlg", "lines": [{"speaker": "MC (thinking)", "text": "That was enough. It really was enough."}]},
    {"type": "room", "room": "work", "px": 480, "py": 460},
    {"type": "task", "target": "Boss", "prompt": "Walk up to your boss."},
    {"type": "dlg", "lines": [
        {"speaker": "Boss", "text": "You're on time."},
        {"speaker": "MC", "text": "I am. It took work, but I am."},
        {"speaker": "Boss", "text": "Keep that momentum going."},
    ]},
    {"type": "task", "target": "Coworker", "prompt": "Talk to your coworker."},
    {"type": "dlg", "lines": [
        {"speaker": "Coworker", "text": "You seem lighter."},
        {"speaker": "MC", "text": "I still get the thoughts. But now I can see them, breathe, and choose what to do next."},
        {"speaker": "Narrator", "text": "That is not a perfect ending. It is something better: a real one."},
    ]},
    {"type": "end"},
]


def draw_hud(surf, anxiety, room_name, font, objective, settings):
    room_lbl = font.render(room_name, True, WHITE)
    surf.blit(room_lbl, (18, 16))
    bw = 190
    bh = 15
    bx = SCREEN_W - bw - 18
    by = 18
    draw_box(surf, (28, 22, 48, 210), (bx - 8, by - 4, bw + 16, bh + 8), 6)
    fill = int(bw * max(0, anxiety) / 100)
    fill_col = RED if anxiety > 65 else (220, 175, 55) if anxiety > 35 else (80, 200, 120)
    if settings["high_contrast"]:
        fill_col = (255, 70, 70) if anxiety > 65 else (255, 220, 70) if anxiety > 35 else (70, 255, 140)
    pygame.draw.rect(surf, fill_col, (bx, by, fill, bh), border_radius=5)
    pygame.draw.rect(surf, TEXT_COL, (bx, by, bw, bh), 1, border_radius=5)
    anxiety_lbl = font.render(f"Anxiety: {anxiety}%", True, TEXT_COL)
    surf.blit(anxiety_lbl, (bx, by + bh + 4))
    if objective:
        wrapped = wrap(objective, font, 292)
        obj_h = 30 + len(wrapped) * (font.get_linesize() + 1)
        obj_box = pygame.Rect(18, 42, 320, max(48, obj_h))
        draw_box(surf, (16, 12, 30, 210), obj_box, 10)
        pygame.draw.rect(surf, ACCENT, obj_box, 2, border_radius=10)
        goal_lbl = font.render("Goal", True, ACCENT)
        surf.blit(goal_lbl, (obj_box.x + 10, obj_box.y + 6))
        for idx, line in enumerate(wrapped[:3]):
            text_lbl = font.render(line, True, TEXT_COL)
            surf.blit(text_lbl, (obj_box.x + 10, obj_box.y + 24 + idx * (font.get_linesize() + 1)))


def draw_title(surf, ft, fb, tick, settings):
    surf.fill((10, 8, 22))
    random.seed(7)
    for idx in range(24):
        x = (random.randint(0, SCREEN_W) + tick * (idx % 3 + 1) // 55) % SCREEN_W
        y = (random.randint(0, SCREEN_H) + tick * (idx % 2 + 1) // 75) % SCREEN_H
        radius = random.randint(8, 22)
        alpha = random.randint(28, 55)
        temp = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
        pygame.draw.circle(temp, (55, 200, 100, alpha), (radius, radius), radius)
        surf.blit(temp, (x, y))
    random.seed()
    bob = 2 if settings["reduce_motion"] else math.sin(tick * 0.0018) * 7
    title = ft.render("GERMOPHOBIA", True, ACCENT)
    surf.blit(title, (SCREEN_W // 2 - title.get_width() // 2, int(154 + bob)))
    subtitle = fb.render("A harder, stranger, more hopeful day-by-day journey", True, TEXT_COL)
    surf.blit(subtitle, (SCREEN_W // 2 - subtitle.get_width() // 2, 238))
    card = pygame.Rect(234, 290, 556, 176)
    draw_box(surf, (16, 12, 28, 205), card, 18)
    pygame.draw.rect(surf, ACCENT, card, 2, border_radius=18)
    lines = [
        "Experience life through the lens of a germaphobe ",
    ]
    for idx, line in enumerate(lines):
        lbl = fb.render(line, True, TEXT_COL)
        surf.blit(lbl, (card.x + 24, card.y + 24 + idx * 30))
    if int(tick / 550) % 2 == 0:
        prompt = fb.render("Press ENTER to begin", True, WHITE)
        surf.blit(prompt, (SCREEN_W // 2 - prompt.get_width() // 2, 496))
    ctrl = fb.render("WASD / arrows to move, E or ENTER to interact, TAB for settings", True, (100, 100, 125))
    surf.blit(ctrl, (SCREEN_W // 2 - ctrl.get_width() // 2, SCREEN_H - 42))


def draw_ending(surf, ft, fb, tick):
    top = (28, 28, 42)
    bottom = (90, 120, 150)
    for y in range(SCREEN_H):
        mix = y / SCREEN_H
        col = (
            int(top[0] * (1 - mix) + bottom[0] * mix),
            int(top[1] * (1 - mix) + bottom[1] * mix),
            int(top[2] * (1 - mix) + bottom[2] * mix),
        )
        pygame.draw.line(surf, col, (0, y), (SCREEN_W, y))
    for idx in range(12):
        x = 80 + idx * 82 + int(math.sin(tick * 0.001 + idx) * 8)
        y = 90 + int(math.cos(tick * 0.0009 + idx) * 18)
        pygame.draw.circle(surf, (255, 235, 180, 38), (x, y), 22)
    card = pygame.Rect(162, 96, SCREEN_W - 324, SCREEN_H - 192)
    draw_box(surf, (14, 18, 28, 228), card, 24)
    pygame.draw.rect(surf, (255, 224, 140), card, 2, border_radius=24)
    title = ft.render("A Comfortable Ending", True, ACCENT)
    surf.blit(title, (SCREEN_W // 2 - title.get_width() // 2, 130))
    lines = [
        "You are not failing because hard thoughts still show up.",
        "You are growing because you noticed them, stayed present, and kept going anyway.",
        "Healing is rarely clean, fast, or dramatic.",
        "Small decisions count. Rest counts. Asking for help counts.",
        "You deserve a life with more room in it than fear.",
    ]
    for idx, line in enumerate(lines):
        lbl = fb.render(line, True, TEXT_COL)
        surf.blit(lbl, (card.x + 42, card.y + 98 + idx * 42))
    note = fb.render("Press ENTER to return to the title screen.", True, WHITE)
    surf.blit(note, (SCREEN_W // 2 - note.get_width() // 2, card.bottom - 62))


class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        pygame.display.set_caption("Germophobia")
        self.clock = pygame.time.Clock()
        self.settings = DEFAULT_SETTINGS.copy()
        self._rebuild_fonts()

        sheet = load_img("character.png")
        self.player = Player(sheet, 300, 380)
        self.dlg = DialogueBox(self.fb, self.fs, self.settings)
        self.fader = Fader()
        self.camera = Camera(1000, 800)
        self.state = ST_TITLE
        self.ev_idx = 0
        self.anxiety = 100
        self.minigame = None
        self.tick = 0
        self.particles = []
        self.current_task = None
        self.settings_overlay = SettingsOverlay(self)
        self.ending_ready = False
        self.wash_stage = {"pop": 0, "scrub": 0, "rhythm": 0}

        self._build_rooms()
        self._set_room("home")

    def _rebuild_fonts(self):
        # Fonts are rebuilt from settings instead of scaled on the fly for cleaner text.
        if self.settings["large_text"]:
            self.ft = pygame.font.SysFont("Georgia", 52, bold=True)
            self.fb = pygame.font.SysFont("Georgia", 26)
            self.fs = pygame.font.SysFont("Georgia", 26, bold=True)
            self.fsm = pygame.font.SysFont("Georgia", 18)
        else:
            self.ft = pygame.font.SysFont("Georgia", 46, bold=True)
            self.fb = pygame.font.SysFont("Georgia", 22)
            self.fs = pygame.font.SysFont("Georgia", 22, bold=True)
            self.fsm = pygame.font.SysFont("Georgia", 16)

    def toggle_setting(self, key):
        self.settings[key] = not self.settings[key]
        if key == "large_text":
            self._rebuild_fonts()
            self.dlg.refresh_fonts(self.fb, self.fs)
        if self.minigame and hasattr(self.minigame, "refresh_fonts"):
            self.minigame.refresh_fonts(self.fb, self.ft)

    def _build_rooms(self):
        home = Room("Your Apartment", 32, 26, (108, 94, 84), (66, 54, 42), (188, 150, 92))
        home.objects += [
            Obj("Sink", 120, 170, 72, 62, "sink"),
            Obj("Mirror", 248, 128, 58, 84, "mirror"),
            Obj("Front Door", 390, 48, 76, 44, "door"),
            Obj("Fridge", 660, 128, 68, 102, "fridge", interactable=False),
            Obj("Dinner Table", 480, 286, 118, 68, "table"),
            Obj("Bed", 700, 352, 128, 84, "bed", interactable=False),
            Obj("Plant", 854, 140, 46, 74, "plant", interactable=False),
            Obj("Bookshelf", 832, 340, 62, 110, "bookshelf", interactable=False),
            Obj("Rug", 360, 392, 196, 100, "rug", interactable=False, solid=False),
            Obj("Lamp", 596, 364, 36, 72, "lamp", interactable=False),
        ]
        work = Room("Office", 34, 26, (78, 86, 98), (42, 50, 64), (122, 170, 220))
        work.objects += [
            Obj("Work Door", 486, 48, 78, 44, "door"),
            Obj("Reception Desk", 168, 182, 120, 62, "desk", interactable=False),
            Obj("Meeting Table", 630, 210, 132, 68, "table", interactable=False),
            Obj("Bookshelf", 804, 126, 62, 110, "bookshelf", interactable=False),
            Obj("Plant", 130, 430, 46, 74, "plant", interactable=False),
            Obj("Lamp", 892, 384, 36, 72, "lamp", interactable=False),
            Obj("Rug", 396, 362, 220, 98, "rug", interactable=False, solid=False),
        ]
        work.npcs += [
            NPC("Boss", 510, 220, (170, 64, 64), (190, 84, 84)),
            NPC("Coworker", 300, 330, (65, 125, 190), (85, 145, 210)),
        ]
        therapy = Room("Therapist's Office", 28, 24, (92, 108, 96), (52, 72, 60), (128, 180, 146))
        therapy.objects += [
            Obj("Couch", 180, 286, 132, 70, "couch"),
            Obj("Desk", 610, 196, 128, 62, "desk", interactable=False),
            Obj("Bookshelf", 738, 110, 62, 110, "bookshelf", interactable=False),
            Obj("Plant", 148, 126, 46, 74, "plant", interactable=False),
            Obj("Rug", 336, 332, 220, 110, "rug", interactable=False, solid=False),
            Obj("Lamp", 566, 314, 36, 72, "lamp", interactable=False),
        ]
        therapy.npcs += [NPC("Therapist", 530, 266, (130, 178, 135), (150, 198, 155))]
        self.rooms = {"home": home, "work": work, "therapy": therapy}

    def _set_room(self, name, px=300, py=380):
        self.room_name = name
        self.room = self.rooms[name]
        self.player.x = float(px)
        self.player.y = float(py)
        self.camera = Camera(self.room.pw, self.room.ph)
        self.fader.fade_in()

    def _objective_text(self):
        if not self.current_task:
            return ""
        return self.current_task["prompt"]

    def _target_entity(self):
        if not self.current_task:
            return None
        return self.room.find_target(self.current_task["target"])

    def _run_event(self, idx):
        if idx >= len(STORY):
            self.state = ST_ENDING
            self.ending_ready = True
            return
        ev = STORY[idx]
        kind = ev["type"]
        # This is the story dispatcher: each event decides what system wakes up next.
        if kind == "dlg":
            self.current_task = None
            self.dlg.start(ev["lines"], on_complete=self._advance)
        elif kind == "room":
            self.current_task = None

            def do_room():
                self._set_room(ev["room"], ev["px"], ev["py"])
                self.state = ST_OVERWORLD
                self._advance()

            self.fader.fade_out(do_room)
        elif kind == "task":
            self.current_task = {"target": ev["target"], "prompt": ev["prompt"]}
            self.state = ST_OVERWORLD
        elif kind == "mg_wash":
            self.current_task = None
            variant = ev["variant"]
            self.wash_stage[variant] += 1
            self.minigame = WashMinigame(self.fb, self.ft, self.settings, variant, self.wash_stage[variant])
            self.state = ST_MINIGAME
        elif kind == "mg_door":
            self.current_task = None
            self.minigame = DoorMinigame(self.fb, self.ft, self.settings, self.anxiety)
            self.state = ST_MINIGAME
        elif kind == "mg_eat":
            self.current_task = None
            self.minigame = CatFightMinigame(self.fb, self.ft, self.settings, self.anxiety)
            self.state = ST_MINIGAME
        elif kind == "mg_therapy":
            self.current_task = None
            self.minigame = TherapyMinigame(self.fb, self.ft, self.settings)
            self.state = ST_MINIGAME
        elif kind == "mg_boss":
            self.current_task = None
            self.minigame = BossMinigame(self.fb, self.ft, self.settings)
            self.state = ST_MINIGAME
        elif kind == "end":
            self.current_task = None
            self.state = ST_ENDING
            self.ending_ready = True

    def _advance(self):
        self.ev_idx += 1
        total = max(1, len(STORY) - 1)
        self.anxiety = max(12, 100 - int((self.ev_idx / total) * 92))
        self._run_event(self.ev_idx)

    def _end_minigame(self):
        self.minigame = None
        self.state = ST_OVERWORLD
        self._advance()

    def _interact(self):
        if self.dlg.active or self.minigame:
            return
        player_rect = self.player.rect
        if self.current_task:
            if self.room_name == "work" and self.current_task["target"] == "Work Door":
                boss = self.room.find_target("Boss")
                if boss and boss.talk_rect.colliderect(player_rect):
                    # Getting caught by the boss skips the door minigame and jumps
                    # straight into the confrontation sequence.
                    self.ev_idx = 14
                    total = max(1, len(STORY) - 1)
                    self.anxiety = max(12, 100 - int((15 / total) * 92))
                    self._run_event(15)
                    return
            # When a story task is active, only the target interaction advances the plot.
            target = self._target_entity()
            if not target:
                self._advance()
                return
            target_rect = target.talk_rect if isinstance(target, NPC) else target.near_rect
            if target_rect.colliderect(player_rect):
                self._advance()
            return
        for npc in self.room.npcs:
            if npc.talk_rect.colliderect(player_rect):
                self._advance()
                return
        for obj in self.room.objects:
            if obj.interactable and obj.near_rect.colliderect(player_rect):
                self._advance()
                return

    def _draw_target_pointer(self):
        if not self.settings["guided_mode"] or not self.current_task:
            return
        target = self._target_entity()
        if not target:
            return
        cx, cy = self.camera.xi, self.camera.yi
        if isinstance(target, NPC):
            tx = target.x - cx
            ty = target.y - cy - target.size // 2 - 42
        else:
            tx = target.x + target.w // 2 - cx
            ty = target.y - cy - 42
        if 12 <= tx <= SCREEN_W - 12 and 12 <= ty <= SCREEN_H - 12:
            return
        # If the target is off-screen, clamp a pointer to the screen edge instead.
        tx = clamp(tx, 24, SCREEN_W - 24)
        ty = clamp(ty, 24, SCREEN_H - 24)
        pygame.draw.circle(self.screen, ACCENT, (int(tx), int(ty)), 18)
        pygame.draw.circle(self.screen, DARK, (int(tx), int(ty)), 18, 2)
        pygame.draw.polygon(self.screen, DARK, [(tx, ty - 8), (tx - 7, ty + 5), (tx + 7, ty + 5)])

    def _draw_world_entities(self, surf, cx, cy, highlight):
        drawables = []
        for obj in self.room.objects:
            drawables.append((obj.draw_layer, 0, obj))
        for npc in self.room.npcs:
            drawables.append((npc.draw_layer, 1, npc))
        drawables.sort(key=lambda item: (item[0], item[1]))
        player_layer = self.player.rect.bottom
        player_drawn = False
        # Draw entities by their feet so the player can pass behind taller props.
        for layer, kind, entity in drawables:
            if not player_drawn and layer > player_layer:
                self.player.draw(surf, cx, cy)
                player_drawn = True
            if kind == 0:
                nearby = entity.interactable and entity.near_rect.colliderect(self.player.rect)
                entity.draw(surf, cx, cy, self.fsm, highlight=(entity.name == highlight), prompt=nearby)
            else:
                nearby = entity.talk_rect.colliderect(self.player.rect)
                entity.draw(surf, cx, cy, self.fsm, highlight=(entity.name == highlight))
                if nearby:
                    lbl = self.fsm.render("[E] talk", True, ACCENT)
                    sx = entity.x - cx - lbl.get_width() // 2
                    sy = entity.y - cy - entity.size // 2 - 38
                    draw_box(surf, (0, 0, 0, 165), (sx - 4, sy - 2, lbl.get_width() + 8, lbl.get_height() + 4), 4)
                    surf.blit(lbl, (sx, sy))
        if not player_drawn:
            self.player.draw(surf, cx, cy)

    def _draw_office_pressure(self, surf, cx, cy):
        if self.room_name != "work":
            return
        center = (int(self.player.x - cx), int(self.player.y - cy - 10))
        stealth_mode = self.current_task and self.current_task["target"] == "Work Door"
        draw_vignette(surf, center, 170 if stealth_mode else 220, 118 if stealth_mode else 72)
        if not stealth_mode:
            return
        boss = self.room.find_target("Boss")
        if not boss:
            return
        bx = int(boss.x - cx)
        by = int(boss.y - cy + 4)
        cone = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        pygame.draw.polygon(cone, (120, 28, 34, 78), [(bx, by), (bx - 180, by + 225), (bx + 180, by + 225)])
        surf.blit(cone, (0, 0))
        hint = self.fsm.render("Stay low. Circle around him before you touch the door.", True, (255, 224, 224))
        draw_box(surf, (16, 10, 20, 190), (SCREEN_W // 2 - 220, 104, 440, 30), 8)
        surf.blit(hint, (SCREEN_W // 2 - hint.get_width() // 2, 110))

    def _reset_to_title(self):
        self.state = ST_TITLE
        self.ev_idx = 0
        self.anxiety = 100
        self.minigame = None
        self.current_task = None
        self.ending_ready = False
        self.particles.clear()
        self.wash_stage = {"pop": 0, "scrub": 0, "rhythm": 0}
        self._set_room("home")

    def run(self):
        # Main loop: read input, update the active system, then draw one frame.
        while True:
            dt = self.clock.tick(FPS)
            self.tick += dt
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()

                if self.settings_overlay.handle_event(ev):
                    continue

                if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                    if self.settings_overlay.open:
                        self.settings_overlay.open = False
                    else:
                        pygame.quit()
                        sys.exit()

                if self.state == ST_TITLE:
                    if ev.type == pygame.KEYDOWN and ev.key == pygame.K_RETURN:
                        self.state = ST_OVERWORLD
                        self.fader.fade_in()
                        self.ev_idx = 0
                        self._run_event(0)

                elif self.state == ST_OVERWORLD:
                    if ev.type == pygame.KEYDOWN and ev.key in (pygame.K_RETURN, pygame.K_e, pygame.K_SPACE):
                        if self.dlg.active:
                            self.dlg.advance()
                        else:
                            self._interact()

                elif self.state == ST_MINIGAME and self.minigame:
                    if ev.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN, pygame.MOUSEMOTION):
                        self.minigame.handle_event(ev)

                elif self.state == ST_ENDING:
                    if ev.type == pygame.KEYDOWN and ev.key == pygame.K_RETURN:
                        self._reset_to_title()

            if not self.settings_overlay.open:
                if self.state == ST_OVERWORLD:
                    if not self.dlg.active:
                        keys = pygame.key.get_pressed()
                        dx = (keys[pygame.K_RIGHT] or keys[pygame.K_d]) - (keys[pygame.K_LEFT] or keys[pygame.K_a])
                        dy = (keys[pygame.K_DOWN] or keys[pygame.K_s]) - (keys[pygame.K_UP] or keys[pygame.K_w])
                        self.player.move(dx, dy, dt, self.room.collision_rects)
                        if self.anxiety > 42 and not self.settings["reduce_motion"] and random.random() < 0.05:
                            self.particles.append(Particle(self.player.x, self.player.y - 20, (80, 200, 120)))
                    self.player.update(dt)
                    self.camera.update(self.player.x, self.player.y)
                    self.dlg.update(dt)
                    for npc in self.room.npcs:
                        npc.update(dt, self.settings["reduce_motion"])
                    for obj in self.room.objects:
                        obj.update(dt, self.settings["reduce_motion"])
                    self.particles = [p for p in self.particles if not p.dead()]
                    for p in self.particles:
                        p.update(dt)
                elif self.state == ST_MINIGAME and self.minigame:
                    self.minigame.update(dt)
                    if self.minigame.done:
                        self._end_minigame()
                self.fader.update(dt)

            self.screen.fill(DARK)
            if self.state == ST_TITLE:
                draw_title(self.screen, self.ft, self.fb, self.tick, self.settings)
            elif self.state == ST_OVERWORLD:
                cx, cy = self.camera.xi, self.camera.yi
                highlight = self.current_task["target"] if self.current_task and self.settings["guided_mode"] else None
                self.room.draw(self.screen, cx, cy, self.fsm, self.player.rect, highlight_target=highlight, draw_entities=False)
                for p in self.particles:
                    p.draw(self.screen, cx, cy)
                self._draw_world_entities(self.screen, cx, cy, highlight)
                self._draw_office_pressure(self.screen, cx, cy)
                draw_hud(self.screen, self.anxiety, self.room.name, self.fsm, self._objective_text(), self.settings)
                self._draw_target_pointer()
                self.dlg.draw(self.screen)
            elif self.state == ST_MINIGAME and self.minigame:
                mg = self.minigame
                if isinstance(mg, WashMinigame):
                    mg.draw(self.screen)
                elif isinstance(mg, DoorMinigame):
                    mg.draw(self.screen, self.fsm)
                elif isinstance(mg, CatFightMinigame):
                    mg.draw(self.screen, self.fsm)
                elif isinstance(mg, TherapyMinigame):
                    mg.draw(self.screen)
                elif isinstance(mg, BossMinigame):
                    mg.draw(self.screen)
                if hasattr(mg, "draw_flow_overlay"):
                    mg.draw_flow_overlay(self.screen)
            elif self.state == ST_ENDING:
                draw_ending(self.screen, self.ft, self.fb, self.tick)

            self.settings_overlay.draw_button(self.screen, self.fsm)
            if self.settings_overlay.open:
                self.settings_overlay.draw(self.screen, self.ft, self.fb)
            self.fader.draw(self.screen)
            pygame.display.flip()


if __name__ == "__main__":
    game = Game()
    game.run()
