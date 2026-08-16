from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent / "icons"
OUT.mkdir(parents=True, exist_ok=True)

def font(size: int, bold: bool = True):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
    ]
    for p in candidates:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()

def make_icon(size: int, maskable: bool = False):
    bg = "#0f172a"
    accent = "#22c55e"
    white = "#f8fafc"
    img = Image.new("RGBA", (size, size), bg)
    d = ImageDraw.Draw(img)

    margin = int(size * (0.18 if maskable else 0.10))
    card = [margin, margin, size - margin, size - margin]
    radius = int(size * 0.18)
    d.rounded_rectangle(card, radius=radius, fill="#111827", outline="#334155", width=max(2, size // 96))

    # chart bars
    bar_bottom = int(size * 0.74)
    bar_w = max(8, int(size * 0.085))
    xs = [0.30, 0.43, 0.56]
    heights = [0.16, 0.25, 0.34]
    for x, h in zip(xs, heights):
        left = int(size * x)
        top = int(bar_bottom - size * h)
        d.rounded_rectangle(
            [left, top, left + bar_w, bar_bottom],
            radius=max(2, bar_w // 3),
            fill=accent,
        )

    # money symbol
    f = font(int(size * 0.34), True)
    text = "$"
    bbox = d.textbbox((0, 0), text, font=f)
    tx = int(size * 0.66 - (bbox[2]-bbox[0]) / 2)
    ty = int(size * 0.43 - (bbox[3]-bbox[1]) / 2 - bbox[1])
    d.text((tx, ty), text, font=f, fill=white)

    return img

files = [
    ("icon-192.png", 192, False),
    ("icon-512.png", 512, False),
    ("icon-maskable-192.png", 192, True),
    ("icon-maskable-512.png", 512, True),
    ("apple-touch-icon.png", 180, False),
    ("favicon-32.png", 32, False),
]

for name, size, maskable in files:
    make_icon(size, maskable).save(OUT / name)

print(f"Generated {len(files)} icons in: {OUT}")
