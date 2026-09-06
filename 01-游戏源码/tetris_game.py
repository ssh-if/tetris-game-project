"""
俄罗斯方块 - 主程序（Pygame 渲染）
==================================
运行: python tetris_game.py
依赖: pip install pygame

操作:
  方向键左/右 : 移动
  方向键下   : 软降
  方向键上 / X : 顺时针旋转
  空格       : 硬降
  P          : 暂停
  R          : 重新开始
  Esc        : 退出
"""

import os
import sys
import json
import time
import pygame

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tetris_core import Tetris, GameOver, COLOR_INDEX, COLS, ROWS

# ---- 配置 ----
CELL = 28                       # 每格像素
BOARD_W = COLS * CELL
BOARD_H = ROWS * CELL
SIDEBAR_W = 180
HUD_H = 50
WIN_W = BOARD_W + SIDEBAR_W + 40
WIN_H = BOARD_H + HUD_H + 20
FPS = 60

# 方块颜色 (索引 1~7)
COLORS = [
    (0, 0, 0),
    (0, 200, 220),    # 1 I - 青
    (220, 220, 0),    # 2 O - 黄
    (180, 0, 220),    # 3 T - 紫
    (0, 220, 80),     # 4 S - 绿
    (220, 40, 40),    # 5 Z - 红
    (40, 80, 220),    # 6 J - 蓝
    (240, 140, 0),    # 7 L - 橙
]

COLOR_BG = (18, 20, 28)
COLOR_GRID = (38, 44, 58)
COLOR_PANEL = (28, 32, 44)
COLOR_TEXT = (235, 238, 245)
COLOR_DIM = (140, 150, 165)
COLOR_GHOST = (255, 255, 255)
COLOR_ACCENT = (90, 180, 240)

HIGHSCORE_FILE = os.path.join(os.path.dirname(__file__), "highscore.json")
BOARD_X = 20
BOARD_Y = HUD_H + 10


def load_highscore():
    if os.path.exists(HIGHSCORE_FILE):
        try:
            with open(HIGHSCORE_FILE, "r", encoding="utf-8") as f:
                return json.load(f).get("highscore", 0)
        except Exception:
            return 0
    return 0


def save_highscore(score):
    try:
        with open(HIGHSCORE_FILE, "w", encoding="utf-8") as f:
            json.dump({"highscore": score}, f)
    except Exception:
        pass


def draw_cell(surface, x, y, color, ghost=False):
    px = BOARD_X + x * CELL
    py = BOARD_Y + y * CELL
    if ghost:
        pygame.draw.rect(surface, color, (px + 2, py + 2, CELL - 4, CELL - 4),
                         width=2, border_radius=3)
        return
    pygame.draw.rect(surface, color, (px + 1, py + 1, CELL - 2, CELL - 2),
                     border_radius=3)
    # 高光
    pygame.draw.rect(surface, (255, 255, 255), (px + 2, py + 2, CELL - 4, 4),
                     border_radius=2)


def draw_grid(surface):
    for x in range(COLS + 1):
        px = BOARD_X + x * CELL
        pygame.draw.line(surface, COLOR_GRID, (px, BOARD_Y), (px, BOARD_Y + BOARD_H))
    for y in range(ROWS + 1):
        py = BOARD_Y + y * CELL
        pygame.draw.line(surface, COLOR_GRID, (BOARD_X, py), (BOARD_X + BOARD_W, py))


def draw_board(surface, game):
    # 已锁方块
    for y, row in enumerate(game.board):
        for x, c in enumerate(row):
            if c:
                draw_cell(surface, x, y, COLORS[c])
    # 幽灵方块
    gy = game.ghost_y()
    for dx, dy in game.piece.cells:
        gx, gpy = game.piece.x + dx, gy + dy
        if gpy >= 0:
            draw_cell(surface, gx, gpy, COLOR_GHOST, ghost=True)
    # 活动方块
    for ax, ay in game.piece.absolute_cells():
        if ay >= 0:
            draw_cell(surface, ax, ay, COLORS[game.piece.color])


def draw_next_piece(surface, game, font):
    panel_x = BOARD_X + BOARD_W + 20
    panel_y = BOARD_Y
    pygame.draw.rect(surface, COLOR_PANEL,
                     (panel_x, panel_y, SIDEBAR_W, 120), border_radius=8)
    label = font.render("下一个", True, COLOR_DIM)
    surface.blit(label, (panel_x + 12, panel_y + 8))
    # 预览方块
    from tetris_core import SHAPES
    cells = SHAPES[game.next_piece]
    color = COLORS[COLOR_INDEX[game.next_piece]]
    w = max(c[0] for c in cells) + 1
    h = max(c[1] for c in cells) + 1
    size = 18
    ox = panel_x + (SIDEBAR_W - w * size) // 2
    oy = panel_y + 40 + (4 - h) * size // 2
    for dx, dy in cells:
        px = ox + dx * size
        py = oy + dy * size
        pygame.draw.rect(surface, color, (px, py, size - 2, size - 2), border_radius=2)


def draw_hud(surface, game, font, small_font, highscore, state):
    pygame.draw.rect(surface, COLOR_PANEL, (0, 0, WIN_W, HUD_H))
    score = font.render(f"得分 {game.score}", True, COLOR_TEXT)
    lines = font.render(f"消行 {game.lines}", True, COLOR_ACCENT)
    level = font.render(f"等级 {game.level}", True, COLOR_TEXT)
    hi = small_font.render(f"最高 {highscore}", True, COLOR_DIM)
    surface.blit(score, (20, 14))
    surface.blit(lines, (170, 14))
    surface.blit(level, (290, 14))
    surface.blit(hi, (WIN_W - hi.get_width() - 20, 18))
    if state == "paused":
        msg = font.render("已暂停  按 P 继续", True, COLOR_ACCENT)
        surface.blit(msg, (WIN_W // 2 - msg.get_width() // 2, 14))
    elif state == "ready":
        msg = font.render("按空格开始  方向键移动/旋转", True, COLOR_ACCENT)
        surface.blit(msg, (WIN_W // 2 - msg.get_width() // 2, 14))


def draw_controls(surface, small_font):
    panel_x = BOARD_X + BOARD_W + 20
    panel_y = BOARD_Y + 140
    pygame.draw.rect(surface, COLOR_PANEL,
                     (panel_x, panel_y, SIDEBAR_W, 200), border_radius=8)
    label = small_font.render("操作说明", True, COLOR_DIM)
    surface.blit(label, (panel_x + 12, panel_y + 8))
    tips = [
        "← →   左右移动",
        "↓      软降",
        "↑ / X  旋转",
        "空格   硬降",
        "P      暂停",
        "R      重新开始",
        "Esc    退出",
    ]
    for i, t in enumerate(tips):
        surface.blit(small_font.render(t, True, COLOR_TEXT),
                     (panel_x + 12, panel_y + 32 + i * 22))


def draw_game_over(surface, game, font, big_font, highscore):
    overlay = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 180))
    surface.blit(overlay, (0, 0))
    title = big_font.render("游戏结束", True, (230, 80, 80))
    score = font.render(f"本局得分: {game.score}", True, COLOR_TEXT)
    lines = font.render(f"消行: {game.lines}  等级: {game.level}", True, COLOR_TEXT)
    hi = font.render(f"最高分: {highscore}", True, COLOR_ACCENT)
    tip = font.render("按 R 重新开始 / Esc 退出", True, COLOR_DIM)
    cx = WIN_W // 2
    cy = WIN_H // 2
    surface.blit(title, (cx - title.get_width() // 2, cy - 90))
    surface.blit(score, (cx - score.get_width() // 2, cy - 30))
    surface.blit(lines, (cx - lines.get_width() // 2, cy))
    surface.blit(hi, (cx - hi.get_width() // 2, cy + 30))
    surface.blit(tip, (cx - tip.get_width() // 2, cy + 70))


def main():
    pygame.init()
    pygame.display.set_caption("俄罗斯方块 Tetris")
    screen = pygame.display.set_mode((WIN_W, WIN_H))
    clock = pygame.time.Clock()

    font = pygame.font.SysFont("microsoftyahei,arial", 20)
    big_font = pygame.font.SysFont("microsoftyahei,arial", 40, bold=True)
    small_font = pygame.font.SysFont("microsoftyahei,arial", 14)

    highscore = load_highscore()
    game = Tetris(seed=None)
    state = "ready"       # ready / running / paused / over
    last_drop = time.time()

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0

        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            elif ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    running = False
                elif ev.key == pygame.K_SPACE:
                    if state == "ready":
                        state = "running"
                        last_drop = time.time()
                    elif state == "over":
                        game = Tetris(seed=None)
                        state = "ready"
                    elif state == "running":
                        game.hard_drop()
                elif ev.key == pygame.K_r and state == "over":
                    game = Tetris(seed=None)
                    state = "ready"
                elif ev.key == pygame.K_p:
                    if state == "running":
                        state = "paused"
                    elif state == "paused":
                        state = "running"
                        last_drop = time.time()
                elif state == "running":
                    if ev.key in (pygame.K_LEFT, pygame.K_a):
                        game.move_left()
                    elif ev.key in (pygame.K_RIGHT, pygame.K_d):
                        game.move_right()
                    elif ev.key in (pygame.K_DOWN, pygame.K_s):
                        game.move_down()
                    elif ev.key in (pygame.K_UP, pygame.K_x, pygame.K_w):
                        game.rotate()

        # 自动下落
        if state == "running":
            interval = 1.0 / game.speed
            if time.time() - last_drop >= interval:
                last_drop = time.time()
                try:
                    if not game.move_down():
                        pass  # move_down 内部已锁定并生成新块
                except GameOver:
                    state = "over"
                    if game.score > highscore:
                        highscore = game.score
                        save_highscore(highscore)

        # 渲染
        screen.fill(COLOR_BG)
        draw_grid(screen)
        draw_board(screen, game)
        draw_next_piece(screen, game, font)
        draw_controls(surface=screen, small_font=small_font)
        draw_hud(screen, game, font, small_font, highscore, state)
        if state == "over":
            draw_game_over(screen, game, font, big_font, highscore)
        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
