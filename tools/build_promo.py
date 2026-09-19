# -*- coding: utf-8 -*-
"""Builds the short promo cut: kinetic Arabic type over tilted UI screens.

Different animal from build_video.py. That one narrates every screen for six
minutes; this one is a 70-second pitch — big type, 3D-tilted product shots,
fast cuts. Compositions are pre-rendered in Pillow (gradient, rounded card,
soft shadow, perspective tilt), then ffmpeg adds drift and burns the type.

    python tools/build_promo.py            # assets + beats + final
    python tools/build_promo.py beats      # re-render the shot compositions
"""
import math
import os
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFilter

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BUILD = os.path.join(ROOT, "build")
SHOTS = os.path.join(BUILD, "shots")
FONTS = os.path.join(BUILD, "fonts")
OUT = os.path.join(BUILD, "promo")
for _d in (BUILD, OUT):
    os.makedirs(_d, exist_ok=True)

W, H, FPS = 1920, 1080, 30

INK = (8, 26, 21)
INK_2 = (12, 43, 35)
ACCENT = (63, 191, 151)
PAPER = (238, 242, 239)

# kind: "type" = full-bleed type beat, "shot" = tilted screen beat
# side: which half the screen card sits on ("r" or "l")
BEATS = [
    {"kind": "type", "dur": 4.5, "theme": "dark",
     "lines": ["الوثيقة الناقصة", "توقف المعاملة."], "hi": 1},
    {"kind": "type", "dur": 3.5, "theme": "dark",
     "lines": ["سَنَد ٢"], "hi": 0, "sub": "الوثيقة · الثقة · القرار"},
    {"kind": "shot", "dur": 5.0, "page": "p11", "side": "l", "theme": "dark",
     "lines": ["مساحة واحدة", "لكل ملفات الوافدين."], "hi": 0},
    {"kind": "shot", "dur": 5.0, "page": "p16", "side": "r", "theme": "dark",
     "lines": ["أرفق النسخة،", "وتُقرأ خاناتها فورًا."], "hi": 1},
    {"kind": "shot", "dur": 4.5, "page": "p19", "side": "l", "theme": "dark",
     "lines": ["محفوظة بمصدرها", "وببصمة ملفها."], "hi": 1},
    {"kind": "type", "dur": 4.0, "theme": "accent",
     "lines": ["كل تعديل موقّع.", "السجل لا يتغيّر بصمت."], "hi": 0},
    {"kind": "shot", "dur": 5.0, "page": "p53", "side": "r", "theme": "dark",
     "lines": ["سلسلة توقيعات", "تكشف أي تغيير."], "hi": 0},
    {"kind": "shot", "dur": 4.5, "page": "p54", "side": "l", "theme": "dark",
     "lines": ["قبل وبعد،", "ومن عدّل، ولماذا."], "hi": 0},
    {"kind": "shot", "dur": 4.5, "page": "p58", "side": "r", "theme": "dark",
     "lines": ["مؤشرات للمراجعة،", "لا أحكامًا."], "hi": 1},
    {"kind": "shot", "dur": 5.0, "page": "p62", "side": "l", "theme": "dark",
     "lines": ["حاكِ القرار", "قبل ما تتخذه."], "hi": 1},
    {"kind": "shot", "dur": 5.0, "page": "p67", "side": "r", "theme": "dark",
     "lines": ["توقّع الإقبال", "٢٤ ساعة قادمة."], "hi": 1},
    {"kind": "type", "dur": 5.0, "theme": "accent",
     "lines": ["٨٦٫٩٢ مقابل ٩٣٫٩٧"], "hi": 0,
     "sub": "تحسّن ٧٫٥٪ في متوسط الخطأ على ٦٬٧٧٣ ساعة اختبار — لا «نسبة دقة»"},
    {"kind": "shot", "dur": 4.5, "page": "p81", "side": "l", "theme": "dark",
     "lines": ["أربعة أدوار،", "والتحقق على الخادم."], "hi": 1},
    {"kind": "shot", "dur": 4.0, "page": "p87", "side": "r", "theme": "dark",
     "lines": ["وعلى الجوال", "بنفس الصلاحيات."], "hi": 0},
    {"kind": "type", "dur": 5.5, "theme": "light",
     "lines": ["سَنَد ٢"], "hi": 0,
     "sub": "sanad-v2.songokualshareef.workers.dev · نموذج أولي ببيانات اصطناعية"},
]


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def background(theme):
    """Vertical wash plus a soft accent bloom — the ground every beat sits on."""
    if theme == "light":
        top, bottom, bloom = PAPER, (222, 231, 226), (120, 210, 180)
    elif theme == "accent":
        top, bottom, bloom = (10, 58, 46), INK, ACCENT
    else:
        top, bottom, bloom = INK_2, INK, ACCENT
    img = Image.new("RGB", (W, H), bottom)
    d = ImageDraw.Draw(img)
    for y in range(H):
        d.line([(0, y), (W, y)], fill=lerp(top, bottom, (y / H) ** 0.85))
    glow = Image.new("RGB", (W, H), (0, 0, 0))
    g = ImageDraw.Draw(glow)
    g.ellipse([W * 0.52, -H * 0.42, W * 1.22, H * 0.62], fill=bloom)
    glow = glow.filter(ImageFilter.GaussianBlur(190))
    img = Image.blend(img, Image.blend(img, glow, 0.5), 0.34 if theme != "light" else 0.16)
    # faint rule grid, keeps the flat wash from looking empty
    d = ImageDraw.Draw(img, "RGBA")
    line = (255, 255, 255, 12) if theme != "light" else (10, 40, 32, 14)
    for x in range(0, W, 120):
        d.line([(x, 0), (x, H)], fill=line)
    for y in range(0, H, 120):
        d.line([(0, y), (W, y)], fill=line)
    return img


def rounded(img, radius):
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, img.size[0] - 1, img.size[1] - 1],
                                           radius=radius, fill=255)
    out = img.convert("RGBA")
    out.putalpha(mask)
    return out


def perspective_coeffs(src, dst):
    """Solves the 8 coefficients Image.transform(PERSPECTIVE) wants."""
    matrix = []
    for (sx, sy), (dx, dy) in zip(src, dst):
        matrix.append([dx, dy, 1, 0, 0, 0, -sx * dx, -sx * dy])
        matrix.append([0, 0, 0, dx, dy, 1, -sy * dx, -sy * dy])
    a = matrix
    b = [c for p in src for c in p]
    # Gaussian elimination, 8x8 — no numpy dependency for eight rows
    n = 8
    for i in range(n):
        p = max(range(i, n), key=lambda r: abs(a[r][i]))
        a[i], a[p] = a[p], a[i]
        b[i], b[p] = b[p], b[i]
        piv = a[i][i]
        for j in range(i, n):
            a[i][j] /= piv
        b[i] /= piv
        for r in range(n):
            if r == i:
                continue
            f = a[r][i]
            if not f:
                continue
            for j in range(i, n):
                a[r][j] -= f * a[i][j]
            b[r] -= f * b[i]
    return b


def tilt(card, angle, squeeze=0.13):
    """Fakes a Y-axis rotation: pull the far edge in and shorten it."""
    w, h = card.size
    pad = int(w * 0.10)
    canvas = Image.new("RGBA", (w + pad * 2, h + pad * 2), (0, 0, 0, 0))
    canvas.paste(card, (pad, pad), card)
    w2, h2 = canvas.size
    k = squeeze * (1 if angle > 0 else -1)
    inset = abs(k) * w2
    drop = abs(k) * h2 * 0.5
    if k > 0:  # far edge on the left
        dst = [(inset, drop), (w2, 0), (w2, h2), (inset, h2 - drop)]
    else:      # far edge on the right
        dst = [(0, 0), (w2 - inset, drop), (w2 - inset, h2 - drop), (0, h2)]
    src = [(0, 0), (w2, 0), (w2, h2), (0, h2)]
    coeffs = perspective_coeffs(src, dst)
    return canvas.transform((w2, h2), Image.PERSPECTIVE, coeffs, Image.BICUBIC)


def shot_plate(page, side, theme):
    """Background + tilted screenshot card with a soft cast shadow."""
    bg = background(theme)
    shot = Image.open(os.path.join(SHOTS, page + ".png")).convert("RGB")
    card_w = int(W * 0.50)
    card_h = int(card_w * shot.size[1] / shot.size[0])
    shot = shot.resize((card_w, card_h), Image.LANCZOS)
    card = rounded(shot, 26)
    border = Image.new("RGBA", card.size, (0, 0, 0, 0))
    ImageDraw.Draw(border).rounded_rectangle(
        [0, 0, card.size[0] - 1, card.size[1] - 1], radius=26,
        outline=(255, 255, 255, 46), width=2)
    card.alpha_composite(border)

    angle = 1 if side == "l" else -1
    plate = tilt(card, angle)

    x = int(W * 0.02) if side == "l" else W - plate.size[0] - int(W * 0.02)
    y = int((H - plate.size[1]) / 2 + H * 0.06)

    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sil = Image.new("RGBA", plate.size, (0, 0, 0, 0))
    sil.paste((0, 0, 0, 190), (0, 0), plate.split()[3])
    shadow.paste(sil, (x + int(W * 0.012), y + int(H * 0.03)), sil)
    shadow = shadow.filter(ImageFilter.GaussianBlur(38))

    out = bg.convert("RGBA")
    out.alpha_composite(shadow)
    out.alpha_composite(plate, (x, y))
    return out.convert("RGB")


def type_plate(theme):
    return background(theme)


def ts(sec):
    return "%d:%02d:%05.2f" % (int(sec // 3600), int(sec % 3600 // 60), sec % 60)


def rtl(s):
    return "‫" + s.replace("{", "(").replace("}", ")") + "‬"


def build_ass(path):
    """Type is the star here, so each beat gets its own sized, moving lines."""
    head = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 2
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Hero,IBM Plex Sans Arabic,132,&H00F4F8F1,&H00FFFFFF,&H50040F0C,&H00000000,0,0,0,0,100,100,0,0,1,0,2,5,100,100,100,1
Style: HeroHi,IBM Plex Sans Arabic,132,&H0097BF3F,&H00FFFFFF,&H50040F0C,&H00000000,0,0,0,0,100,100,0,0,1,0,2,5,100,100,100,1
Style: HeroDark,IBM Plex Sans Arabic,132,&H00160D06,&H00FFFFFF,&H00FFFFFF,&H00000000,0,0,0,0,100,100,0,0,1,0,0,5,100,100,100,1
Style: Sub,IBM Plex Sans Arabic,40,&H00BFCEC6,&H00FFFFFF,&H50040F0C,&H00000000,0,0,0,0,100,100,0,0,1,0,1.5,5,140,140,100,1
Style: SubDark,IBM Plex Sans Arabic,40,&H004C5B43,&H00FFFFFF,&H00FFFFFF,&H00000000,0,0,0,0,100,100,0,0,1,0,0,5,140,140,100,1
Style: Beat,IBM Plex Sans Arabic,62,&H00F4F8F1,&H00FFFFFF,&H64040F0C,&H00000000,0,0,0,0,100,100,0,0,1,0,2,5,80,80,80,1
Style: BeatHi,IBM Plex Sans Arabic,62,&H0097BF3F,&H00FFFFFF,&H64040F0C,&H00000000,0,0,0,0,100,100,0,0,1,0,2,5,80,80,80,1
Style: Mark,IBM Plex Sans Arabic,30,&H0080998F,&H00FFFFFF,&H64040F0C,&H00000000,0,0,0,0,100,100,0,0,1,0,1,3,90,90,70,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ev = []
    t = 0.0
    for b in BEATS:
        end = t + b["dur"] - 0.18
        light = b["theme"] == "light"
        if b["kind"] == "type":
            base = "HeroDark" if light else "Hero"
            hi = "HeroDark" if light else "HeroHi"
            n = len(b["lines"])
            for i, ln in enumerate(b["lines"]):
                y = 470 + (i - (n - 1) / 2.0) * 170
                st = t + 0.18 + i * 0.26
                style = hi if i == b.get("hi", -1) else base
                ev.append("Dialogue: 0,%s,%s,%s,,0,0,0,,{\\fad(300,240)\\move(960,%d,960,%d)}%s"
                          % (ts(st), ts(end), style, int(y + 26), int(y), rtl(ln)))
            if b.get("sub"):
                ev.append("Dialogue: 0,%s,%s,%s,,0,0,0,,{\\fad(360,240)\\pos(960,%d)}%s"
                          % (ts(t + 0.6), ts(end), "SubDark" if light else "Sub",
                             int(470 + (n / 2.0) * 170 + 60), rtl(b["sub"])))
        else:
            # type sits opposite the card: card on the left, words on the right
            x = 1545 if b["side"] == "l" else 375
            n = len(b["lines"])
            for i, ln in enumerate(b["lines"]):
                y = 500 + (i - (n - 1) / 2.0) * 92
                st = t + 0.22 + i * 0.24
                style = "BeatHi" if i == b.get("hi", -1) else "Beat"
                ev.append("Dialogue: 0,%s,%s,%s,,0,0,0,,{\\fad(280,220)\\move(%d,%d,%d,%d)}%s"
                          % (ts(st), ts(end), style, x + 34, int(y), x, int(y), rtl(ln)))
        t += b["dur"]
    ev.append("Dialogue: 0,%s,%s,Mark,,0,0,0,,{\\fad(400,400)}%s"
              % (ts(0.4), ts(t - 0.4), rtl("لقطات فعلية · بيانات اصطناعية")))
    with open(path, "w", encoding="utf-8") as f:
        f.write(head + "\n".join(ev) + "\n")
    return t


def run(cmd):
    p = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if p.returncode != 0:
        sys.stdout.write((p.stderr or "")[-1500:] + "\n")
        raise SystemExit("ffmpeg failed")


def build_beats():
    paths = []
    for i, b in enumerate(BEATS):
        plate = os.path.join(OUT, "plate%02d.png" % i)
        if b["kind"] == "shot":
            shot_plate(b["page"], b["side"], b["theme"]).save(plate)
        else:
            type_plate(b["theme"]).save(plate)
        frames = int(b["dur"] * FPS)
        clip = os.path.join(OUT, "b%02d.mp4" % i).replace("\\", "/")
        # alternate push-in and pull-out so consecutive cuts never drift alike
        if i % 2 == 0:
            z = "1.02+0.05*on/%d" % frames
        else:
            z = "1.07-0.05*on/%d" % frames
        vf = ("scale=2560:-2,setsar=1,zoompan=z='%s':d=%d:x='iw/2-(iw/zoom/2)'"
              ":y='ih/2-(ih/zoom/2)':s=%dx%d:fps=%d,format=yuv420p" % (z, frames, W, H, FPS))
        run('ffmpeg -loglevel error -y -i "%s" -vf "%s" -frames:v %d -r %d '
            '-c:v libx264 -preset veryfast -crf 19 -pix_fmt yuv420p "%s"'
            % (plate.replace("\\", "/"), vf, frames, FPS, clip))
        paths.append(clip)
        print("beat %02d ok" % i, flush=True)
    lst = os.path.join(OUT, "list.txt")
    with open(lst, "w", encoding="utf-8") as f:
        for p in paths:
            f.write("file '%s'\n" % p)
    return lst


def render_final():
    cwd = os.getcwd()
    os.chdir(OUT)
    try:
        run('ffmpeg -loglevel error -y -f concat -safe 0 -i list.txt -c copy raw.mp4')
        run('ffmpeg -loglevel error -y -i raw.mp4 -vf "ass=promo.ass:fontsdir=../fonts" '
            '-c:v libx264 -preset slow -crf 19 -pix_fmt yuv420p -movflags +faststart '
            '-an sanad-v2-promo.mp4')
        # 1:1 crop for feeds that prefer square
        run('ffmpeg -loglevel error -y -i sanad-v2-promo.mp4 '
            '-vf "crop=1080:1080:420:0" -c:v libx264 -preset slow -crf 20 '
            '-pix_fmt yuv420p -movflags +faststart -an sanad-v2-promo-square.mp4')
    finally:
        os.chdir(cwd)
    print("promo:", os.path.join(OUT, "sanad-v2-promo.mp4"))


if __name__ == "__main__":
    step = sys.argv[1] if len(sys.argv) > 1 else "all"
    if step in ("all", "assets"):
        total = build_ass(os.path.join(OUT, "promo.ass"))
        print("captions ok - %.1fs" % total)
    if step in ("all", "beats"):
        build_beats()
    if step in ("all", "final"):
        render_final()
