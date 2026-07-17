import json
import os
import sys
import platform

class TextManager:
    """テキストリソースを管理するクラス"""
    
    def __init__(self):
        self.data = {}
        self.current_language = 'en'
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
    def init(self, lang='en'):
        """テキストデータをロード"""
        self.load_language(lang)

    def load_language(self, lang):
        """指定された言語をロード"""
        json_path = os.path.join(self.base_dir, 'assets', 'data', f'text_{lang}.json')
        
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                self.data = json.load(f)
            self.current_language = lang
            print(f"Loaded text resources: {lang}")
            
            # Web版の場合、HTMLのlang属性も更新
            if sys.platform == 'emscripten':
                try:
                    # Pygbag/Emscripten環境下でのJS実行
                    import platform
                    # window.document.documentElement.lang = lang
                    # platform.window.eval(...) は pygbagでは直接使えない場合があるが
                    # 簡易的に標準出力に出しても効果はないため、
                    # 実際には platform.window オブジェクトがあれば使用する
                    if hasattr(platform, 'window'):
                        platform.window.document.documentElement.lang = lang
                except Exception as e:
                    print(f"Failed to update HTML lang: {e}")
                    
        except Exception as e:
            print(f"Failed to load text resources for {lang}: {e}")
            # フォールバック: 英語を試す
            if lang != 'en':
                print("Falling back to English...")
                self.load_language('en')

    def get(self, key_path, *args):
        """
        ドット区切りのキーでテキストを取得
        例: get("ui.clear") -> "CLEAR!"
        引数がある場合はフォーマットする
        """
        keys = key_path.split('.')
        value = self.data
        
        try:
            for k in keys:
                value = value[k]
            
            if isinstance(value, str):
                if args:
                    return value.format(*args)
                return value
            return value
        except (KeyError, TypeError) as e:
            # キーが見つからない場合はキー自体を返す（開発中に気づけるように）
            return key_path

# シングルトンインスタンス
text_manager = TextManager()
