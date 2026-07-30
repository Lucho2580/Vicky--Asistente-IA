import sys
import threading
import time
from pathlib import Path

import webview

from core.env_config import consume_and_scrub_embedded_ai_api_key
from web_ui.api import Api

TEMPLATE_PATH = Path(__file__).parent / "templates" / "index.html"
ICON_PATH = Path(__file__).parent.parent / "packaging" / "pyinstaller" / "icon.ico"
WINDOW_TITLE = "Vicky"


def _set_app_user_model_id() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("LaVianda.Vicky")
    except Exception:
        pass


def _set_windows_window_icon() -> None:
    if sys.platform != "win32" or not ICON_PATH.exists():
        return

    time.sleep(1)
    try:
        import ctypes

        user32 = ctypes.windll.user32
        hwnd = user32.FindWindowW(None, WINDOW_TITLE)
        if not hwnd:
            return

        IMAGE_ICON = 1
        LR_LOADFROMFILE = 0x00000010
        LR_DEFAULTSIZE = 0x00000040
        hicon = user32.LoadImageW(0, str(ICON_PATH), IMAGE_ICON, 0, 0, LR_LOADFROMFILE | LR_DEFAULTSIZE)
        if not hicon:
            return

        WM_SETICON = 0x0080
        ICON_SMALL = 0
        ICON_BIG = 1
        user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, hicon)
        user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, hicon)
    except Exception:
        pass


def main() -> None:
    _set_app_user_model_id()
    consume_and_scrub_embedded_ai_api_key()

    api = Api()
    window = webview.create_window(
        WINDOW_TITLE,
        url=str(TEMPLATE_PATH),
        js_api=api,
        width=1100,
        height=750,
        min_size=(900, 600),
    )
    api.set_window(window)

    threading.Thread(target=_set_windows_window_icon, daemon=True).start()

    icon_arg = str(ICON_PATH) if ICON_PATH.exists() else None
    webview.start(icon=icon_arg)


if __name__ == "__main__":
    main()
