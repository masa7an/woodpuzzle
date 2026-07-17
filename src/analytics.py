"""
Analytics Module
Handles sending events to Google Analytics 4 (GA4).
Compatible with both Web (emscripten) and Desktop environments.
"""

import sys
import json

class AnalyticsManager:
    """Manages analytics event tracking."""
    
    def __init__(self):
        self.is_web = sys.platform == 'emscripten'
        self.gtag = None
        self._gtag_initialized = False
        
        if self.is_web:
            # Web: Lazy initialization of gtag (will be initialized on first use)
            print("[Analytics] Web mode detected - GA4 events will be enabled on first use")
        else:
            # Desktop: Keep analytics logging
            print("[Analytics] Desktop mode - logging to console.")
    
    def _ensure_gtag(self):
        """Ensure gtag is initialized (lazy initialization)"""
        if self._gtag_initialized:
            return self.gtag is not None
        
        if not self.is_web:
            return False
        
        try:
            import platform
            if hasattr(platform, 'window'):
                window = platform.window
                if hasattr(window, 'gtag') and callable(window.gtag):
                    self.gtag = window.gtag
                    self._gtag_initialized = True
                    print("[Analytics] GA4 events enabled via platform.window.gtag")
                    return True
                else:
                    # Try accessing via window object directly
                    if hasattr(window, 'gtag'):
                        self.gtag = window.gtag
                        self._gtag_initialized = True
                        print("[Analytics] GA4 events enabled (direct access)")
                        return True
        except Exception as e:
            print(f"[Analytics] Failed to initialize gtag: {e}")
        
        self._gtag_initialized = True
        return False

    def send_event(self, event_name, params=None):
        """
        Send an event to GA4.
        Web: Uses platform.window.gtag directly (non-blocking)
        Desktop: Logs to console
        """
        if params is None:
            params = {}
        
        if self.is_web:
            # Web: Send event via gtag (non-blocking, lazy initialization)
            if self._ensure_gtag() and self.gtag:
                try:
                    # Call gtag('event', event_name, params)
                    # This should be non-blocking as gtag uses dataLayer.push internally
                    self.gtag('event', event_name, params)
                    print(f"[Analytics] Event sent: {event_name}, Params: {json.dumps(params)}")
                except Exception as e:
                    # Silently fail to prevent freeze - just log the error
                    print(f"[Analytics] Failed to send event (non-blocking): {e}")
            else:
                # gtag not available - skip silently to prevent freeze
                pass
        else:
            # Desktop Mode: Log to console
            print(f"[Analytics] Event: {event_name}, Params: {json.dumps(params)}")

# Global instance
analytics = AnalyticsManager()
