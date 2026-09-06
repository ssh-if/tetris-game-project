"""
俄罗斯方块 - 核心逻辑模块
========================
与渲染层解耦，不依赖任何图形库，可由 pytest 在无头环境直接驱动。

坐标约定：
- 棋盘 board[rows][cols]，board[y][x]，y 向下递增，x 向右递增
- 空槽为 0，已锁定格子为颜色编号 (1~7)
- 活动方块以基准点 (x, y) + 相对偏移 cells 表示
"""

from __future__ import annotations
import random
from copy import deepcopy


# 棋盘尺寸
COLS = 10
ROWS = 20

# 方块类型与其初始形状（相对坐标，4 格）
SHAPES = {
    "I": [(0, 0), (1, 0), (2, 0), (3, 0)],
    "O": [(0, 0), (1, 0), (0, 1), (1, 1)],
    "T": [(0, 0), (1, 0), (2, 0), (1, 1)],
    "S": [(1, 0), (2, 0), (0, 1), (1, 1)],
    "Z": [(0, 0), (1, 0), (1, 1), (2, 1)],
    "J": [(0, 0), (0, 1), (1, 1), (2, 1)],
    "L": [(2, 0), (0, 1), (1, 1), (2, 1)],
}

# 方块颜色（仅作为编号映射，渲染层自行配色）
COLOR_INDEX = {k: i + 1 for i, k in enumerate(SHAPES)}

# 消行得分表（按消行数 1/2/3/4）
LINE_SCORES = [0, 100, 300, 500, 800]

# 每升一级所需消行数
LINES_PER_LEVEL = 10

# 基础下落速度（格/秒）随等级递增
BASE_SPEED = 1.0
SPEED_STEP = 0.8
MAX_SPEED = 20.0


def rotate_cells(cells):
    """对一组相对坐标顺时针旋转 90° 并归一化到非负坐标"""
    rotated = [(y, -x) for x, y in cells]
    min_x = min(c[0] for c in rotated)
    min_y = min(c[1] for c in rotated)
    return [(x - min_x, y - min_y) for x, y in rotated]


class Piece:
    """活动方块"""

    def __init__(self, shape: str, x: int = 3, y: int = 0):
        if shape not in SHAPES:
            raise ValueError(f"未知方块类型: {shape}")
        self.shape = shape
        self.rotation = 0
        self.cells = list(SHAPES[shape])
        self.x = x
        self.y = y

    @property
    def color(self):
        return COLOR_INDEX[self.shape]

    def rotated_cells(self):
        """返回顺时针旋转一次后的相对坐标（不改变自身状态）"""
        return rotate_cells(self.cells)

    def rotate(self):
        """执行顺时针旋转一次"""
        self.cells = rotate_cells(self.cells)
        self.rotation = (self.rotation + 1) % 4

    def absolute_cells(self, cells=None):
        """返回绝对棋盘坐标 [(x,y), ...]"""
        cells = cells if cells is not None else self.cells
        return [(self.x + dx, self.y + dy) for dx, dy in cells]


class Bag:
    """7-bag 随机发生器：每 7 个方块包含全部 7 种，保证公平"""

    def __init__(self, seed=None):
        self._rng = random.Random(seed)
        self._bag = []
        self._refill()

    def _refill(self):
        bag = list(SHAPES.keys())
        self._rng.shuffle(bag)
        self._bag = bag

    def next(self) -> str:
        if not self._bag:
            self._refill()
        return self._bag.pop()

    def peek(self) -> str:
        if not self._bag:
            self._refill()
        return self._bag[-1]


class GameOver(Exception):
    def __init__(self, reason="TOPOUT", score=0, lines=0, level=1):
        super().__init__(reason)
        self.reason = reason
        self.score = score
        self.lines = lines
        self.level = level


class Tetris:
    """俄罗斯方块核心逻辑"""

    def __init__(self, cols=COLS, rows=ROWS, seed=None):
        if cols < 4 or rows < 4:
            raise ValueError("棋盘至少 4x4")
        self.cols = cols
        self.rows = rows
        self.board = [[0] * cols for _ in range(rows)]
        self._bag = Bag(seed=seed)

        self.score = 0
        self.lines = 0
        self.level = 1
        self.combo = -1  # 连续消行连击，-1 表示未激活

        self.piece = None
        self.next_piece = self._bag.next()
        self._spawn()
        self._over = False
        self._over_reason = None

    # ---- 生成与结束 ----
    def _spawn(self):
        shape = self.next_piece
        self.next_piece = self._bag.next()
        self.piece = Piece(shape, x=self.cols // 2 - 2, y=0)
        # 若生成即碰撞 -> 游戏结束
        if self._collides(self.piece):
            self._over = True
            self._over_reason = "TOPOUT"
            raise GameOver("TOPOUT", self.score, self.lines, self.level)

    # ---- 碰撞检测 ----
    def _collides(self, piece: Piece, cells=None) -> bool:
        """检测给定 cells（默认当前）是否与墙/底/已锁方块碰撞"""
        for ax, ay in piece.absolute_cells(cells):
            if ax < 0 or ax >= self.cols or ay >= self.rows:
                return True
            if ay >= 0 and self.board[ay][ax] != 0:
                return True
        return False

    # ---- 操作 ----
    def move_left(self) -> bool:
        if self._over:
            return False
        self.piece.x -= 1
        if self._collides(self.piece):
            self.piece.x += 1
            return False
        return True

    def move_right(self) -> bool:
        if self._over:
            return False
        self.piece.x += 1
        if self._collides(self.piece):
            self.piece.x -= 1
            return False
        return True

    def move_down(self) -> bool:
        """软降一格，返回是否成功（False 表示需锁定）"""
        if self._over:
            return False
        self.piece.y += 1
        if self._collides(self.piece):
            self.piece.y -= 1
            self._lock()
            return False
        return True

    def rotate(self) -> bool:
        """顺时针旋转，含简单 wall-kick（左/右各试 1 格）"""
        if self._over:
            return False
        if self.piece.shape == "O":
            return True
        rotated = self.piece.rotated_cells()
        for dx in (0, -1, 1, -2, 2):
            self.piece.x += dx
            if not self._collides(self.piece, cells=rotated):
                self.piece.cells = rotated
                self.piece.rotation = (self.piece.rotation + 1) % 4
                return True
            self.piece.x -= dx
        return False

    def hard_drop(self) -> int:
        """硬降到底并锁定，返回下落格数"""
        if self._over:
            return 0
        drop = 0
        while not self._collides(self.piece):
            self.piece.y += 1
            drop += 1
        self.piece.y -= 1  # 回退到合法位置
        drop -= 1
        self.score += drop * 2  # 硬降得分：每格 2 分
        self._lock()
        return drop

    def ghost_y(self) -> int:
        """幽灵方块的 y 坐标（硬降预览位置）"""
        y = self.piece.y
        while True:
            test = Piece(self.piece.shape)
            test.cells = list(self.piece.cells)
            test.x = self.piece.x
            test.y = y + 1
            if self._collides(test):
                return y
            y += 1

    # ---- 锁定与消行 ----
    def _lock(self):
        """将当前方块写入棋盘，消行，计分，生成新方块"""
        for ax, ay in self.piece.absolute_cells():
            if 0 <= ay < self.rows and 0 <= ax < self.cols:
                self.board[ay][ax] = self.piece.color
        cleared = self._clear_lines()
        if cleared > 0:
            self.lines += cleared
            self.combo += 1
            combo_bonus = 50 * self.combo * self.level if self.combo > 0 else 0
            self.score += LINE_SCORES[cleared] * self.level + combo_bonus
            # 升级
            new_level = self.lines // LINES_PER_LEVEL + 1
            if new_level > self.level:
                self.level = new_level
        else:
            self.combo = -1
        self._spawn()

    def _clear_lines(self) -> int:
        """消除满行并将上方下移，返回消除行数"""
        cleared = 0
        new_board = [row for row in self.board if any(c == 0 for c in row)]
        cleared = self.rows - len(new_board)
        for _ in range(cleared):
            new_board.insert(0, [0] * self.cols)
        self.board = new_board
        return cleared

    # ---- 状态查询 ----
    @property
    def is_over(self):
        return self._over

    @property
    def over_reason(self):
        return self._over_reason

    @property
    def speed(self):
        """当前下落速度（格/秒）"""
        return min(BASE_SPEED + (self.level - 1) * SPEED_STEP, MAX_SPEED)

    def snapshot(self):
        return {
            "board": deepcopy(self.board),
            "piece": {
                "shape": self.piece.shape,
                "cells": list(self.piece.cells),
                "x": self.piece.x,
                "y": self.piece.y,
                "color": self.piece.color,
            },
            "next": self.next_piece,
            "score": self.score,
            "lines": self.lines,
            "level": self.level,
            "speed": self.speed,
            "combo": self.combo,
            "is_over": self._over,
            "over_reason": self._over_reason,
        }
