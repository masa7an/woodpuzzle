"""
ステージエディタモジュール
ステージの編集・保存を担当（デスクトップ版のみ、Web版では無効）
"""

import os
import sys

import pygame

from src.piece import PIECE_COLORS
from src.stage_loader import StageLoader
from src.text_manager import text_manager


class StageEditor:
    """
    ステージエディタ

    セルをクリックしてピースIDを割り当て、.stageファイルとして保存する。
    グリッドやフォント、ステージの読み込みはGame側の資産を使うため、
    Gameへの参照を保持する
    """

    def __init__(self, game):
        self.game = game

        self.enabled = False
        self.cell_map = {}  # {(row, col): piece_id}
        self.page = 0       # ステージ選択ページ (0: 1-10, 1: 11-20...)

        # 編集可能な最大サイズ
        self.max_rows = 11
        self.max_cols = 11

        # A-Zまで用意しておく（自動生成ステージ対応）
        self.piece_ids = [chr(i) for i in range(ord('A'), ord('Z') + 1)]

    def _fill_cell_map(self):
        """現在のグリッドの有効セルを全て'A'で初期化"""
        self.cell_map = {cell: 'A' for cell in self.game.grid.valid_cells}

    def toggle(self):
        """エディタモード切り替え"""
        # Web版ではエディタモード無効
        if sys.platform == 'emscripten':
            return

        self.enabled = not self.enabled

        if self.enabled:
            # エディタモード開始時、グリッドを現在の正解で初期化
            self._fill_cell_map()

            stages = StageLoader.list_stages(self.game.stages_dir)
            print(text_manager.get("logs.editor_mode_on"))
            print(text_manager.get("logs.available_stages", len(stages)))
            print(text_manager.get("logs.editor_console_guide"))
        else:
            print(text_manager.get("logs.editor_mode_off"))
            # エディタ終了時に現在のステージを再ロードして変更を反映
            stage_num = self.game._current_stage_num()
            if stage_num is not None:
                self.game._load_stage(stage_num)
            else:
                self.game._load_stage1()

    def new_stage(self):
        """新規ステージを作成"""
        self._fill_cell_map()
        self.game.current_stage_id = ''
        print(text_manager.get("logs.new_stage_created"))

    def load_stage(self, stage_num):
        """指定番号のステージを読み込み"""
        stage_file = os.path.join(self.game.stages_dir, f"STAGE_{stage_num:03d}.stage")

        if not os.path.exists(stage_file):
            print(text_manager.get("logs.stage_not_found", stage_num, stage_file))
            return

        # ステージを読み込み
        try:
            stage_data = StageLoader.load_stage(stage_file)
        except Exception as e:
            print(text_manager.get("logs.load_fail", e))
            return

        self.game.current_stage_id = stage_data['stage_id']

        # グリッド形状を更新
        self.game.grid = self.game._build_grid(stage_data['grid_shape'],
                                               self.game.grid.cell_size)

        # エディタセルマップを初期化
        self._fill_cell_map()

        # ピース情報からセルマップを設定
        for piece_data in stage_data['pieces']:
            base_row, base_col = piece_data['position']
            for r, c in piece_data['cells']:
                cell = (base_row + r, base_col + c)
                if cell in self.cell_map:
                    self.cell_map[cell] = piece_data['id']

        print(text_manager.get("logs.loaded_stage",
                               self.game.current_stage_id, stage_data['name']))

    def prev_page(self):
        """ステージ選択ページを戻す"""
        self.page = max(0, self.page - 1)
        print(f"Page: {self.page + 1}")

    def next_page(self):
        """ステージ選択ページを進める"""
        self.page += 1
        print(f"Page: {self.page + 1}")

    def stage_num_for_key(self, num):
        """数字キー(1-10)を現在のページのステージ番号に変換"""
        return (self.page * 10) + num

    def click(self, pos, button):
        """エディタモードでのクリック処理"""
        row, col = self.game.grid.pixel_to_cell(*pos)

        # 中クリック: グリッドの有効/無効を切り替え
        if button == 2:
            # 最大サイズ内かチェック
            if 0 <= row < self.max_rows and 0 <= col < self.max_cols:
                if (row, col) in self.cell_map:
                    # 有効→無効
                    del self.cell_map[(row, col)]
                    self.game.grid.set_cell(row, col, False)
                else:
                    # 無効→有効
                    self.cell_map[(row, col)] = 'A'
                    self.game.grid.set_cell(row, col, True)
            return

        if (row, col) not in self.cell_map:
            return

        # 左クリック: 次のID / 右クリック: 前のID
        current_id = self.cell_map[(row, col)]
        idx = self._piece_id_index(current_id)

        if button == 1:
            idx = (idx + 1) % len(self.piece_ids)
        elif button == 3:
            idx = (idx - 1) % len(self.piece_ids)

        self.cell_map[(row, col)] = self.piece_ids[idx]

    def _piece_id_index(self, piece_id):
        """ピースIDの並び順を取得（未知のIDは末尾に登録する）"""
        if piece_id not in self.piece_ids:
            self.piece_ids.append(piece_id)
        return self.piece_ids.index(piece_id)

    def save_design(self):
        """設計結果を.stageファイルに保存"""
        # ピースIDごとにセルをグループ化
        pieces = {}
        for (row, col), pid in self.cell_map.items():
            pieces.setdefault(pid, []).append((row, col))

        # ピースデータを作成（セルはピース左上を原点としたローカル座標にする）
        pieces_list = []
        for pid in sorted(pieces.keys()):
            cells = pieces[pid]
            if not cells:
                continue

            min_row = min(c[0] for c in cells)
            min_col = min(c[1] for c in cells)
            pieces_list.append({
                'id': pid,
                'position': (min_row, min_col),
                'cells': sorted((r - min_row, c - min_col) for r, c in cells)
            })

        stage_id, stage_num = self._resolve_save_target()
        output_path = os.path.join(self.game.stages_dir, f"{stage_id}.stage")

        StageLoader.save_stage(
            filepath=output_path,
            stage_id=stage_id,
            name=f"Stage {stage_num}",
            difficulty=1,
            grid_shape=self.game.grid.shape,
            pieces=pieces_list
        )

        self.game.current_stage_id = stage_id
        self.game.save_message = text_manager.get("ui.save_message", stage_num)
        self.game.save_message_timer = 120  # 2秒表示
        print(text_manager.get("logs.saved_file", output_path))

    def _resolve_save_target(self):
        """保存先の (stage_id, stage_num) を決定"""
        # 既存ステージを編集中ならそれを上書き
        stage_num = self.game._current_stage_num()
        if stage_num is not None:
            return self.game.current_stage_id, stage_num

        # 新規ステージ: 既存の最大番号+1
        # （ファイル数+1だと欠番がある時に既存ステージを上書きしてしまう）
        max_num = 0
        for path in StageLoader.list_stages(self.game.stages_dir):
            existing_id = os.path.splitext(os.path.basename(path))[0]
            existing_num = self.game._stage_id_to_num(existing_id)
            if existing_num is not None and existing_num > max_num:
                max_num = existing_num

        stage_num = max_num + 1
        return f"STAGE_{stage_num:03d}", stage_num

    def instructions(self):
        """操作説明の行を返す [(text, color, action), ...]"""
        stage_info = self.game.current_stage_id if self.game.current_stage_id else "(New)"
        return [
            (text_manager.get("instructions.editor.title", stage_info), (255, 200, 100), None),
            (text_manager.get("instructions.editor.load"), (180, 180, 180), None),
            (text_manager.get("instructions.editor.new"), (180, 180, 180), None),
            (text_manager.get("instructions.editor.save"), (180, 180, 180), None),
            (text_manager.get("instructions.editor.change_id"), (180, 180, 180), None),
            (text_manager.get("instructions.editor.toggle_grid"), (180, 180, 180), None),
            (text_manager.get("instructions.editor.exit"), (200, 200, 255), None),
        ]

    def draw(self, screen):
        """エディタモードの描画"""
        grid = self.game.grid
        cell_size = grid.cell_size

        # 最大サイズのグリッド線をうっすら描画（無効セル）
        for row in range(self.max_rows):
            for col in range(self.max_cols):
                if (row, col) not in self.cell_map:
                    x, y = grid.cell_to_pixel(row, col)
                    # pygame.Rect の生成を削減
                    pygame.draw.rect(screen, (60, 60, 70), (x, y, cell_size, cell_size), 1)

        # 有効セルを描画（ピースID付き）
        for (row, col), pid in self.cell_map.items():
            x, y = grid.cell_to_pixel(row, col)

            # ピースIDに応じた色
            idx = self._piece_id_index(pid)
            color = PIECE_COLORS[idx % len(PIECE_COLORS)]

            pygame.draw.rect(screen, color, (x, y, cell_size, cell_size))
            pygame.draw.rect(screen, (0, 0, 0), (x, y, cell_size, cell_size), 2)

            # ピースID文字
            text = self.game.font_ui.render(pid, True, (255, 255, 255))
            text_rect = text.get_rect(center=(x + cell_size // 2, y + cell_size // 2))
            screen.blit(text, text_rect)

        # ページ・操作ガイド表示
        start_stage = (self.page * 10) + 1
        end_stage = (self.page + 1) * 10
        page_info = text_manager.get("ui.editor_info", self.page + 1, start_stage, end_stage)

        info_text = self.game.font_ui.render(page_info, True, (200, 200, 200))
        screen.blit(info_text, (20, self.game.screen_height - 40))
