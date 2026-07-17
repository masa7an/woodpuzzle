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
from src.piece import Piece
from src.sound import sound_manager
from src.text_manager import text_manager
from src.stage_loader import StageLoader
from src.analytics import analytics


# ピースの色パレット
PIECE_COLORS = [
    (220, 80, 80),    # A: 赤
    (80, 180, 80),    # B: 緑
    (80, 120, 220),   # C: 青
    (220, 180, 60),   # D: 黄
    (180, 80, 180),   # E: 紫
    (80, 200, 200),   # F: シアン
    (240, 140, 80),   # G: オレンジ
    (255, 120, 180),  # H: ピンク
]


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
        
        # エディタモード
        self.editor_mode = False
        self.editor_cell_map = {}  # {(row, col): piece_id}
        # A-Zまで用意しておく（自動生成ステージ対応）
        self.piece_ids = [chr(i) for i in range(ord('A'), ord('Z')+1)]
        self.editor_max_rows = 11  # 編集可能な最大行数
        self.editor_max_cols = 11  # 編集可能な最大列数
        
        # ステージ情報
        self.current_stage_id = ''
        self.stages_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'stages')
        self.editor_page = 0  # ステージ選択ページ (0: 1-10, 1: 11-20...)
        
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
        self._timer_cache_text = None
        self._timer_cache_key = None # (time_str, color)
        self._timer_last_update = 0.0
        self._timer_update_interval = 0.01 # 10ms
        
        # その他キャッシュ
        self._next_stage_exists_cache = None
        self._cached_instructions = None
        self._last_ghost_state = False
        self._last_editor_mode = False
        
        # Privacy Policy Mode
        self.privacy_mode = False
        self._last_stage_id_for_inst = None
        self._cached_privacy_surfaces = None
        self._last_privacy_lang = None
        
        # Touch controls for instructions (Web only)
        self.instruction_rects = []  # [(rect, action_key), ...]
        
        # Save message cache
        self._cached_save_message_text = None
        self._last_save_message = None
        
        # Title screen cache
        self._cached_title_surfaces = None
        self._last_title_lang = None
        

    
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
        self._timer_cache_text = None # フォント変更時にキャッシュクリア
        self._timer_cache_key = None

    def _refresh_text_surfaces(self):
        """静的テキストを再レンダリング"""
        pygame.display.set_caption(text_manager.get("window_title"))
        self.text_clear = self.font_large.render(text_manager.get("ui.clear"), True, (255, 215, 0))
        self.text_all_clear = self.font_large.render(text_manager.get("ui.all_clear"), True, (255, 215, 0))
        self.text_press_space = self.font_small.render(text_manager.get("ui.press_space"), True, (200, 200, 200))
        
        # キャッシュ無効化（次回描画時に再生成）
        self._cached_stage_num_text = None
        self._cached_stage_label_text = None
        self._cached_ranking_surfaces = None
        self._cached_instructions = None
    
    def _load_stage1(self):
        """Stage 1（赤十字型）を読み込み"""
        # ステージ番号を持たないと次ステージ判定が働かないため必ず設定する
        self.current_stage_id = 'STAGE_001'
        self._next_stage_exists_cache = None

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
        
        # グリッド作成（画面中央に配置）
        cell_size = 40
        grid_width = len(shape[0]) * cell_size
        grid_height = len(shape) * cell_size
        offset_x = (self.screen_width - grid_width) // 2
        offset_y = (self.screen_height - grid_height) // 2
        
        self.grid = Grid(shape, cell_size, offset_x, offset_y)
        
        # ピースを作成
        self._create_stage1_pieces(cell_size)
    
    def _create_stage1_pieces(self, cell_size):
        """Stage 1のピースを作成（ユーザーデザイン）"""
        # 赤十字の有効セル数: 57セル
        # 8ピース構成: A(4) + B(5) + C(12) + D(6) + E(6) + F(7) + G(13) + H(4) = 57セル
        
        # 正解位置情報
        self.solution = {
            'A': {'row': 2, 'col': 5},
            'B': {'row': 3, 'col': 6},
            'C': {'row': 7, 'col': 4},
            'D': {'row': 6, 'col': 5},
            'E': {'row': 4, 'col': 8},
            'F': {'row': 0, 'col': 4},
            'G': {'row': 4, 'col': 0},
            'H': {'row': 2, 'col': 3},
        }
        
        pieces_data = [
            # A: 4セル - 縦棒
            {
                'id': 'A',
                'cells': [(0, 0), (1, 0), (2, 0), (3, 0)],
            },
            # B: 5セル
            {
                'id': 'B',
                'cells': [(0, 0), (1, 0), (1, 1), (2, 0), (2, 1)],
            },
            # C: 12セル - 3x4ブロック
            {
                'id': 'C',
                'cells': [
                    (0, 0), (0, 1), (0, 2),
                    (1, 0), (1, 1), (1, 2),
                    (2, 0), (2, 1), (2, 2),
                    (3, 0), (3, 1), (3, 2),
                ],
            },
            # D: 6セル - 横棒
            {
                'id': 'D',
                'cells': [(0, 0), (0, 1), (0, 2), (0, 3), (0, 4), (0, 5)],
            },
            # E: 6セル - 2x3ブロック
            {
                'id': 'E',
                'cells': [(0, 0), (0, 1), (0, 2), (1, 0), (1, 1), (1, 2)],
            },
            # F: 7セル - L字型
            {
                'id': 'F',
                'cells': [(0, 0), (0, 1), (0, 2), (1, 0), (1, 1), (1, 2), (2, 2)],
            },
            # G: 13セル - 大きなL字型
            {
                'id': 'G',
                'cells': [
                    (0, 0), (0, 1), (0, 2),
                    (1, 0), (1, 1), (1, 2), (1, 3), (1, 4),
                    (2, 0), (2, 1), (2, 2), (2, 3), (2, 4),
                ],
            },
            # H: 4セル
            {
                'id': 'H',
                'cells': [(0, 1), (1, 1), (2, 0), (2, 1)],
            },
        ]
        
        # ピースを作成して初期位置に配置
        self.pieces = []
        start_x = 20
        start_y = 50
        
        for i, data in enumerate(pieces_data):
            color = PIECE_COLORS[i % len(PIECE_COLORS)]
            piece = Piece(data['id'], data['cells'], color, cell_size)
            
            # 初期位置（画面左側に縦に並べる）
            piece.set_position(start_x, start_y)
            start_y += piece.height + 20
            
            # 画面下に行きすぎたら次の列へ
            if start_y > self.screen_height - 100:
                start_y = 50
                start_x += 180
            
            self.pieces.append(piece)
    
    def _load_stage_from_file(self, filepath):
        """ファイルからステージを読み込み"""
        stage_data = StageLoader.load_stage(filepath)
        self._setup_stage(stage_data)

    def _setup_stage(self, stage_data):
        """ステージデータ（辞書）からゲームを初期化"""
        self.current_stage_id = stage_data['stage_id']
        
        # グリッド作成
        shape = stage_data['grid_shape']
        cell_size = 40
        grid_width = len(shape[0]) * cell_size
        grid_height = len(shape) * cell_size
        offset_x = (self.screen_width - grid_width) // 2
        offset_y = (self.screen_height - grid_height) // 2
        
        self.grid = Grid(shape, cell_size, offset_x, offset_y)
        
        # 正解位置情報を作成
        self.solution = {}
        for piece_data in stage_data['pieces']:
            self.solution[piece_data['id']] = {
                'row': piece_data['position'][0],
                'col': piece_data['position'][1]
            }
        
        # ピースを作成
        self.pieces = []
        start_x = 20
        start_y = 50
        
        for i, piece_data in enumerate(stage_data['pieces']):
            color = PIECE_COLORS[i % len(PIECE_COLORS)]
            piece = Piece(piece_data['id'], piece_data['cells'], color, cell_size)
            
            piece.set_position(start_x, start_y)
            start_y += piece.height + 20
            
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
                elif sys.platform == 'emscripten' and event.button == 1 and not self.editor_mode:
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
                elif self.editor_mode:
                    self._editor_click(event.pos, event.button)
                elif event.button == 1:
                    # Clear screen click
                    if self.game_clear and self._check_next_stage_exists():
                        self._load_next_stage()
                    else:
                        self._on_mouse_down(event.pos)
            
            elif event.type == pygame.MOUSEBUTTONUP:
                if not self.editor_mode and event.button == 1:
                    self._on_mouse_up(event.pos)
            
            elif event.type == pygame.MOUSEMOTION:
                self._on_mouse_move(event.pos)
            
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if self.game_clear and not self.editor_mode and not self._check_next_stage_exists():
                        # オールクリア時のESCはゲーム終了
                        self.running = False
                    elif not self.game_clear:
                         self.running = False
                elif event.key == pygame.K_SPACE:
                    if not self.space_lock: # 連打防止
                        self.space_lock = True
                        if self.privacy_mode:
                            self.privacy_mode = False
                        elif self.game_clear and not self.editor_mode:
                            if self._check_next_stage_exists():
                                self._load_next_stage()
                elif event.key == pygame.K_r:
                    # リセット
                    self._reset_game()
                elif event.key == pygame.K_z:
                    # Undo
                    if not self.editor_mode and not self.game_clear:
                        self._undo_last_action()
                elif event.key == pygame.K_t:
                    # タイマー表示切り替え
                    self.show_timer = not self.show_timer
                elif event.key == pygame.K_s:
                    # 正解表示
                    self._show_solution()
                    # 正解を見たらRTA無効
                    if not self.editor_mode and not self.game_clear:
                        self.rta_invalid = True
                elif event.key == pygame.K_e:
                    # エディタモード切り替え
                    self._toggle_editor_mode()
                elif event.key == pygame.K_p:
                    # 設計を.stageファイルに保存
                    if self.editor_mode:
                        self._print_design()
                    # タイトル画面 または ゲーム中（非エディタ）でプライバシーポリシー表示
                    elif not self.editor_mode:
                        self.privacy_mode = not self.privacy_mode
                elif event.key == pygame.K_n:
                    # 新規ステージ（エディタモード時）
                    if self.editor_mode:
                        self._editor_new_stage()
                # ページ切り替え（エディタモード）
                elif event.key == pygame.K_LEFT and self.editor_mode:
                    self.editor_page = max(0, self.editor_page - 1)
                    print(f"Page: {self.editor_page + 1}")
                elif event.key == pygame.K_RIGHT and self.editor_mode:
                    self.editor_page += 1
                    print(f"Page: {self.editor_page + 1}")
                
                elif event.key in [pygame.K_0, pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5,
                                   pygame.K_6, pygame.K_7, pygame.K_8, pygame.K_9]:
                    # 数字キー処理
                    if self.editor_mode:
                        # ステージ切り替え（エディタモード時）
                        num = event.key - pygame.K_0
                        if num == 0: num = 10
                        
                        stage_num = (self.editor_page * 10) + num
                        self._editor_load_stage(stage_num)
                    
                    elif event.key == pygame.K_1:
                         # オールクリア時の1はステージ1からリスタート
                         if self.game_clear and not self.editor_mode and not self._check_next_stage_exists():
                            self._load_stage(1)
                elif event.key == pygame.K_h:
                    # ゴースト表示切り替え
                    if not self.editor_mode:
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
            if not self.editor_mode and not self.game_clear:
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
                    # オールクリア判定
                    if not self._check_next_stage_exists():
                        self.game_clear = True
                        self.clear_time = self.elapsed_time
                        sound_manager.play("clear")
                        
                        # Analytics: Stage Clear (non-blocking)
                        try:
                            analytics.send_event("stage_clear", {
                                "stage_id": self.current_stage_id,
                                "time_ms": self.elapsed_time,
                                "rta_valid": not self.rta_invalid
                            })
                        except Exception as e:
                            print(f"[Game] Analytics error (non-blocking): {e}")
                        
                        # 総合タイム計算とランキング更新（RTA有効時のみ）
                        if not self.rta_invalid:
                            total_time = self.accumulated_time + self.elapsed_time
                            self._update_ranking(total_time)
                    else:
                        self.game_clear = True
                        self.clear_time = self.elapsed_time
                        sound_manager.play("clear")
                        
                        # Analytics: Stage Clear (non-blocking)
                        try:
                            analytics.send_event("stage_clear", {
                                "stage_id": self.current_stage_id,
                                "time_ms": self.elapsed_time,
                                "rta_valid": not self.rta_invalid
                            })
                        except Exception as e:
                            print(f"[Game] Analytics error (non-blocking): {e}")
            
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
    
    def _toggle_editor_mode(self):
        """エディタモード切り替え"""
        # Web版ではエディタモード無効
        if sys.platform == 'emscripten':
            return
        self.editor_mode = not self.editor_mode
        if self.editor_mode:
            # エディタモード開始時、グリッドを現在の正解で初期化
            self.editor_cell_map = {}
            for cell in self.grid.valid_cells:
                self.editor_cell_map[cell] = 'A'  # 初期は全てA
            
            stages = StageLoader.list_stages(self.stages_dir)
            print(text_manager.get("logs.editor_mode_on"))
            print(text_manager.get("logs.available_stages", len(stages)))
            print(text_manager.get("logs.editor_console_guide"))
        else:
            print(text_manager.get("logs.editor_mode_off"))
            # エディタ終了時に現在のステージを再ロードして変更を反映
            stage_num = self._current_stage_num()
            if stage_num is not None:
                self._load_stage(stage_num)
            else:
                self._load_stage1()
    
    def _editor_new_stage(self):
        """新規ステージを作成"""
        # 全セルをAで初期化
        self.editor_cell_map = {}
        for cell in self.grid.valid_cells:
            self.editor_cell_map[cell] = 'A'
        self.current_stage_id = ''
        print(text_manager.get("logs.new_stage_created"))
    
    def _editor_load_stage(self, stage_num):
        """指定番号のステージを読み込み"""
        stage_file = os.path.join(self.stages_dir, f"STAGE_{stage_num:03d}.stage")
        
        if not os.path.exists(stage_file):
            print(text_manager.get("logs.stage_not_found", stage_num, stage_file))
            return
        
        # ステージを読み込み
        stage_data = StageLoader.load_stage(stage_file)
        self.current_stage_id = stage_data['stage_id']
        
        # グリッド形状を更新
        shape = stage_data['grid_shape']
        cell_size = self.grid.cell_size
        grid_width = len(shape[0]) * cell_size
        grid_height = len(shape) * cell_size
        offset_x = (self.screen_width - grid_width) // 2
        offset_y = (self.screen_height - grid_height) // 2
        
        self.grid = Grid(shape, cell_size, offset_x, offset_y)
        
        # エディタセルマップを初期化
        self.editor_cell_map = {}
        for cell in self.grid.valid_cells:
            self.editor_cell_map[cell] = 'A'
        
        # ピース情報からセルマップを設定
        for piece_data in stage_data['pieces']:
            base_row = piece_data['position'][0]
            base_col = piece_data['position'][1]
            for r, c in piece_data['cells']:
                cell = (base_row + r, base_col + c)
                if cell in self.editor_cell_map:
                    self.editor_cell_map[cell] = piece_data['id']
        
        print(text_manager.get("logs.loaded_stage", self.current_stage_id, stage_data['name']))
    
    def _editor_click(self, pos, button):
        """エディタモードでのクリック処理"""
        mx, my = pos
        row, col = self.grid.pixel_to_cell(mx, my)
        
        # 中クリック: グリッドの有効/無効を切り替え
        if button == 2:
            # 最大サイズ内かチェック
            if 0 <= row < self.editor_max_rows and 0 <= col < self.editor_max_cols:
                if (row, col) in self.editor_cell_map:
                    # 有効→無効
                    del self.editor_cell_map[(row, col)]
                    # グリッドからも削除
                    if (row, col) in self.grid.valid_cells:
                        self.grid.valid_cells.remove((row, col))
                        self.grid.shape[row][col] = 0
                else:
                    # 無効→有効
                    self.editor_cell_map[(row, col)] = 'A'
                    # グリッドにも追加
                    if (row, col) not in self.grid.valid_cells:
                        self.grid.valid_cells.append((row, col))
                        # shapeを拡張する必要があれば拡張
                        while len(self.grid.shape) <= row:
                            self.grid.shape.append([0] * self.editor_max_cols)
                        while len(self.grid.shape[row]) <= col:
                            self.grid.shape[row].append(0)
                        self.grid.shape[row][col] = 1
            return
        
        if (row, col) in self.editor_cell_map:
            current_id = self.editor_cell_map[(row, col)]
            idx = self.piece_ids.index(current_id)
            
            if button == 1:  # 左クリック: 次のID
                idx = (idx + 1) % len(self.piece_ids)
            elif button == 3:  # 右クリック: 前のID
                idx = (idx - 1) % len(self.piece_ids)
            
            self.editor_cell_map[(row, col)] = self.piece_ids[idx]
    
    def _print_design(self):
        """設計結果を.stageファイルに保存"""
        # ピースIDごとにセルをグループ化
        pieces = {}
        for (row, col), pid in self.editor_cell_map.items():
            if pid not in pieces:
                pieces[pid] = []
            pieces[pid].append((row, col))
        
        # ピースデータを作成
        pieces_list = []
        for pid in sorted(pieces.keys()):
            cells = pieces[pid]
            if cells:
                min_row = min(c[0] for c in cells)
                min_col = min(c[1] for c in cells)
                local_cells = [(r - min_row, c - min_col) for r, c in cells]
                pieces_list.append({
                    'id': pid,
                    'position': (min_row, min_col),
                    'cells': sorted(local_cells)
                })
        
        # ステージIDを決定（既存の場合は上書き、新規の場合は新しい番号）
        stage_num = self._current_stage_num()
        if stage_num is not None:
            # 既存ステージを上書き
            stage_id = self.current_stage_id
        else:
            # 新規ステージ: 既存の最大番号+1
            # （ファイル数+1だと欠番がある時に既存ステージを上書きしてしまう）
            max_num = 0
            for path in StageLoader.list_stages(self.stages_dir):
                existing_id = os.path.splitext(os.path.basename(path))[0]
                existing_num = self._stage_id_to_num(existing_id)
                if existing_num is not None and existing_num > max_num:
                    max_num = existing_num
            stage_num = max_num + 1
            stage_id = f"STAGE_{stage_num:03d}"
        
        # ファイルパス
        output_path = os.path.join(self.stages_dir, f"{stage_id}.stage")
        
        # 保存
        StageLoader.save_stage(
            filepath=output_path,
            stage_id=stage_id,
            name=f"Stage {stage_num}",
            difficulty=1,
            grid_shape=self.grid.shape,
            pieces=pieces_list
        )
        
        self.current_stage_id = stage_id
        self.save_message = text_manager.get("ui.save_message", stage_num)
        self.save_message_timer = 120  # 2秒表示
        print(text_manager.get("logs.saved_file", output_path))

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
        
        # Analytics: Retry
        try:
            analytics.send_event("retry", {
                "stage_id": self.current_stage_id,
                "cause": "user_reset"
            })
        except Exception as e:
            print(f"[Game] Analytics error (non-blocking): {e}")
        
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
            self.editor_mode = False
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
                self._cached_stage_num_text = None
                self._cached_stage_label_text = None
                self._cached_ranking_surfaces = None
                self._cached_instructions = None
                self._cached_privacy_surfaces = None
                self._cached_title_surfaces = None
                self._cached_save_message_text = None
                self._timer_cache_text = None
                self._timer_cache_key = None
                
                # Analytics: Level Start
                try:
                    analytics.send_event("level_start", {
                        "stage_id": self.current_stage_id,
                        "difficulty": stage_data.get('difficulty', 1)
                    })
                except Exception as e:
                    print(f"[Game] Analytics error (non-blocking): {e}")
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
        if not self.game_clear and not self.editor_mode:
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
        
        if self.editor_mode:
            # エディタモード: セルマップを描画
            self._draw_editor()
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
        if self.game_clear and not self.editor_mode:
            self._draw_clear_message()
        
        # 操作説明
        self._draw_instructions()
        
        # ステージ番号（右上）
        if not self.editor_mode:
            self._draw_stage_number()
        
        # 保存メッセージ
        if self.save_message:
            self._draw_save_message()
            
        # タイマー描画
        if self.show_timer and not self.editor_mode:
            self._draw_timer()
            
        # プライバシーポリシー（最前面にオーバーレイ）
        if self.privacy_mode:
            self._draw_privacy_policy()
        
        pygame.display.flip()
    
    def _draw_editor(self):
        """エディタモードの描画"""
        cell_size = self.grid.cell_size
        
        # 最大サイズのグリッド線をうっすら描画
        for row in range(self.editor_max_rows):
            for col in range(self.editor_max_cols):
                if (row, col) not in self.editor_cell_map:
                    # 無効セル: うっすらとした線で表示
                    x, y = self.grid.cell_to_pixel(row, col)
                    # pygame.Rect の生成を削減
                    pygame.draw.rect(self.screen, (60, 60, 70), (x, y, cell_size, cell_size), 1)
        
        # 有効セルを描画（ピースID付き）
        for (row, col), pid in self.editor_cell_map.items():
            x, y = self.grid.cell_to_pixel(row, col)
            
            # ピースIDに応じた色
            if pid not in self.piece_ids:
                self.piece_ids.append(pid)
            
            idx = self.piece_ids.index(pid)
            color = PIECE_COLORS[idx % len(PIECE_COLORS)]
            
            # pygame.Rect の生成を削減
            pygame.draw.rect(self.screen, color, (x, y, cell_size, cell_size))
            pygame.draw.rect(self.screen, (0, 0, 0), (x, y, cell_size, cell_size), 2)
            
            # ピースID文字
            font = self.font_ui
            text = font.render(pid, True, (255, 255, 255))
            text_rect = text.get_rect(center=(x + cell_size // 2, y + cell_size // 2))
            self.screen.blit(text, text_rect)

        # ページ・操作ガイド表示
        start_stage = (self.editor_page * 10) + 1
        end_stage = (self.editor_page + 1) * 10
        page_info = text_manager.get("ui.editor_info", self.editor_page + 1, start_stage, end_stage)
        
        info_text = self.font_ui.render(page_info, True, (200, 200, 200))
        self.screen.blit(info_text, (20, self.screen_height - 40))
    
    def _draw_clear_message(self):
        """クリアメッセージを描画"""
        # ステージ番号
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
            # ランキング表示に合わせて全体を上にずらす（さらに上へ：重なり回避）
            text_rect = self.text_all_clear.get_rect(center=(self.screen_width // 2 - 20, self.screen_height // 2 - 140))
            

            
            # 描画
            self.screen.blit(stage_text, stage_rect)
            self.screen.blit(self.text_all_clear, text_rect)
            
            # ランキングキャッシュ生成・描画
            if self._cached_ranking_surfaces is None:
                 # 開始位置Yの計算が必要
                 start_y = self.screen_height // 2 + 50 - 80 + 30
                 self._generate_ranking_cache(start_y)
                 
                 # 背景描画のために矩形計算も必要だが、簡略化のため
                 # 以前の矩形描画ロジックは「文字が見やすくなる背景」用だったので、
                 # キャッシュ生成時に矩形も計算するか、あるいは固定サイズで描画するか。
                 # ここでは「レンダリング負荷」が主原因なので、背景矩形計算（Union）は残してもよいが、
                 # Renderそのものをループ内でやらないことが重要。
            
            # 矩形計算（軽量なので残す、ただしRender済みのSurfaceサイズを使う）
            # ...元のロジックが複雑な依存関係にあるので、
            # 思い切って「背景描画」もキャッシュに含めるか、背景描画を固定サイズにするのが良い。
            # ここでは「キャッシュがあればそれを使う」単純なアプローチにする。
            
            # 背景の再計算は面倒なので、キャッシュ生成時に背景Rectも計算して保存しておくアプローチに変更すべきだが
            # 今はフリーズ回避優先。背景は「前回と同じ」でよければ...
            
            # 簡易対応：背景の矩形計算を省略し、固定サイズまたは全画面暗転にする手もあるが、
            # 元の見た目を維持したい。
            
            # よって、_generate_ranking_cache で Rectリストも作る。
            
            option_rects = [] # 使わないが変数エラー回避
            rank_surfaces = [] # 使わない
            
            # ----------------------------------------------------------------
            # リファクタリング: オールクリア画面の描画は重いため、
            # 全体を1つのSurfaceに描画するか、キャッシュ済みリストを描画する。
            # 背景枠の計算のためにはRectが必要。
            # ----------------------------------------------------------------
            
            if self._cached_ranking_surfaces is None:
                start_y = self.screen_height // 2 + 50 - 80 + 30
                self._generate_ranking_cache(start_y)

            # 背景描画のためにRectを結合
            total_rect = stage_rect.union(text_rect)
            for s, r in self._cached_ranking_surfaces:
                total_rect = total_rect.union(r)
            
            bg_rect = total_rect.inflate(60, 120)
            pygame.draw.rect(self.screen, (0, 0, 0), bg_rect)
            pygame.draw.rect(self.screen, (255, 215, 0), bg_rect, 3)
            
            # 描画
            self.screen.blit(stage_text, stage_rect)
            self.screen.blit(self.text_all_clear, text_rect)
            
            # キャッシュされたランキング描画
            if self._cached_ranking_surfaces:
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
            seconds = time_ms // 1000
            ms = (time_ms % 1000) // 100
            minutes = seconds // 60
            seconds = seconds % 60
            hours = minutes // 60
            minutes = minutes % 60
            
            time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}.{ms}"
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
        
        # 半透明で描画（Surfaceを使用）
        ghost_alpha = 80  # 透明度（0-255）
        ghost_color = piece.color
        
        for dr, dc in piece.cells:
            x, y = self.grid.cell_to_pixel(base_row + dr, base_col + dc)
            # 半透明Surfaceを作成して描画
            ghost_surface = pygame.Surface((cell_size, cell_size), pygame.SRCALPHA)
            ghost_surface.set_alpha(ghost_alpha)
            pygame.draw.rect(ghost_surface, ghost_color, (0, 0, cell_size, cell_size))
            self.screen.blit(ghost_surface, (x, y))
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
        """経過時間を描画（最適化版）"""
        if not self.show_timer:
            return
            
        now = pygame.time.get_ticks() / 1000.0
        
        # 更新頻度制御（10ms）
        if now - self._timer_last_update < self._timer_update_interval:
            # 表示内容は変わらない（または頻度制限内）→ キャッシュがあれば表示
            if self._timer_cache_text:
                text = self._timer_cache_text
                rect = text.get_rect(bottomright=(self.screen_width - 10, self.screen_height - 10))
                self.screen.blit(text, rect)
            return

        self._timer_last_update = now
            
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
        current_editor = self.editor_mode
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
            
            instructions = []
            if self.editor_mode:
                stage_info = self.current_stage_id if self.current_stage_id else "(New)"
                # (text, color, action) の3要素で揃える（描画側が3要素で展開するため）
                instructions = [
                    (text_manager.get("instructions.editor.title", stage_info), (255, 200, 100), None),
                    (text_manager.get("instructions.editor.load"), (180, 180, 180), None),
                    (text_manager.get("instructions.editor.new"), (180, 180, 180), None),
                    (text_manager.get("instructions.editor.save"), (180, 180, 180), None),
                    (text_manager.get("instructions.editor.change_id"), (180, 180, 180), None),
                    (text_manager.get("instructions.editor.toggle_grid"), (180, 180, 180), None),
                    (text_manager.get("instructions.editor.exit"), (200, 200, 255), None),
                ]
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
