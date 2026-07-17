"""
ピース管理モジュール
ピースの定義、描画、ドラッグ操作を担当
"""

import pygame


class Piece:
    """パズルピースを管理するクラス"""
    
    def __init__(self, piece_id, cells, color, cell_size=50):
        """
        Args:
            piece_id: ピースの一意識別子
            cells: ピースを構成するセル座標リスト [(row, col), ...]
                   ローカル座標（左上が(0,0)）
            color: ピースの色 (R, G, B)
            cell_size: 1セルのピクセルサイズ
        """
        self.piece_id = piece_id
        self.cells = cells  # ローカル座標
        self.color = color
        self.cell_size = cell_size
        
        # 現在位置（ピクセル座標、ピースの左上）
        self.x = 0
        self.y = 0
        
        # グリッド上に配置済みかどうか
        self.placed = False
        self.placed_row = None
        self.placed_col = None
        
        # ドラッグ中かどうか
        self.dragging = False
        self.drag_offset_x = 0
        self.drag_offset_y = 0
        
        # バウンディングボックス計算
        self._calc_bounds()
    
    def _calc_bounds(self):
        """ピースのバウンディングボックスを計算"""
        if not self.cells:
            self.width = 0
            self.height = 0
            return
        
        min_row = min(c[0] for c in self.cells)
        max_row = max(c[0] for c in self.cells)
        min_col = min(c[1] for c in self.cells)
        max_col = max(c[1] for c in self.cells)
        
        self.width = (max_col - min_col + 1) * self.cell_size
        self.height = (max_row - min_row + 1) * self.cell_size
    
    def set_position(self, x, y):
        """ピクセル座標で位置を設定"""
        self.x = x
        self.y = y
    
    def get_world_cells(self):
        """現在位置でのワールド座標セルリストを取得"""
        if self.placed and self.placed_row is not None:
            return [(self.placed_row + r, self.placed_col + c) for r, c in self.cells]
        return []
    
    def contains_point(self, px, py):
        """指定ピクセル座標がピース上にあるか判定"""
        # クリック判定を緩くするためのマージン
        # 配置済みの場合は誤操作防止のため少し狭く(10)、未配置は掴みやすく広く(20)
        margin = 10 if self.placed else 20
        
        for row, col in self.cells:
            cell_x = self.x + col * self.cell_size
            cell_y = self.y + row * self.cell_size
            
            # 判定範囲を少し広げる
            if (cell_x - margin <= px < cell_x + self.cell_size + margin and
                cell_y - margin <= py < cell_y + self.cell_size + margin):
                return True
        return False
    
    def start_drag(self, mouse_x, mouse_y):
        """ドラッグ開始"""
        self.dragging = True
        self.drag_offset_x = self.x - mouse_x
        self.drag_offset_y = self.y - mouse_y
    
    def update_drag(self, mouse_x, mouse_y):
        """ドラッグ中の位置更新"""
        if self.dragging:
            self.x = mouse_x + self.drag_offset_x
            self.y = mouse_y + self.drag_offset_y
    
    def end_drag(self):
        """ドラッグ終了"""
        self.dragging = False
    
    def try_place(self, grid):
        """グリッドに配置を試みる（広めの吸着範囲）"""
        # ピースの最初のセルの位置からグリッド位置を推定
        first_cell = self.cells[0]
        cell_x = self.x + first_cell[1] * self.cell_size + self.cell_size // 2
        cell_y = self.y + first_cell[0] * self.cell_size + self.cell_size // 2
        
        base_row, base_col = grid.pixel_to_cell(cell_x, cell_y)
        target_row = base_row - first_cell[0]
        target_col = base_col - first_cell[1]
        
        # スナップ吸着範囲を広げるため、周囲のセルも候補としてチェック
        # 優先度: 中央 → 上下左右 → 斜め
        offsets = [
            (0, 0),   # 中央（最優先）
            (0, -1), (0, 1), (-1, 0), (1, 0),  # 上下左右
            (-1, -1), (-1, 1), (1, -1), (1, 1),  # 斜め
        ]
        
        for dr, dc in offsets:
            test_row = target_row + dr
            test_col = target_col + dc
            
            if self._can_place_at(grid, test_row, test_col):
                # 配置成功
                self.placed = True
                self.placed_row = test_row
                self.placed_col = test_col
                
                # グリッドに占有を記録
                for r, c in self.cells:
                    grid.occupy(test_row + r, test_col + c, self.piece_id)
                
                # 位置をスナップ
                self.x, self.y = grid.cell_to_pixel(test_row, test_col)
                
                return True
        
        return False
    
    def _can_place_at(self, grid, target_row, target_col):
        """指定位置に配置可能か判定"""
        for r, c in self.cells:
            world_row = target_row + r
            world_col = target_col + c
            
            if not grid.is_valid_cell(world_row, world_col):
                return False
            if grid.is_occupied(world_row, world_col):
                return False
        return True
    
    def remove_from_grid(self, grid):
        """グリッドから取り除く"""
        if self.placed:
            grid.release(self.piece_id)
            self.placed = False
            self.placed_row = None
            self.placed_col = None
    
    def draw(self, screen):
        """ピースを描画（最適化版）"""
        # 配色は配置状態によって変更（事前計算）
        if self.placed:
            # 配置済みは少し明るく（tuple生成を削減）
            draw_color = (
                min(255, self.color[0] + 30),
                min(255, self.color[1] + 30),
                min(255, self.color[2] + 30)
            )
            border_color = (
                max(0, draw_color[0] - 40),
                max(0, draw_color[1] - 40),
                max(0, draw_color[2] - 40)
            )
            highlight = (
                min(255, draw_color[0] + 30),
                min(255, draw_color[1] + 30),
                min(255, draw_color[2] + 30)
            )
        else:
            draw_color = self.color
            border_color = (
                max(0, self.color[0] - 40),
                max(0, self.color[1] - 40),
                max(0, self.color[2] - 40)
            )
            highlight = (
                min(255, self.color[0] + 30),
                min(255, self.color[1] + 30),
                min(255, self.color[2] + 30)
            )
        
        # ドラッグ中の視覚フィードバック（強調表示）
        if self.dragging:
            # ドラッグ中は少し明るく、枠線を太く
            draw_color = (
                min(255, draw_color[0] + 40),
                min(255, draw_color[1] + 40),
                min(255, draw_color[2] + 40)
            )
            border_color = (255, 255, 255)  # 白い枠線で強調
            border_width = 4  # 太い枠線
        else:
            border_width = 3
        
        # 各セルを描画（pygame.Rect の生成を削減）
        for row, col in self.cells:
            x = self.x + col * self.cell_size
            y = self.y + row * self.cell_size
            
            # 塗りつぶし
            pygame.draw.rect(screen, draw_color, (x, y, self.cell_size, self.cell_size))
            
            # 枠線
            pygame.draw.rect(screen, border_color, (x, y, self.cell_size, self.cell_size), border_width)
            
            # 内側のハイライト
            pygame.draw.rect(screen, highlight, (x + 4, y + 4, self.cell_size - 8, self.cell_size - 8), 1)
