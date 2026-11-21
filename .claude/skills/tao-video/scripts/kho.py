#!/usr/bin/env python3
"""Đường dẫn kho của tao-video, theo thư mục Downloads THẬT của máy (Windows cho chuyển Downloads sang ổ khác).

  python kho.py              → in <KHO>        = <Downloads>/tao-video-kho
  python kho.py --downloads  → in <Downloads>  (thư mục Downloads thật, vd E:\\Downloads)

Trong script:  from kho import KHO, DOWNLOADS
Đặt biến môi trường TAO_VIDEO_KHO để dùng kho ở chỗ khác hẳn.
Không dùng "~/Downloads": máy đã chuyển Downloads sang ổ E thì ~/Downloads không còn, script sẽ tạo kho rỗng mới ở ổ C.
"""
import os
import sys


def _downloads():
    if os.name == "nt":
        try:  # SHGetKnownFolderPath(FOLDERID_Downloads): cùng chỗ File Explorer đang dùng
            import ctypes
            import uuid
            from ctypes import wintypes

            class GUID(ctypes.Structure):
                _fields_ = [("d1", wintypes.DWORD), ("d2", wintypes.WORD), ("d3", wintypes.WORD), ("d4", ctypes.c_ubyte * 8)]

            u = uuid.UUID("{374DE290-123F-4565-9164-39C4925E467B}")
            g = GUID(u.fields[0], u.fields[1], u.fields[2], (ctypes.c_ubyte * 8)(*u.bytes[8:]))
            p = ctypes.c_wchar_p()
            if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(g), 0, None, ctypes.byref(p)) == 0:
                path = p.value
                ctypes.windll.ole32.CoTaskMemFree(p)
                if path:
                    return path
        except Exception:
            pass
    else:
        try:  # Linux: thư mục theo xdg-user-dirs
            import subprocess
            path = subprocess.run(["xdg-user-dir", "DOWNLOAD"], capture_output=True, text=True).stdout.strip()
            if path and os.path.isdir(path):
                return path
        except Exception:
            pass
    return os.path.expanduser("~/Downloads")


DOWNLOADS = _downloads()
KHO = os.environ.get("TAO_VIDEO_KHO") or os.path.join(DOWNLOADS, "tao-video-kho")

if __name__ == "__main__":
    print(DOWNLOADS if "--downloads" in sys.argv[1:] else KHO)
