"""
グリッド管理モジュール
枠（フレーム）の定義と描画を担当
"""

import pygame


class Grid:
    """パズルの枠（フレーム）を管理するクラス"""
    
    def __init__(self, shape, cell_size=50, offset_x=100, offset_y=100):
        """
        Args:
            shape: 2D配列（1=有効セル, 0=無効セル）
            cell_size: 1セルのピクセルサイズ
            offset_x: 画面上のX座標オフセット
            offset_y: 画面上のY座標オフセット
        """
        self.shape = shape
        self.rows = len(shape)
        self.cols = len(shape[0]) if self.rows > 0 else 0
        self.cell_size = cell_size
        self.offset_x = offset_x
        self.offset_y = offset_y
        
        # 有効セルの集合（shapeから導出。毎フレームの所属判定に使うためset）
        self.valid_cells = self._extract_valid_cells()

        # 配置済みセル（ピースIDでマーク）
        self.occupied = {}  # {(row, col): piece_id}

    def _extract_valid_cells(self):
        """有効セルの座標集合を抽出"""
        cells = set()
        for row in range(self.rows):
            for col in range(self.cols):
                if self.shape[row][col] == 1:
                    cells.add((row, col))
        return cells

    def cell_to_pixel(self, row, col):
        """セル座標をピクセル座標に変換"""
        x = self.offset_x + col * self.cell_size
        y = self.offset_y + row * self.cell_size
        return x, y

    def pixel_to_cell(self, x, y):
        """
        ピクセル座標をセル座標に変換（切り下げ）

        グリッドの左/上にはみ出した座標は負のセルを返す。
        int()だと0方向に切り捨てられ、枠外のクリックが端のセル(0)に
        吸い込まれてしまうため、整数除算（切り下げ）を使う。
        """
        col = (x - self.offset_x) // self.cell_size
        row = (y - self.offset_y) // self.cell_size
        return row, col

    def set_cell(self, row, col, active):
        """
        セルの有効/無効を切り替える（エディタ用）

        shape（正）と valid_cells（導出）を一貫して更新し、
        必要に応じてshapeを拡張する
        """
        if row < 0 or col < 0:
            return

        if active:
            # shapeを必要な大きさまで拡張
            while len(self.shape) <= row:
                self.shape.append([0] * self.cols)
            for shape_row in self.shape:
                while len(shape_row) <= col:
                    shape_row.append(0)

            self.rows = len(self.shape)
            self.cols = max(len(r) for r in self.shape)

            self.shape[row][col] = 1
            self.valid_cells.add((row, col))
        else:
            if row < self.rows and col < len(self.shape[row]):
                self.shape[row][col] = 0
            self.valid_cells.discard((row, col))

    def is_valid_cell(self, row, col):
        """セルが枠内かどうか判定"""
        if 0 <= row < self.rows and 0 <= col < self.cols:
            return self.shape[row][col] == 1
        return False
    
    def is_occupied(self, row, col):
        """セルが既に占有されているか判定"""
        return (row, col) in self.occupied
    
    def occupy(self, row, col, piece_id):
        """セルを占有"""
        self.occupied[(row, col)] = piece_id
    
    def release(self, piece_id):
        """指定ピースの占有を解除（最適化版）"""
        # リスト内包表記を避けて、直接削除
        to_remove = []
        for cell, pid in self.occupied.items():
            if pid == piece_id:
                to_remove.append(cell)
        for cell in to_remove:
            del self.occupied[cell]
    
    def is_complete(self):
        """全有効セルが埋まったか判定"""
        return len(self.occupied) == len(self.valid_cells)
    
    def draw(self, screen):
        """枠を描画（最適化版：有効セルのみ描画）"""
        # 枠セル
        frame_color = (139, 90, 43)  # 木の色
        frame_border = (100, 60, 20)
        
        # 有効セルのみを描画（無効セルはスキップ）
        for row, col in self.valid_cells:
            x, y = self.cell_to_pixel(row, col)
            # pygame.Rect の生成を削減（直接タプルで描画）
            pygame.draw.rect(screen, frame_color, (x, y, self.cell_size, self.cell_size))
            pygame.draw.rect(screen, frame_border, (x, y, self.cell_size, self.cell_size), 2)
