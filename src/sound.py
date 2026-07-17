"""
サウンド管理モジュール
効果音の再生を担当
"""

import pygame
import os


class SoundManager:
    """効果音を管理するクラス"""
    
    def __init__(self):
        self.sounds = {}
        self.enabled = True
        self._initialized = False
    
    def init(self):
        """サウンドシステムを初期化"""
        try:
            pygame.mixer.init()
            self._initialized = True
            self._load_sounds()
        except pygame.error as e:
            print(f"Sound initialization failed: {e}")
            self._initialized = False
    
    def _load_sounds(self):
        """効果音を読み込み"""
        if not self._initialized:
            return
        
        # 効果音ファイルのパス
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        se_path = os.path.join(base_path, "assets", "SE")
        
        # スナップ音
        snap_file = os.path.join(se_path, "snap.wav")
        if os.path.exists(snap_file):
            try:
                self.sounds["snap"] = pygame.mixer.Sound(snap_file)
                self.sounds["snap"].set_volume(0.5)
            except pygame.error as e:
                print(f"Failed to load snap sound: {e}")
        
        # クリア音
        clear_file = os.path.join(se_path, "clear.wav")
        if os.path.exists(clear_file):
            try:
                self.sounds["clear"] = pygame.mixer.Sound(clear_file)
                self.sounds["clear"].set_volume(0.5)
            except pygame.error as e:
                print(f"Failed to load clear sound: {e}")
    
    def play(self, sound_name):
        """効果音を再生"""
        if not self._initialized or not self.enabled:
            return
        
        if sound_name in self.sounds:
            self.sounds[sound_name].play()
    
    def set_enabled(self, enabled):
        """効果音の有効/無効を切り替え"""
        self.enabled = enabled


# グローバルインスタンス
sound_manager = SoundManager()
