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
        
        # 有効セルの座標リスト
        self.valid_cells = self._extract_valid_cells()
        
        # 配置済みセル（ピースIDでマーク）
        self.occupied = {}  # {(row, col): piece_id}
    
    def _extract_valid_cells(self):
        """有効セルの座標リストを抽出"""
        cells = []
        for row in range(self.rows):
            for col in range(self.cols):
                if self.shape[row][col] == 1:
                    cells.append((row, col))
        return cells
    
    def cell_to_pixel(self, row, col):
        """セル座標をピクセル座標に変換"""
        x = self.offset_x + col * self.cell_size
        y = self.offset_y + row * self.cell_size
        return x, y
    
    def pixel_to_cell(self, x, y):
        """ピクセル座標をセル座標に変換（切り捨て）"""
        col = int((x - self.offset_x) / self.cell_size)
        row = int((y - self.offset_y) / self.cell_size)
        return row, col
    
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
