"""
ゲームループ管理モジュール
ゲームの状態管理とメインループを担当
"""

import pygame
import os
import sys
import json
import datetime
import asyncio
from src.grid import Grid
from src.piece import Piece, PIECE_COLORS
from src.editor import StageEditor
from src.sound import sound_manager
from src.text_manager import text_manager
from src.stage_loader import StageLoader
from src.analytics import analytics


class Game:
    """パズルゲームのメインクラス"""
    
    def __init__(self, screen_width=800, screen_height=600):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.screen = None
        self.clock = None
        self.running = False
        
        self.grid = None
        self.pieces = []
        self.dragging_piece = None
        
        self.game_clear = False
        
        # ステージ情報
        self.current_stage_id = ''
        self.stages_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'stages')

        # ステージエディタ（デスクトップ版のみ）
        self.editor = StageEditor(self)
        
        # 保存メッセージ表示
        self.save_message = ''
        self.save_message_timer = 0
        
        # ゴースト表示（Hキーで切り替え）
        # ゴースト表示（Hキーで切り替え）
        self.show_ghost = False
        
        # Undo履歴
        self.action_history = []
        self.drag_start_state = None
        
        # RTAタイマー
        self.start_time = 0
        self.elapsed_time = 0  # ミリ秒
        self.show_timer = True
        self.clear_time = 0  # クリア時のタイム
        self.rta_invalid = False  # RTA無効フラグ
        self.accumulated_time = 0  # 累積タイム（総合時間用）
        
        # ランキング
        self.ranking = []
        self._load_ranking()
        
        # Web版最適化用
        self.space_lock = False
        self.font_timer = None

        # 次ステージの有無（os.path.existsの結果。ステージ切替時のみ破棄）
        self._next_stage_exists_cache = None

        # 描画キャッシュの再生成判定に使う前回値
        self._last_ghost_state = False
        self._last_editor_mode = False
        self._last_stage_id_for_inst = None
        self._last_privacy_lang = None
        self._last_save_message = None
        self._last_title_lang = None

        # 描画キャッシュ本体
        self._invalidate_render_cache()

        # Privacy Policy Mode
        self.privacy_mode = False

        # Touch controls for instructions (Web only)
        self.instruction_rects = []  # [(rect, action_key), ...]

    def _invalidate_render_cache(self):
        """
        描画キャッシュを一括破棄

        フォント・言語・ステージが変わると描画済みSurfaceは全て古くなる。
        個別にクリアしていると新しいキャッシュを足した時に消し忘れるため、
        破棄は必ずこの1箇所にまとめる
        """
        self._cached_stage_num_text = None
        self._cached_stage_label_text = None
        self._cached_ranking_surfaces = None
        self._cached_instructions = None
        self._cached_privacy_surfaces = None
        self._cached_title_surfaces = None
        self._cached_save_message_text = None
        self._timer_cache_text = None
        self._timer_cache_key = None   # (time_str, color)
        self._ghost_cell_surface = None
        self._ghost_cell_key = None    # (color, cell_size)

    def init(self):
        """Pygame初期化"""
        pygame.init()
        self.screen = pygame.display.set_mode((self.screen_width, self.screen_height))
        pygame.display.set_caption(text_manager.get("window_title"))
        self.clock = pygame.time.Clock()
        self.running = True
        
        
        # サウンド・テキスト初期化
        text_manager.init()
        sound_manager.init()
        
        # フォント更新（言語に合わせて）
        self._update_fonts()
        self._refresh_text_surfaces()

        
        # Stage 1を読み込み（ファイルから）
        stage_file = os.path.join(self.stages_dir, 'STAGE_001.stage')
        if os.path.exists(stage_file):
            try:
                self._load_stage_from_file(stage_file)
            except Exception as e:
                # 破損した.stageファイルで起動できなくなるのを防ぐ
                print(text_manager.get("logs.load_fail", e))
                self._load_stage1()  # フォールバック
        else:
            self._load_stage1()  # フォールバック
        
        # タイマー計測開始
        self.start_time = pygame.time.get_ticks()

    def _update_fonts(self):
        """現在の言語に合わせてフォントを更新"""
        lang = text_manager.current_language
        font_name = None
        
        if lang == 'ja':
            if sys.platform == 'emscripten':
                # Web版: assets/fonts/NotoSansJP-Regular.ttf を探す
                font_path = os.path.join("assets", "fonts", "NotoSansJP-Regular.ttf")
                if os.path.exists(font_path):
                    font_name = font_path
                else:
                    print(f"Web font not found: {font_path}")
                    # フォントがない場合、日本語表示は危険なので英語に戻す
                    print("Falling back to English to prevent crash.")
                    text_manager.load_language('en')
                    # 再帰的に呼ばずにここで設定を変更して終了
                    lang = 'en'
                    font_name = None
            else:
                # Windows向けの日本語フォント
                font_list = ["meiryo", "msgothic", "yu gothic", "arial unicode ms"]
                font_name = pygame.font.match_font(font_list)
        
        # フォントサイズ設定
        # デフォルト(英語)
        size_large = 72
        size_medium = 48
        size_small = 32
        size_ui = 28
        
        # 日本語の場合は20%小さくする（ユーザー要望）
        if lang == 'ja':
            size_large = int(size_large * 0.8)
            size_medium = int(size_medium * 0.8)
            size_small = int(size_small * 0.8)
            size_ui = int(size_ui * 0.8)
            
        self.font_large = pygame.font.Font(font_name, size_large)
        self.font_medium = pygame.font.Font(font_name, size_medium)
        self.font_small = pygame.font.Font(font_name, size_small)
        self.font_ui = pygame.font.Font(font_name, size_ui)
        
        # タイマー用フォント（等幅） - 初期化時に一度だけ生成
        # Consolasがなければデフォルトフォント等が使われる

        self.font_timer = pygame.font.SysFont("consolas", 48)

        # フォントが変わると描画済みSurfaceは全て古くなる
        self._invalidate_render_cache()

    def _refresh_text_surfaces(self):
        """静的テキストを再レンダリング"""
        pygame.display.set_caption(text_manager.get("window_title"))
        self.text_clear = self.font_large.render(text_manager.get("ui.clear"), True, (255, 215, 0))
        self.text_all_clear = self.font_large.render(text_manager.get("ui.all_clear"), True, (255, 215, 0))
        self.text_press_space = self.font_small.render(text_manager.get("ui.press_space"), True, (200, 200, 200))

        # 次回描画時に再生成させる
        self._invalidate_render_cache()
    
    def _load_stage1(self):
        """Stage 1（赤十字型）を読み込み（.stageファイルが無い場合のフォールバック）"""
        # 赤十字型の枠（11x11グリッド）
        # 中央が太い十字
        shape = [
            [0, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0],
            [0, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0],
            [0, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0],
            [0, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0],
            [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            [0, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0],
            [0, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0],
            [0, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0],
            [0, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0],
        ]

        # 赤十字の有効セル数: 57セル
        # 8ピース構成: A(4) + B(5) + C(12) + D(6) + E(6) + F(7) + G(13) + H(4) = 57セル
        # position は正解位置（.stageファイルと同じ形式）
        pieces = [
            # A: 4セル - 縦棒
            {'id': 'A', 'position': (2, 5),
             'cells': [(0, 0), (1, 0), (2, 0), (3, 0)]},
            # B: 5セル
            {'id': 'B', 'position': (3, 6),
             'cells': [(0, 0), (1, 0), (1, 1), (2, 0), (2, 1)]},
            # C: 12セル - 3x4ブロック
            {'id': 'C', 'position': (7, 4),
             'cells': [
                 (0, 0), (0, 1), (0, 2),
                 (1, 0), (1, 1), (1, 2),
                 (2, 0), (2, 1), (2, 2),
                 (3, 0), (3, 1), (3, 2),
             ]},
            # D: 6セル - 横棒
            {'id': 'D', 'position': (6, 5),
             'cells': [(0, 0), (0, 1), (0, 2), (0, 3), (0, 4), (0, 5)]},
            # E: 6セル - 2x3ブロック
            {'id': 'E', 'position': (4, 8),
             'cells': [(0, 0), (0, 1), (0, 2), (1, 0), (1, 1), (1, 2)]},
            # F: 7セル - L字型
            {'id': 'F', 'position': (0, 4),
             'cells': [(0, 0), (0, 1), (0, 2), (1, 0), (1, 1), (1, 2), (2, 2)]},
            # G: 13セル - 大きなL字型
            {'id': 'G', 'position': (4, 0),
             'cells': [
                 (0, 0), (0, 1), (0, 2),
                 (1, 0), (1, 1), (1, 2), (1, 3), (1, 4),
                 (2, 0), (2, 1), (2, 2), (2, 3), (2, 4),
             ]},
            # H: 4セル
            {'id': 'H', 'position': (2, 3),
             'cells': [(0, 1), (1, 1), (2, 0), (2, 1)]},
        ]

        self._setup_stage({
            'stage_id': 'STAGE_001',
            'name': 'Stage 1',
            'difficulty': 1,
            'grid_shape': shape,
            'pieces': pieces,
        })
        # ステージが切り替わったので次ステージ判定をやり直させる
        self._next_stage_exists_cache = None

    def _load_stage_from_file(self, filepath):
        """ファイルからステージを読み込み"""
        stage_data = StageLoader.load_stage(filepath)
        self._setup_stage(stage_data)

    def _build_grid(self, shape, cell_size=40):
        """グリッドを生成して画面中央に配置"""
        if not shape or not shape[0]:
            raise ValueError("grid shape is empty")

        grid_width = len(shape[0]) * cell_size
        grid_height = len(shape) * cell_size
        offset_x = (self.screen_width - grid_width) // 2
        offset_y = (self.screen_height - grid_height) // 2
        return Grid(shape, cell_size, offset_x, offset_y)

    def _setup_stage(self, stage_data):
        """ステージデータ（辞書）からゲームを初期化"""
        self.current_stage_id = stage_data['stage_id']

        # グリッド作成
        self.grid = self._build_grid(stage_data['grid_shape'])

        # 正解位置情報を作成
        self.solution = {}
        for piece_data in stage_data['pieces']:
            self.solution[piece_data['id']] = {
                'row': piece_data['position'][0],
                'col': piece_data['position'][1]
            }

        # ピースを作成して初期位置に配置（画面左側に縦に並べる）
        self.pieces = []
        start_x = 20
        start_y = 50

        for i, piece_data in enumerate(stage_data['pieces']):
            color = PIECE_COLORS[i % len(PIECE_COLORS)]
            piece = Piece(piece_data['id'], piece_data['cells'], color, self.grid.cell_size)

            piece.set_position(start_x, start_y)
            start_y += piece.height + 20

            # 画面下に行きすぎたら次の列へ
            if start_y > self.screen_height - 100:
                start_y = 50
                start_x += 180

            self.pieces.append(piece)

    def _current_stage_num(self):
        """
        現在のステージ番号を取得

        Returns:
            int: STAGE_NNN形式のIDから取り出した番号
            None: 未設定、または番号を持たないID（.stageファイル由来の任意文字列）
        """
        return self._stage_id_to_num(self.current_stage_id)

    @staticmethod
    def _stage_id_to_num(stage_id):
        """ステージIDから番号を取り出す（解析できなければNone）"""
        if not stage_id:
            return None
        try:
            return int(stage_id.split('_')[1])
        except (IndexError, ValueError):
            return None

    def handle_events(self):
        """イベント処理"""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            
            elif event.type == pygame.MOUSEBUTTONDOWN:
                # Privacy Mode dismissal
                if self.privacy_mode:
                    if event.button == 1:
                        self.privacy_mode = False
                # Instruction menu tap (Web only)
                elif sys.platform == 'emscripten' and event.button == 1 and not self.editor.enabled:
                    tapped = False
                    for rect, action in self.instruction_rects:
                        if rect.collidepoint(event.pos):
                            tapped = True
                            self._handle_instruction_tap(action)
                            break
                    if not tapped:
                        # Normal click handling
                        if self.game_clear and self._check_next_stage_exists():
                            self._load_next_stage()
                        else:
                            self._on_mouse_down(event.pos)
                elif self.editor.enabled:
                    self.editor.click(event.pos, event.button)
                elif event.button == 1:
                    # Clear screen click
                    if self.game_clear and self._check_next_stage_exists():
                        self._load_next_stage()
                    else:
                        self._on_mouse_down(event.pos)
            
            elif event.type == pygame.MOUSEBUTTONUP:
                if not self.editor.enabled and event.button == 1:
                    self._on_mouse_up(event.pos)
            
            elif event.type == pygame.MOUSEMOTION:
                self._on_mouse_move(event.pos)
            
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if self.game_clear and not self.editor.enabled and not self._check_next_stage_exists():
                        # オールクリア時のESCはゲーム終了
                        self.running = False
                    elif not self.game_clear:
                         self.running = False
                elif event.key == pygame.K_SPACE:
                    if not self.space_lock: # 連打防止
                        self.space_lock = True
                        if self.privacy_mode:
                            self.privacy_mode = False
                        elif self.game_clear and not self.editor.enabled:
                            if self._check_next_stage_exists():
                                self._load_next_stage()
                elif event.key == pygame.K_r:
                    # リセット
                    self._reset_game()
                elif event.key == pygame.K_z:
                    # Undo
                    if not self.editor.enabled and not self.game_clear:
                        self._undo_last_action()
                elif event.key == pygame.K_t:
                    # タイマー表示切り替え
                    self.show_timer = not self.show_timer
                elif event.key == pygame.K_s:
                    # 正解表示
                    self._show_solution()
                    # 正解を見たらRTA無効
                    if not self.editor.enabled and not self.game_clear:
                        self.rta_invalid = True
                elif event.key == pygame.K_e:
                    # エディタモード切り替え
                    self.editor.toggle()
                elif event.key == pygame.K_p:
                    # 設計を.stageファイルに保存
                    if self.editor.enabled:
                        self.editor.save_design()
                    # タイトル画面 または ゲーム中（非エディタ）でプライバシーポリシー表示
                    elif not self.editor.enabled:
                        self.privacy_mode = not self.privacy_mode
                elif event.key == pygame.K_n:
                    # 新規ステージ（エディタモード時）
                    if self.editor.enabled:
                        self.editor.new_stage()
                # ページ切り替え（エディタモード）
                elif event.key == pygame.K_LEFT and self.editor.enabled:
                    self.editor.prev_page()
                elif event.key == pygame.K_RIGHT and self.editor.enabled:
                    self.editor.next_page()

                elif event.key in [pygame.K_0, pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5,
                                   pygame.K_6, pygame.K_7, pygame.K_8, pygame.K_9]:
                    # 数字キー処理
                    if self.editor.enabled:
                        # ステージ切り替え（エディタモード時）
                        num = event.key - pygame.K_0
                        if num == 0: num = 10

                        self.editor.load_stage(self.editor.stage_num_for_key(num))

                    elif event.key == pygame.K_1:
                         # オールクリア時の1はステージ1からリスタート
                         if self.game_clear and not self.editor.enabled and not self._check_next_stage_exists():
                            self._load_stage(1)
                elif event.key == pygame.K_h:
                    # ゴースト表示切り替え
                    if not self.editor.enabled:
                        self.show_ghost = not self.show_ghost
                        # ヒントを使ったらRTA無効
                        if self.show_ghost and not self.game_clear:
                            self.rta_invalid = True
                
                elif event.key == pygame.K_l:
                    # 言語切り替え
                    new_lang = 'ja' if text_manager.current_language == 'en' else 'en'
                    text_manager.load_language(new_lang)
                    self._update_fonts()
                    self._refresh_text_surfaces()
            
            elif event.type == pygame.KEYUP:
                if event.key == pygame.K_SPACE:
                    self.space_lock = False
    
    def _handle_instruction_tap(self, action):
        """操作説明のタップを処理（Web版のみ）"""
        if action == 'Z':
            if not self.editor.enabled and not self.game_clear:
                self._undo_last_action()
        elif action == 'T':
            self.show_timer = not self.show_timer
        elif action == 'R':
            self._reset_game()
        elif action == 'S':
            self._show_solution()
        elif action == 'H':
            if not self.game_clear:
                self.show_ghost = not self.show_ghost
                if self.show_ghost:
                    self.rta_invalid = True
                self._cached_instructions = None  # キャッシュ無効化
        elif action == 'L':
            new_lang = 'ja' if text_manager.current_language == 'en' else 'en'
            text_manager.load_language(new_lang)
            self._update_fonts()
            self._refresh_text_surfaces()
        elif action == 'P':
            self.privacy_mode = not self.privacy_mode

    def _on_mouse_down(self, pos):
        """マウスボタン押下"""
        if self.game_clear:
            return
        
        mx, my = pos
        
        # ピースを逆順でチェック（上に描画されているものを優先）
        for piece in reversed(self.pieces):
            if piece.contains_point(mx, my):
                # 操作開始時の状態を記録（Undo用）
                self.drag_start_state = self._capture_piece_state(piece)
                
                # 配置済みなら解除
                if piece.placed:
                    piece.remove_from_grid(self.grid)
                
                piece.start_drag(mx, my)
                self.dragging_piece = piece
                
                # ドラッグ中のピースを最前面に
                self.pieces.remove(piece)
                self.pieces.append(piece)

                # ヒントはドラッグ中に正解位置を示すため、ここでは消さない
                # （配置に成功した時点で _on_mouse_up がOFFにする）

                break
    
    def _on_mouse_up(self, pos):
        """マウスボタン解放"""
        if self.dragging_piece:
            self.dragging_piece.end_drag()
            
            # グリッドに配置を試みる
            if self.dragging_piece.try_place(self.grid):
                # 配置成功 - スナップ音を再生
                sound_manager.play("snap")
                
                # 配置に成功したらヒントを消費してOFF
                if self.show_ghost:
                    self.show_ghost = False
            
                # グリッドが完成しているかチェック
                if self.grid.is_complete():
                    self.game_clear = True
                    self.clear_time = self.elapsed_time
                    sound_manager.play("clear")

                    analytics.send_event("stage_clear", {
                        "stage_id": self.current_stage_id,
                        "time_ms": self.elapsed_time,
                        "rta_valid": not self.rta_invalid
                    })

                    # オールクリアなら総合タイムをランキングへ（RTA有効時のみ）
                    if not self._check_next_stage_exists() and not self.rta_invalid:
                        self._update_ranking(self.accumulated_time + self.elapsed_time)
            
            # 状態が変化していれば履歴に追加
            current_state = self._capture_piece_state(self.dragging_piece)
            if self.drag_start_state and current_state != self.drag_start_state:
                self.action_history.append((self.dragging_piece.piece_id, self.drag_start_state))
            
            self.dragging_piece = None
        
        self.drag_start_state = None

    def _capture_piece_state(self, piece):
        """ピースの状態をキャプチャ"""
        return {
            'placed': piece.placed,
            'placed_row': piece.placed_row,
            'placed_col': piece.placed_col,
            'x': piece.x,
            'y': piece.y
        }

    def _undo_last_action(self):
        """直前の操作を元に戻す"""
        if not self.action_history:
            return
        
        piece_id, prev_state = self.action_history.pop()
        
        # 対象ピースを探す
        target_piece = None
        for p in self.pieces:
            if p.piece_id == piece_id:
                target_piece = p
                break
        
        if not target_piece:
            return
        
        # 現在グリッドに配置されているなら解除
        if target_piece.placed:
            target_piece.remove_from_grid(self.grid)
        
        # 状態を復元
        target_piece.x = prev_state['x']
        target_piece.y = prev_state['y']
        target_piece.placed = False
        target_piece.placed_row = None
        target_piece.placed_col = None

        # 復元後の状態が配置済みならグリッドに反映
        # ただし、その後に別のピースが同じ場所を埋めている場合がある。
        # 無条件にoccupyすると相手の占有セルを奪って盤面が壊れるため、
        # 空いている時だけ配置済みとして復元する（埋まっていれば未配置のまま戻す）
        if prev_state['placed'] and target_piece._can_place_at(
                self.grid, prev_state['placed_row'], prev_state['placed_col']):
            target_piece.placed = True
            target_piece.placed_row = prev_state['placed_row']
            target_piece.placed_col = prev_state['placed_col']
            for r, c in target_piece.cells:
                self.grid.occupy(target_piece.placed_row + r,
                               target_piece.placed_col + c,
                               target_piece.piece_id)

        # スナップ音（フィードバックとして）
        sound_manager.play("snap")
    
    def _on_mouse_move(self, pos):
        """マウス移動"""
        if self.dragging_piece:
            self.dragging_piece.update_drag(pos[0], pos[1])
    
    def _show_solution(self):
        """正解配置を表示"""
        # 全ピースをグリッドから解除
        for piece in self.pieces:
            piece.remove_from_grid(self.grid)
        
        # 正解位置に配置
        for piece in self.pieces:
            if piece.piece_id in self.solution:
                sol = self.solution[piece.piece_id]
                target_row = sol['row']
                target_col = sol['col']
                
                # 配置
                piece.placed = True
                piece.placed_row = target_row
                piece.placed_col = target_col
                
                for r, c in piece.cells:
                    self.grid.occupy(target_row + r, target_col + c, piece.piece_id)
                
                piece.x, piece.y = self.grid.cell_to_pixel(target_row, target_col)
        
        # クリア判定
        if self.grid.is_complete():
            self.game_clear = True
    
    def _load_ranking(self):
        """ランキングを読み込み"""
        # Web版はlocalStorageを使用
        if sys.platform == 'emscripten':
            try:
                import platform
                stored = platform.window.localStorage.getItem("woodpuzzle:ranking:rta")
                if stored:
                    self.ranking = json.loads(stored)
                else:
                    self.ranking = []
            except Exception as e:
                print(f"localStorage load error: {e}")
                self.ranking = []
            return

        ranking_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'ranking.json')
        if os.path.exists(ranking_file):
            try:
                with open(ranking_file, 'r') as f:
                    self.ranking = json.load(f)
            except Exception as e:
                print(text_manager.get("logs.ranking_load_fail", e))
                self.ranking = []
        else:
            self.ranking = []

    def _save_ranking(self):
        """ランキングを保存"""
        # Web版はlocalStorageを使用
        if sys.platform == 'emscripten':
            try:
                import platform
                platform.window.localStorage.setItem("woodpuzzle:ranking:rta", json.dumps(self.ranking))
            except Exception as e:
                print(f"localStorage save error: {e}")
            return
            
        ranking_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'ranking.json')
        try:
            with open(ranking_file, 'w') as f:
                json.dump(self.ranking, f, indent=2)
        except Exception as e:
            print(text_manager.get("logs.ranking_save_fail", e))

    def _update_ranking(self, total_time):
        """ランキングを更新"""
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 現在のステージ番号を取得（＝総ステージ数）
        stage_num = self._current_stage_num() or 0

        entry = {
            "time": total_time,
            "date": now_str,
            "stages": stage_num
        }
        
        self.ranking.append(entry)
        # タイム昇順でソート
        self.ranking.sort(key=lambda x: x['time'])
        # 上位5件を残す
        self.ranking = self.ranking[:5]
        
        self._save_ranking()
    
    def _reset_game(self):
        """ゲームをリセット"""
        self.game_clear = False

        analytics.send_event("retry", {
            "stage_id": self.current_stage_id,
            "cause": "user_reset"
        })

        self.action_history = []  # 履歴クリア
        self.start_time = pygame.time.get_ticks()  # タイマーリセット
        self.elapsed_time = 0
        self.clear_time = 0
        
        # 現在のステージIDからロード、なければステージ1
        stage_num = self._current_stage_num()
        if stage_num is not None:
            self._load_stage(stage_num)

            # ステージ1以外でのリセットはRTA無効
            if stage_num > 1:
                self.rta_invalid = True
        else:
            self._load_stage(1)
            # ステージ1なら有効（リトライ扱い）
            self.rta_invalid = False

    def _load_stage(self, stage_num):
        """指定番号のステージをロード"""
        stage_id = f"STAGE_{stage_num:03d}"
        filename = f"{stage_id}.stage"
        filepath = os.path.join(self.stages_dir, filename)
        
        if os.path.exists(filepath):
            self.current_stage_id = stage_id
            self.editor.enabled = False
            self.show_ghost = False
            self.dragging_piece = None
            self.action_history = []  # 履歴クリア
            self._next_stage_exists_cache = None # キャッシュリセット
            
            # ステージロード時は必ずラップタイムをリセット
            self.start_time = pygame.time.get_ticks()
            self.elapsed_time = 0
            self.game_clear = False  # ロード時にクリア状態をリセット
            
            # ステージ1ロード時は総合タイムもリセット
            if stage_num == 1:
                self.accumulated_time = 0
                self.rta_invalid = False
            
            try:
                # ファイルから読み込み
                stage_data = StageLoader.load_stage(filepath)
                self._setup_stage(stage_data)
                print(text_manager.get("logs.loaded_stage", filename, ""))

                # キャッシュクリア（メモリリーク防止）
                self._invalidate_render_cache()


                analytics.send_event("level_start", {
                    "stage_id": self.current_stage_id,
                    "difficulty": stage_data.get('difficulty', 1)
                })
            except Exception as e:
                print(text_manager.get("logs.load_fail", e))
                # 失敗したらhardcodedステージ1へ
                self._load_stage1()
        else:
             # ファイルがなければhardcodedステージ1へ（初回など）
             self._load_stage1()

    def _check_next_stage_exists(self):
        """次のステージが存在するかチェック（キャッシュ付き）"""
        if self._next_stage_exists_cache is not None:
             return self._next_stage_exists_cache

        current_num = self._current_stage_num()
        if current_num is None:
            self._next_stage_exists_cache = False
            return False

        next_id = f"STAGE_{current_num + 1:03d}"
        next_path = os.path.join(self.stages_dir, f"{next_id}.stage")
        exists = os.path.exists(next_path)
        self._next_stage_exists_cache = exists
        return exists

    def _load_next_stage(self):
        """次のステージをロード"""
        current_num = self._current_stage_num()
        if current_num is None:
            return

        next_num = current_num + 1

        # 累積タイムに前ステージのクリアタイムを加算
        if hasattr(self, 'clear_time'):
            self.accumulated_time += self.clear_time
        
        self.game_clear = False
        self._load_stage(next_num)
    
    def update(self):
        """ゲーム状態更新"""
        # 保存メッセージのタイマーを減らす
        if self.save_message_timer > 0:
            self.save_message_timer -= 1
            if self.save_message_timer == 0:
                self.save_message = ''
        
        # タイマー計測
        if not self.game_clear and not self.editor.enabled:
            current = pygame.time.get_ticks()
            self.elapsed_time = current - self.start_time
    
    def draw(self):
        """描画"""
        # タイトル画面
        if self.current_stage_id is None:
            self._draw_title_screen()
        else:
            # 背景
            self.screen.fill((50, 50, 60))
        
        # グリッド
        self.grid.draw(self.screen)
        
        if self.editor.enabled:
            # エディタモード: セルマップを描画
            self.editor.draw(self.screen)
        else:
            # 通常モード
            # ゴースト表示（正解位置を半透明で表示）
            if self.show_ghost:
                self._draw_ghost()
            
            # 配置可能位置のハイライト（ドラッグ中のみ）
            if self.dragging_piece:
                self._draw_placeable_highlight()
            
            # ピース描画
            for piece in self.pieces:
                piece.draw(self.screen)
        
        # Clear display
        if self.game_clear and not self.editor.enabled:
            self._draw_clear_message()
        
        # 操作説明
        self._draw_instructions()
        
        # ステージ番号（右上）
        if not self.editor.enabled:
            self._draw_stage_number()
        
        # 保存メッセージ
        if self.save_message:
            self._draw_save_message()
            
        # タイマー描画
        if self.show_timer and not self.editor.enabled:
            self._draw_timer()
            
        # プライバシーポリシー（最前面にオーバーレイ）
        if self.privacy_mode:
            self._draw_privacy_policy()
        
        pygame.display.flip()
    
    def _draw_clear_message(self):
        """クリアメッセージを描画"""
        # ステージ番号
        if self._cached_stage_label_text is None:
             stage_num = self._current_stage_num() or 1
             self._cached_stage_label_text = self.font_large.render(text_manager.get("ui.stage_label", stage_num), True, (200, 200, 200))
        
        stage_text = self._cached_stage_label_text
        stage_rect = stage_text.get_rect(center=(self.screen_width // 2, self.screen_height // 2 - 60))
        
        # CLEAR!
        text_rect = self.text_clear.get_rect(center=(self.screen_width // 2, self.screen_height // 2))
        
        # サブメッセージ
        if self._check_next_stage_exists():
            # 次のステージがある場合
            sub_rect = self.text_press_space.get_rect(center=(self.screen_width // 2, self.screen_height // 2 + 50))
            
            # 背景（全テキストを含む）
            combined_rect = stage_rect.union(text_rect).union(sub_rect)
            bg_rect = combined_rect.inflate(60, 40)
            pygame.draw.rect(self.screen, (0, 0, 0), bg_rect)
            pygame.draw.rect(self.screen, (255, 215, 0), bg_rect, 3)
            
            self.screen.blit(stage_text, stage_rect)
            self.screen.blit(self.text_clear, text_rect)
            
            # 点滅処理 (1600ms周期: 800ms ON / 800ms OFF)
            blink_interval = 800
            if (pygame.time.get_ticks() // blink_interval) % 2 == 0:
                self.screen.blit(self.text_press_space, sub_rect)
            
        else:
            # オールクリアの場合
            # "ALL CLEAR!" を少し右へ戻す（センタリング調整）
            # ランキング表示に合わせて全体を上にずらす（重なり回避）
            text_rect = self.text_all_clear.get_rect(center=(self.screen_width // 2 - 20, self.screen_height // 2 - 140))

            # ランキングはSurfaceをキャッシュ（毎フレームrenderするとWeb版が重い）
            if self._cached_ranking_surfaces is None:
                self._generate_ranking_cache(self.screen_height // 2 + 50 - 80 + 30)

            # 背景（全テキストを含む）
            total_rect = stage_rect.union(text_rect)
            for _, r in self._cached_ranking_surfaces:
                total_rect = total_rect.union(r)

            bg_rect = total_rect.inflate(60, 120)
            pygame.draw.rect(self.screen, (0, 0, 0), bg_rect)
            pygame.draw.rect(self.screen, (255, 215, 0), bg_rect, 3)

            # 描画
            self.screen.blit(stage_text, stage_rect)
            self.screen.blit(self.text_all_clear, text_rect)
            for s, r in self._cached_ranking_surfaces:
                self.screen.blit(s, r)


    def _generate_ranking_cache(self, start_y):
        """ランキング表示をキャッシュ生成"""
        if self._cached_ranking_surfaces is not None:
             return self._cached_ranking_surfaces
             
        # オプションを複数行で表示
        options = [
            (text_manager.get("instructions.game_over.esc"), (200, 200, 200)),
            (text_manager.get("instructions.game_over.restart"), (200, 200, 200)),
            (text_manager.get("instructions.game_over.retry"), (200, 200, 200))
        ]
        
        surfaces = []
        
        # オプション
        for i, (opt_text, color) in enumerate(options):
            s = self.font_small.render(opt_text, True, color)
            r = s.get_rect(topleft=(self.screen_width // 2 - 130, start_y + i * 30))
            surfaces.append((s, r))
            
        rank_start_y = start_y + len(options) * 30 + 30
        rank_title = self.font_small.render(text_manager.get("ui.ranking_title"), True, (255, 215, 0))
        adjust_x = 30
        rank_title_rect = rank_title.get_rect(center=(self.screen_width // 2 - adjust_x, rank_start_y))
        surfaces.append((rank_title, rank_title_rect))
        
        current_total_time = -1
        if not self.rta_invalid and self.game_clear:
                current_total_time = self.accumulated_time + self.elapsed_time

        for i, entry in enumerate(self.ranking):
            time_ms = entry['time']
            time_str = self._format_rta_time(time_ms)

            if i == 0:
                rank_str = text_manager.get("ranking.1st", time_str)
            elif i == 1:
                rank_str = text_manager.get("ranking.2nd", time_str)
            elif i == 2:
                rank_str = text_manager.get("ranking.3rd", time_str)
            else:
                rank_str = text_manager.get("ranking.nth", i+1, time_str)
            
            color = (200, 200, 200)
            if current_total_time != -1 and abs(current_total_time - time_ms) < 10: 
                color = (255, 255, 100)
                rank_str += text_manager.get("ui.ranking_new")
                
            s = self.font_small.render(rank_str, True, color)
            r = s.get_rect(center=(self.screen_width // 2 - adjust_x, rank_start_y + 30 + i * 25))
            surfaces.append((s, r))
            
        self._cached_ranking_surfaces = surfaces
        return surfaces
    
    def _draw_stage_number(self):
        """ステージ番号を右上に描画"""
        if self._cached_stage_num_text is None:
            stage_num = self._current_stage_num() or 1
            self._cached_stage_num_text = self.font_large.render(text_manager.get("ui.stage_label", stage_num), True, (180, 180, 180))
            
        text = self._cached_stage_num_text
        text_rect = text.get_rect(topright=(self.screen_width - 15, 10))
        self.screen.blit(text, text_rect)
    
    def _draw_placeable_highlight(self):
        """配置可能な位置をハイライト表示（最適化版）"""
        if not self.dragging_piece:
            return
        
        piece = self.dragging_piece
        cell_size = self.grid.cell_size
        
        # ピースの中心位置から候補セルを絞り込む
        # ピースの最初のセルの位置を基準に、グリッド上の候補位置を推定
        first_cell = piece.cells[0]
        piece_center_x = piece.x + first_cell[1] * cell_size + cell_size // 2
        piece_center_y = piece.y + first_cell[0] * cell_size + cell_size // 2
        
        # グリッド上の候補セル位置を取得
        candidate_row, candidate_col = self.grid.pixel_to_cell(piece_center_x, piece_center_y)
        target_row = candidate_row - first_cell[0]
        target_col = candidate_col - first_cell[1]
        
        # 候補位置の周辺（±3セル範囲）のみをチェック
        check_range = 3
        candidates = []
        for dr in range(-check_range, check_range + 1):
            for dc in range(-check_range, check_range + 1):
                test_row = target_row + dr
                test_col = target_col + dc
                # 有効セル内かチェック
                if (test_row, test_col) in self.grid.valid_cells:
                    candidates.append((test_row, test_col))
        
        # 候補位置が少ない場合は全セルをチェック（フォールバック）
        if len(candidates) < 5:
            candidates = self.grid.valid_cells
        
        # 候補位置のみをチェック
        for base_row, base_col in candidates:
            # この位置にピースが置けるかチェック
            can_place = True
            cells_to_highlight = []
            
            for dr, dc in piece.cells:
                check_row = base_row + dr
                check_col = base_col + dc
                
                # 枠内かつ未占有かチェック
                if not self.grid.is_valid_cell(check_row, check_col):
                    can_place = False
                    break
                if self.grid.is_occupied(check_row, check_col):
                    can_place = False
                    break
                
                cells_to_highlight.append((check_row, check_col))
            
            # 配置可能ならハイライト表示
            if can_place:
                for r, c in cells_to_highlight:
                    x, y = self.grid.cell_to_pixel(r, c)
                    # pygame.Rect の生成を削減（直接描画）
                    pygame.draw.rect(self.screen, (255, 220, 80), 
                                   (x + 2, y + 2, cell_size - 4, cell_size - 4), 2)
    
    def _draw_ghost(self):
        """選択中のピースの正解位置を半透明で描画"""
        if not hasattr(self, 'solution'):
            return
        
        # ドラッグ中のピースのみ表示
        if not self.dragging_piece:
            return
        
        piece = self.dragging_piece
        
        # 配置済みなら表示しない
        if piece.placed:
            return
        
        # 正解位置を取得
        if piece.piece_id not in self.solution:
            return
        
        cell_size = self.grid.cell_size
        sol = self.solution[piece.piece_id]
        base_row = sol['row']
        base_col = sol['col']
        
        # 半透明セルのSurfaceはピース色ごとにキャッシュ（毎フレーム生成しない）
        ghost_alpha = 80  # 透明度（0-255）
        ghost_key = (piece.color, cell_size)
        if self._ghost_cell_key != ghost_key:
            surface = pygame.Surface((cell_size, cell_size), pygame.SRCALPHA)
            surface.fill((piece.color[0], piece.color[1], piece.color[2], ghost_alpha))
            self._ghost_cell_surface = surface
            self._ghost_cell_key = ghost_key

        for dr, dc in piece.cells:
            x, y = self.grid.cell_to_pixel(base_row + dr, base_col + dc)
            self.screen.blit(self._ghost_cell_surface, (x, y))
            # 枠線
            pygame.draw.rect(self.screen, (255, 255, 255), (x, y, cell_size, cell_size), 1)
    
    def _format_rta_time(self, total_ms):
        """RTA用タイム文字列生成 (ms対応)"""
        seconds = total_ms // 1000
        ms = (total_ms % 1000) // 100  # 1桁（100ms単位）
        
        minutes = seconds // 60
        seconds = seconds % 60
        hours = minutes // 60
        minutes = minutes % 60
        
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{ms}"

    def _draw_timer(self):
        """経過時間を描画（表示文字列が変わった時だけrenderする）"""
        if not self.show_timer:
            return

        # 時間計算（クリア済みなら固定）
        total_ms = self.clear_time if self.game_clear else self.elapsed_time
        
        # 文字列生成
        time_str = self._format_rta_time(total_ms)
        
        # 色決定
        if self.rta_invalid:
            color = (255, 80, 80)
        elif self.game_clear:
            color = (255, 215, 0)
        else:
            color = (255, 255, 255)
            
        # キャッシュキー (文字列, 色)
        cache_key = (time_str, color)
        
        # 変更があれば再生成
        if cache_key != self._timer_cache_key or self._timer_cache_text is None:
            self._timer_cache_key = cache_key
            self._timer_cache_text = self.font_timer.render(time_str, True, color)
            
        text = self._timer_cache_text
        rect = text.get_rect(bottomright=(self.screen_width - 10, self.screen_height - 10))
        
        self.screen.blit(text, rect)

    def _draw_save_message(self):
        """保存メッセージを描画（キャッシュ最適化版）"""
        # メッセージが変わった場合のみ再生成
        if (self._cached_save_message_text is None or 
            self._last_save_message != self.save_message):
            
            self._last_save_message = self.save_message
            if self.save_message:
                self._cached_save_message_text = self.font_medium.render(
                    self.save_message, True, (50, 255, 100))
            else:
                self._cached_save_message_text = None
        
        if self._cached_save_message_text is None:
            return
        
        text = self._cached_save_message_text
        text_rect = text.get_rect(center=(self.screen_width // 2, self.screen_height // 2))
        
        # 背景
        bg_rect = text_rect.inflate(40, 20)
        pygame.draw.rect(self.screen, (0, 50, 20), bg_rect)
        pygame.draw.rect(self.screen, (50, 255, 100), bg_rect, 3)
        
        self.screen.blit(text, text_rect)
    
    def _draw_privacy_policy(self):
        """プライバシーポリシーをオーバーレイ表示（キャッシュ最適化版）"""
        current_lang = text_manager.current_language
        
        # キャッシュの再生成が必要かチェック
        if (self._cached_privacy_surfaces is None or 
            self._last_privacy_lang != current_lang):
            
            self._last_privacy_lang = current_lang
            
            # Title
            title_text = "プライバシーポリシー" if current_lang == 'ja' else "PRIVACY POLICY"
            title_surf = self.font_ui.render(title_text, True, (255, 255, 255))
            title_rect = title_surf.get_rect(center=(self.screen_width // 2, 0))  # yは後で計算
            
            # Content (Localized)
            if current_lang == 'ja':
                lines = [
                    "本ゲームでは Google Analytics 4 (GA4)",
                    "を使用して匿名の利用データを収集しています。",
                    "",
                    "- 収集データ: ステージクリア、リトライ回数",
                    "- 目的: ゲームの技術的改善",
                    "- 個人を特定する情報は収集しません",
                    "",
                    "機能のためにCookieを使用します。",
                ]
            else:
                lines = [
                    "This game uses Google Analytics 4 (GA4)",
                    "to collect anonymous usage data.",
                    "",
                    "- Collected Data: Stage clears, Retries",
                    "- Purpose: Game technical improvements",
                    "- No personal info is collected",
                    "",
                    "Cookies are used for functionality.",
                ]
            
            line_height = 30
            content_surfaces = []
            for line in lines:
                color = (220, 220, 220)
                if line.startswith("-") or line.startswith("- "): 
                    color = (150, 255, 255)
                surf = self.font_ui.render(line, True, color)
                content_surfaces.append((surf, surf.get_rect(center=(self.screen_width // 2, 0))))
            
            # Footer
            footer_text = "クリックで閉じる" if current_lang == 'ja' else "Click to Close"
            footer_surf = self.font_ui.render(footer_text, True, (255, 200, 100))
            footer_rect = footer_surf.get_rect(center=(self.screen_width // 2, 0))
            
            self._cached_privacy_surfaces = {
                'title': (title_surf, title_rect),
                'content': content_surfaces,
                'footer': (footer_surf, footer_rect),
                'line_height': line_height
            }
        
        # 半透明の黒背景
        overlay = pygame.Surface((self.screen_width, self.screen_height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 200)) # Alpha 200/255
        self.screen.blit(overlay, (0, 0))
        
        # ボックス枠
        box_width = 600
        box_height = 400
        box_rect = pygame.Rect(
            (self.screen_width - box_width) // 2,
            (self.screen_height - box_height) // 2,
            box_width, box_height
        )
        pygame.draw.rect(self.screen, (30, 30, 40), box_rect)
        pygame.draw.rect(self.screen, (100, 200, 255), box_rect, 2)
        
        # キャッシュから描画
        cache = self._cached_privacy_surfaces
        y = box_rect.top + 30
        
        # Title
        title_surf, title_rect = cache['title']
        title_rect.centery = y
        self.screen.blit(title_surf, title_rect)
        y += 50
        
        # Content
        for surf, rect in cache['content']:
            rect.centery = y
            self.screen.blit(surf, rect)
            y += cache['line_height']
        
        # Footer
        footer_surf, footer_rect = cache['footer']
        footer_rect.centery = box_rect.bottom - 40
        self.screen.blit(footer_surf, footer_rect)

    def _draw_title_screen(self):
        """タイトル画面を描画（キャッシュ最適化版）"""
        current_lang = text_manager.current_language
        
        # キャッシュの再生成が必要かチェック
        if (self._cached_title_surfaces is None or 
            self._last_title_lang != current_lang):
            
            self._last_title_lang = current_lang
            
            # タイトル
            title_text = text_manager.get("ui.game_title")
            title_surface = self.font_large.render(title_text, True, (255, 255, 255))
            title_rect = title_surface.get_rect(center=(self.screen_width // 2, 200))
            
            # Press start
            start_text = text_manager.get("ui.press_start")
            start_surface = self.font_medium.render(start_text, True, (200, 200, 200))
            start_rect = start_surface.get_rect(center=(self.screen_width // 2, self.screen_height // 2 + 100))
            
            # P: Privacy Policy
            privacy_text = "P:プライバシーポリシー" if current_lang == 'ja' else "P: Privacy Policy"
            privacy_color = (150, 200, 255)
            privacy_surface = self.font_ui.render(privacy_text, True, privacy_color)
            
            self._cached_title_surfaces = {
                'title': (title_surface, title_rect),
                'start': (start_surface, start_rect),
                'privacy': (privacy_surface, (10, 10))
            }
        
        # 背景
        self.screen.fill((0, 0, 0)) # 黒で画面をクリア
        
        # キャッシュから描画
        cache = self._cached_title_surfaces
        
        # タイトル
        self.screen.blit(cache['title'][0], cache['title'][1])
        
        # Press start (点滅)
        if pygame.time.get_ticks() % 1000 < 500:
            self.screen.blit(cache['start'][0], cache['start'][1])
        
        # P: Privacy Policy
        self.screen.blit(cache['privacy'][0], cache['privacy'][1])

    def _draw_instructions(self):
        """操作説明を描画（キャッシュ最適化版）"""
        # 状態変化のチェック
        current_ghost = self.show_ghost
        current_editor = self.editor.enabled
        current_stage = self.current_stage_id
        
        if (self._cached_instructions is None or 
            current_ghost != self._last_ghost_state or 
            current_editor != self._last_editor_mode or
            current_stage != self._last_stage_id_for_inst):
            
            # 状態更新
            self._last_ghost_state = current_ghost
            self._last_editor_mode = current_editor
            self._last_stage_id_for_inst = current_stage
            
            # font = pygame.font.Font(None, 24) # 文字化けの原因
            # UI用フォントを使用 (font_uiは28px設定だが、少し小さくしたい場合はスケールダウンするか、font_uiを使う)
            # instructionは font_ui(28/25px) を使用する
            font = self.font_ui
            
            # 各行は (text, color, action) の3要素
            if self.editor.enabled:
                instructions = self.editor.instructions()
            else:
                hint_status = "ON" if self.show_ghost else "OFF"
                hint_color = (100, 255, 150) if self.show_ghost else (180, 180, 180)
                instructions = [
                    (text_manager.get("instructions.game.drag"), (180, 180, 180), None),
                    ("", None, None),
                    (text_manager.get("instructions.game.undo"), (180, 180, 180), 'Z'),
                    (text_manager.get("instructions.game.timer"), (180, 180, 180), 'T'),
                    (text_manager.get("instructions.game.reset"), (180, 180, 180), 'R'),
                    (text_manager.get("instructions.game.solution"), (180, 180, 180), 'S'),
                    (text_manager.get("instructions.game.hint", hint_status), hint_color, 'H'),
                    # Web版ではエディタ非表示
                    (text_manager.get("instructions.game.editor") if sys.platform != 'emscripten' else "", (200, 200, 255) if sys.platform != 'emscripten' else None, None),
                    (text_manager.get("instructions.game.language"), (150, 255, 255), 'L'),
                    ("P:プライバシーポリシー" if text_manager.current_language == 'ja' else "P: Privacy Policy", (150, 200, 255), 'P')
                ]
            
            # レンダリングしてキャッシュ
            rendered_items = []
            max_width = 0
            for item in instructions:
                if item[1] is None:
                    rendered_items.append((None, None))
                    continue
                
                text, color, action = item
                surface = font.render(text, True, color)
                width = surface.get_width()
                if width > max_width:
                    max_width = width
                rendered_items.append((surface, action))
            
            self._cached_instructions = (rendered_items, max_width)

        # キャッシュから描画
        items, max_width = self._cached_instructions
        
        # ステージ表示（右上）の下に配置
        y = 100
        
        # 右端を基準に左端の位置を決定
        right_margin = 15
        left_x = self.screen_width - right_margin - max_width
        
        # インデントフラグ（空白行の後はインデントする）
        apply_indent = False
        indent_width = 40 # 3文字分程度
        
        # Web版は行間を広げる（タッチ対応）
        line_height = 35 if sys.platform == 'emscripten' else 22
        
        # タップ領域をリセット
        self.instruction_rects = []
        
        for surface, action in items:
            if surface is None:
                y += 10  # 空白
                apply_indent = True
                continue
            
            # インデント適用
            draw_x = left_x
            if apply_indent:
                draw_x += indent_width
            
            # 左揃えで描画
            self.screen.blit(surface, (draw_x, y))
            
            # タップ領域を保存（Web版かつアクションがある場合）
            if sys.platform == 'emscripten' and action:
                rect = pygame.Rect(draw_x, y, max_width, line_height)
                self.instruction_rects.append((rect, action))
            
            y += line_height
    
    async def run(self):
        """メインループ"""
        self.init()
        
        while self.running:
            self.handle_events()
            self.update()
            self.draw()
            # clock.tick(60) は削除: await asyncio.sleep(0) がVSyncと同期するため不要
            await asyncio.sleep(0)
        
        pygame.quit()
