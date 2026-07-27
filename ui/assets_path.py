import os
import sys


def get_asset_path(*relative_parts: str) -> str:
    if getattr(sys, "frozen", False):
        base_dir = sys._MEIPASS
    else:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, "ui", "assets", *relative_parts)
