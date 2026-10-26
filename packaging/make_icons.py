"""Generate every app icon from the one logo: assets/logo.png (square, ideally 1024 px).

    python packaging/make_icons.py

Writes cleftune/web/icon.png (UI, window, Linux menu), icon.ico (Windows) and icon.icns (macOS).
packaging/build.py runs this automatically, so replacing assets/logo.png is all a rebrand needs.
"""

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
LOGO = ROOT / "assets" / "logo.png"
WEB = ROOT / "cleftune" / "web"


def main() -> None:
    logo = Image.open(LOGO).convert("RGBA")
    if logo.width != logo.height:
        side = max(logo.size)
        square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
        square.paste(logo, ((side - logo.width) // 2, (side - logo.height) // 2))
        logo = square
    big = logo.resize((1024, 1024), Image.LANCZOS) if logo.width != 1024 else logo
    big.resize((256, 256), Image.LANCZOS).save(WEB / "icon.png", optimize=True)
    big.save(WEB / "icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    big.save(WEB / "icon.icns")
    print(f"icons written from {LOGO.relative_to(ROOT)} ({logo.width}x{logo.height})")


if __name__ == "__main__":
    main()
