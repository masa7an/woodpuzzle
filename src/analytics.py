"""
Analytics Module
Handles sending events to Google Analytics 4 (GA4).
Compatible with both Web (emscripten) and Desktop environments.

NOTE: Web上でのイベント送信は無効。
      JS側(gtag)の呼び出しがPygbagのゲームループをブロックしてフリーズするため
      （ROADMAP フェーズ6-3 / 6-4 を参照）。
      Web版のPV計測は index.html に注入したGA4タグが行うので、Python側は不要。

Never raises: callers can invoke send_event() bare, without their own try/except.
"""

import sys
import json


class AnalyticsManager:
    """Manages analytics event tracking."""

    def __init__(self):
        self.is_web = sys.platform == 'emscripten'

        if self.is_web:
            # Web: フリーズ防止のため無効
            print("[Analytics] Web mode detected - Analytics DISABLED to prevent freeze.")
        else:
            # Desktop: コンソールへのログのみ
            print("[Analytics] Desktop mode - logging to console.")

    def send_event(self, event_name, params=None):
        """
        Send an event to GA4 (Desktop only).

        Web: 何もしない（フリーズ防止のため無効）
        Desktop: コンソールに出力
        """
        # Web: Do nothing (disabled)
        if self.is_web:
            return

        try:
            print(f"[Analytics] Event: {event_name}, Params: {json.dumps(params or {})}")
        except Exception as e:
            # ログ出力ごときでゲームを止めない
            print(f"[Analytics] Failed to log event (non-blocking): {e}")


# Global instance
analytics = AnalyticsManager()
