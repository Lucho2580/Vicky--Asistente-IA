import sys

_pywinstyles = None
_available = None


def _load_pywinstyles():
    global _pywinstyles, _available
    if _available is not None:
        return _pywinstyles

    if sys.platform != "win32":
        _available = False
        return None

    try:
        import pywinstyles

        _pywinstyles = pywinstyles
        _available = True
    except Exception:
        _available = False

    return _pywinstyles


def is_available() -> bool:
    _load_pywinstyles()
    return bool(_available)


def reset_widget_opacity(widget) -> None:
    pywinstyles = _load_pywinstyles()
    if pywinstyles is None:
        return
    try:
        pywinstyles.set_opacity(widget, value=1.0)
    except Exception:
        pass
