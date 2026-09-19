# -*- coding: utf-8 -*-
"""Promo cut, second pass: a real per-frame camera instead of a static plate.

build_promo.py rendered one composition per beat and let ffmpeg zoom it. That
reads as a slideshow. Here every frame is composed on its own, so the card can
rotate while it travels, settle on an easing curve, and push into a cropped
region of the product — the moves a motion designer actually makes.

Pillow draws the visuals; libass burns the Arabic type on top, animated with
ASS transforms.

    python tools/build_promo2.py              # frames + captions + encode
    python tools/build_promo2.py frames       # visuals only
"""
import math
import os
import shutil
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
OUT = os.path.join(BUILD, "promo2")
FRAMES = os.path.join(OUT, "frames")

W, H, FPS = 1920, 1080, 30

LIGHT_BG = (243, 246, 243)
LIGHT_BG2 = (225, 234, 229)
DARK_BG = (9, 30, 24)
DARK_BG2 = (6, 20, 16)
ACCENT = (16, 122, 96)
ACCENT_LIT = (63, 191, 151)

# ---------------------------------------------------------------- easing
def ease_out(t):
    return 1 - (1 - t) ** 3


def ease_in_out(t):
    return 3 * t * t - 2 * t * t * t


def mix(a, b, t):
    return a + (b - a) * t


# ---------------------------------------------------------------- scenes
# move: from/to camera state — ang (degrees of fake Y rotation), scale,
# x/y offsets in px, applied to the (optionally cropped) product shot.
SCENES = [
    {"id": "hook", "dur": 3.6, "theme": "dark", "kind": "ambient",
     "page": "p11",
     "lines": [("الوثيقة الناقصة", 0), ("توقف المعاملة.", 1)]},

    {"id": "hero", "dur": 4.2, "theme": "light", "kind": "card", "page": "p11",
     "from": {"ang": -13, "sc": 1.03, "x": 0, "y": 210},
     "to":   {"ang": -4,  "sc": 1.00, "x": 0, "y": 118},
     "width": 0.62, "align": "center", "text_pos": "top",
     "lines": [("ومن مساحة واحدة،", 0), ("تدير ملف الوافد كله.", 1)]},

    {"id": "kpi", "dur": 3.8, "theme": "light", "kind": "card", "page": "p11",
     "crop": (0.02, 0.30, 0.78, 0.56),
     "from": {"ang": 7, "sc": 1.00, "x": -40, "y": 30},
     "to":   {"ang": 2, "sc": 1.03, "x": 40,  "y": 10},
     "width": 0.56, "align": "right", "text_pos": "left",
     "lines": [("أربعة أرقام", 0), ("تحدد عمل اليوم.", 1)]},

    {"id": "ocr", "dur": 4.0, "theme": "light", "kind": "card", "page": "p16",
     "from": {"ang": -16, "sc": 1.03, "x": 120, "y": 60},
     "to":   {"ang": -5,  "sc": 1.03, "x": 40,  "y": 20},
     "width": 0.56, "align": "left", "text_pos": "right",
     "lines": [("أرفق النسخة،", 0), ("وتُقرأ خاناتها فورًا.", 1)]},

    {"id": "journal", "dur": 4.0, "theme": "dark", "kind": "card", "page": "p53",
     "crop": (0.0, 0.18, 0.80, 0.72),
     "from": {"ang": 14, "sc": 1.02, "x": -60, "y": 40},
     "to":   {"ang": 4,  "sc": 1.03, "x": 30,  "y": 0},
     "width": 0.56, "align": "right", "text_pos": "left",
     "lines": [("كل تعديل موقّع.", 0), ("السجل لا يتغيّر بصمت.", 1)]},

    {"id": "diff", "dur": 3.6, "theme": "light", "kind": "card", "page": "p54",
     "crop": (0.05, 0.22, 0.85, 0.74),
     "from": {"ang": -10, "sc": 1.03, "x": 60, "y": -20},
     "to":   {"ang": -2,  "sc": 1.02, "x": 0,  "y": 20},
     "width": 0.60, "align": "center", "text_pos": "top",
     "lines": [("قبل وبعد،", 0), ("ومن عدّل، ولماذا.", 1)]},

    {"id": "forecast", "dur": 4.0, "theme": "light", "kind": "card", "page": "p67",
     "crop": (0.02, 0.26, 0.76, 0.86),
     "from": {"ang": 12, "sc": 1.00, "x": -50, "y": 40},
     "to":   {"ang": 3,  "sc": 1.03, "x": 20,  "y": 0},
     "width": 0.56, "align": "right", "text_pos": "left",
     "lines": [("توقّع الإقبال", 0), ("أربعًا وعشرين ساعة.", 1)]},

    {"id": "numbers", "dur": 4.2, "theme": "accent", "kind": "type",
     "lines": [("٨٦٫٩٢ مقابل ٩٣٫٩٧", 0)],
     "sub": "تحسّن ٧٫٥٪ في متوسط الخطأ على ٦٬٧٧٣ ساعة اختبار — لا «نسبة دقة»"},

    {"id": "roles", "dur": 3.8, "theme": "light", "kind": "card", "page": "p81",
     "crop": (0.02, 0.20, 0.80, 0.78),
     "from": {"ang": -14, "sc": 1.02, "x": 80, "y": 30},
     "to":   {"ang": -4,  "sc": 1.03, "x": 20, "y": 0},
     "width": 0.56, "align": "left", "text_pos": "right",
     "lines": [("أربعة أدوار،", 0), ("والتحقق على الخادم.", 1)]},

    {"id": "end", "dur": 4.0, "theme": "light", "kind": "type",
     "lines": [("سَنَد ٢", 0)],
     "sub": "sanad-v2.songokualshareef.workers.dev · نموذج أولي ببيانات اصطناعية"},
]


# ---------------------------------------------------------------- plates
_bg_cache = {}


def background(theme):
    if theme in _bg_cache:
        return _bg_cache[theme]
    if theme == "light":
        top, bottom, bloom, strength = LIGHT_BG, LIGHT_BG2, (150, 220, 195), 0.20
    elif theme == "accent":
        top, bottom, bloom, strength = (9, 56, 45), DARK_BG2, ACCENT_LIT, 0.40
    else:
        top, bottom, bloom, strength = DARK_BG, DARK_BG2, ACCENT_LIT, 0.34
    img = Image.new("RGB", (W, H), bottom)
    d = ImageDraw.Draw(img)
    for y in range(H):
        t = (y / H) ** 0.9
        d.line([(0, y), (W, y)],
               fill=tuple(int(mix(top[i], bottom[i], t)) for i in range(3)))
    glow = Image.new("RGB", (W, H), (0, 0, 0))
    ImageDraw.Draw(glow).ellipse([W * 0.30, -H * 0.55, W * 1.10, H * 0.70], fill=bloom)
    glow = glow.filter(ImageFilter.GaussianBlur(210))
    img = Image.blend(img, Image.blend(img, glow, 0.55), strength)
    _bg_cache[theme] = img
    return img


def rounded(img, radius):
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, img.size[0] - 1, img.size[1] - 1],
                                           radius=radius, fill=255)
    out = img.convert("RGBA")
    out.putalpha(mask)
    return out


def perspective_coeffs(src, dst):
    a, b = [], []
    for (sx, sy), (dx, dy) in zip(src, dst):
        a.append([dx, dy, 1, 0, 0, 0, -sx * dx, -sx * dy])
        a.append([0, 0, 0, dx, dy, 1, -sy * dx, -sy * dy])
        b.extend([sx, sy])
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
            if r == i or not a[r][i]:
                continue
            f = a[r][i]
            for j in range(i, n):
                a[r][j] -= f * a[i][j]
            b[r] -= f * b[i]
    return b


def rotate_y(card, deg):
    """Perspective squeeze that reads as a Y-axis rotation of `deg` degrees."""
    w, h = card.size
    k = math.sin(math.radians(deg)) * 0.34
    pad_x, pad_y = int(w * 0.06), int(h * 0.10)
    canvas = Image.new("RGBA", (w + pad_x * 2, h + pad_y * 2), (0, 0, 0, 0))
    canvas.paste(card, (pad_x, pad_y), card)
    w2, h2 = canvas.size
    inset = abs(k) * w2
    drop = abs(k) * h2 * 0.42
    if k > 0:
        dst = [(inset, drop), (w2, 0), (w2, h2), (inset, h2 - drop)]
    else:
        dst = [(0, 0), (w2 - inset, drop), (w2 - inset, h2 - drop), (0, h2)]
    src = [(0, 0), (w2, 0), (w2, h2), (0, h2)]
    return canvas.transform((w2, h2), Image.PERSPECTIVE,
                            perspective_coeffs(src, dst), Image.BILINEAR)


def cast_shadow(plate, offset, blur, opacity):
    """Blur at quarter scale, on a padded canvas so the falloff is not clipped."""
    pad = int(blur)
    w, h = plate.size[0] + pad * 2, plate.size[1] + pad * 2
    sw, sh = max(1, w // 4), max(1, h // 4)
    sil = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
    small = plate.resize((max(1, plate.size[0] // 4), max(1, plate.size[1] // 4)),
                         Image.BILINEAR)
    sil.paste((4, 18, 14, opacity), (pad // 4, pad // 4), small.split()[3])
    sil = sil.filter(ImageFilter.GaussianBlur(blur / 4.0))
    return sil.resize((w, h), Image.BILINEAR), pad


def load_card(scene):
    shot = Image.open(os.path.join(SHOTS, scene["page"] + ".png")).convert("RGB")
    if scene.get("crop"):
        x0, y0, x1, y1 = scene["crop"]
        shot = shot.crop((int(x0 * shot.size[0]), int(y0 * shot.size[1]),
                          int(x1 * shot.size[0]), int(y1 * shot.size[1])))
    target_w = int(W * scene.get("width", 0.72))
    target_h = int(target_w * shot.size[1] / shot.size[0])
    shot = shot.resize((target_w, target_h), Image.LANCZOS)
    card = rounded(shot, 22)
    edge = Image.new("RGBA", card.size, (0, 0, 0, 0))
    ImageDraw.Draw(edge).rounded_rectangle([0, 0, card.size[0] - 1, card.size[1] - 1],
                                           radius=22, outline=(255, 255, 255, 70), width=2)
    card.alpha_composite(edge)
    return card


# ---------------------------------------------------------------- ambient
def ambient_chips(page):
    """Real KPI tiles lifted out of the product, floated as depth elements."""
    shot = Image.open(os.path.join(SHOTS, page + ".png")).convert("RGB")
    boxes = [(0.030, 0.336, 0.204, 0.516), (0.217, 0.336, 0.386, 0.516),
             (0.399, 0.336, 0.569, 0.516), (0.587, 0.336, 0.759, 0.516)]
    chips = []
    for i, (x0, y0, x1, y1) in enumerate(boxes):
        c = shot.crop((int(x0 * shot.size[0]), int(y0 * shot.size[1]),
                       int(x1 * shot.size[0]), int(y1 * shot.size[1])))
        scale = [0.20, 0.165, 0.185, 0.155][i]
        tw = int(W * scale)
        c = c.resize((tw, int(tw * c.size[1] / c.size[0])), Image.LANCZOS)
        chips.append(rounded(c, 16))
    # anchor, drift vector, depth blur
    layout = [((0.055, 0.145), (16, -12), 0.0),
              ((0.735, 0.115), (-14, 10), 1.8),
              ((0.775, 0.660), (-18, -14), 0.0),
              ((0.085, 0.690), (20, 12), 2.4)]
    return list(zip(chips, layout))


def draw_connectors(img, pts, color, width=2):
    d = ImageDraw.Draw(img, "RGBA")
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        cx, cy = (x0 + x1) / 2, min(y0, y1) - abs(x1 - x0) * 0.18
        prev = None
        for i in range(41):
            t = i / 40
            x = (1 - t) ** 2 * x0 + 2 * (1 - t) * t * cx + t * t * x1
            y = (1 - t) ** 2 * y0 + 2 * (1 - t) * t * cy + t * t * y1
            if prev:
                d.line([prev, (x, y)], fill=color, width=width)
            prev = (x, y)


# ---------------------------------------------------------------- render
def render_scene(scene, index, frame_no):
    n = int(scene["dur"] * FPS)
    bg = background(scene["theme"])
    if scene["kind"] == "type":
        for i in range(n):
            t = ease_in_out(i / max(1, n - 1))
            frame = bg.copy()
            # a slow breathing glow keeps a type card from sitting dead still
            if scene["theme"] == "accent":
                gl = Image.new("RGB", (W, H), (0, 0, 0))
                r = int(W * (0.30 + 0.05 * math.sin(t * math.pi)))
                ImageDraw.Draw(gl).ellipse([W // 2 - r, H // 2 - r // 2,
                                            W // 2 + r, H // 2 + r // 2], fill=ACCENT_LIT)
                gl = gl.filter(ImageFilter.GaussianBlur(190))
                frame = Image.blend(frame, Image.blend(frame, gl, 0.5), 0.16)
            frame.save(os.path.join(FRAMES, "f%05d.png" % (frame_no + i)))
        return frame_no + n

    if scene["kind"] == "ambient":
        chips = ambient_chips(scene["page"])
        for i in range(n):
            p = i / max(1, n - 1)
            e = ease_out(p)
            frame = bg.copy().convert("RGBA")
            pts = []
            for ci, (chip, (anchor, drift, blur)) in enumerate(chips):
                sc = 0.92 + 0.08 * e
                cw, ch = int(chip.size[0] * sc), int(chip.size[1] * sc)
                layer = chip.resize((cw, ch), Image.BILINEAR)
                if blur:
                    layer = layer.filter(ImageFilter.GaussianBlur(blur))
                x = int(anchor[0] * W + drift[0] * e)
                y = int(anchor[1] * H + drift[1] * e)
                alpha = min(1.0, max(0.0, (p - 0.04 * ci) * 4.5))
                if alpha <= 0:
                    continue
                if alpha < 1:
                    a = layer.split()[3].point(lambda v: int(v * alpha))
                    layer.putalpha(a)
                sh, pad = cast_shadow(layer, (0, 0), 90, 96)
                frame.alpha_composite(sh, (x - pad + 4, y - pad + 30))
                frame.alpha_composite(layer, (x, y))
                pts.append((x + cw / 2, y + ch / 2))
            draw_connectors(frame, pts, (63, 191, 151, 46))
            frame.convert("RGB").save(os.path.join(FRAMES, "f%05d.png" % (frame_no + i)))
        return frame_no + n

    card = load_card(scene)
    a, b = scene["from"], scene["to"]
    for i in range(n):
        p = i / max(1, n - 1)
        e = ease_out(p)
        ang = mix(a["ang"], b["ang"], e)
        sc = mix(a["sc"], b["sc"], e)
        dx = mix(a["x"], b["x"], e)
        dy = mix(a["y"], b["y"], e)
        cw, ch = int(card.size[0] * sc), int(card.size[1] * sc)
        layer = card.resize((cw, ch), Image.BILINEAR)
        layer = rotate_y(layer, ang)
        align = scene.get("align", "center")
        if align == "center":
            x = (W - layer.size[0]) // 2
        elif align == "left":
            x = int(W * 0.04)
        else:
            x = W - layer.size[0] - int(W * 0.04)
        y = (H - layer.size[1]) // 2
        x, y = int(x + dx), int(y + dy)
        frame = background(scene["theme"]).copy().convert("RGBA")
        sh, pad = cast_shadow(layer, (0, 0), 150,
                              72 if scene["theme"] == "light" else 120)
        frame.alpha_composite(sh, (x - pad + 6, y - pad + 62))
        frame.alpha_composite(layer, (x, y))
        frame.convert("RGB").save(os.path.join(FRAMES, "f%05d.png" % (frame_no + i)))
    return frame_no + n


# ---------------------------------------------------------------- captions
def ts(sec):
    return "%d:%02d:%05.2f" % (int(sec // 3600), int(sec % 3600 // 60), sec % 60)


def rtl(s):
    return "‫" + s.replace("{", "(").replace("}", ")") + "‬"


HEAD = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 2
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Dark,IBM Plex Sans Arabic,70,&H001E2F14,&H00FFFFFF,&H00FFFFFF,&H00000000,0,0,0,0,100,100,0,0,1,0,0,5,60,60,60,1
Style: DarkHi,IBM Plex Sans Arabic,70,&H00607A10,&H00FFFFFF,&H00FFFFFF,&H00000000,0,0,0,0,100,100,0,0,1,0,0,5,60,60,60,1
Style: Lite,IBM Plex Sans Arabic,70,&H00F2F7F1,&H00FFFFFF,&H4C06170F,&H00000000,0,0,0,0,100,100,0,0,1,0,2,5,60,60,60,1
Style: LiteHi,IBM Plex Sans Arabic,70,&H0097BF3F,&H00FFFFFF,&H4C06170F,&H00000000,0,0,0,0,100,100,0,0,1,0,2,5,60,60,60,1
Style: Big,IBM Plex Sans Arabic,124,&H00F2F7F1,&H00FFFFFF,&H4C06170F,&H00000000,0,0,0,0,100,100,0,0,1,0,2,5,80,80,80,1
Style: BigDark,IBM Plex Sans Arabic,124,&H001E2F14,&H00FFFFFF,&H00FFFFFF,&H00000000,0,0,0,0,100,100,0,0,1,0,0,5,80,80,80,1
Style: Sub,IBM Plex Sans Arabic,36,&H00C3D2C9,&H00FFFFFF,&H4C06170F,&H00000000,0,0,0,0,100,100,0,0,1,0,1,5,120,120,120,1
Style: SubDark,IBM Plex Sans Arabic,36,&H00566849,&H00FFFFFF,&H00FFFFFF,&H00000000,0,0,0,0,100,100,0,0,1,0,0,5,120,120,120,1
Style: Mark,IBM Plex Sans Arabic,26,&H007E9589,&H00FFFFFF,&H4C06170F,&H00000000,0,0,0,0,100,100,0,0,1,0,0,3,70,70,54,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def build_ass(path):
    ev = []
    t = 0.0
    for sc in SCENES:
        end = t + sc["dur"] - 0.14
        light = sc["theme"] == "light"
        if sc["kind"] == "type":
            base = "BigDark" if light else "Big"
            for i, (ln, _hi) in enumerate(sc["lines"]):
                st = t + 0.20 + i * 0.22
                ev.append("Dialogue: 0,%s,%s,%s,,0,0,0,,"
                          "{\\fad(260,220)\\pos(960,470)\\fscx104\\fscy104"
                          "\\t(0,420,\\fscx100\\fscy100)}%s" % (ts(st), ts(end), base, rtl(ln)))
            if sc.get("sub"):
                ev.append("Dialogue: 0,%s,%s,%s,,0,0,0,,{\\fad(320,220)\\pos(960,620)}%s"
                          % (ts(t + 0.55), ts(end), "SubDark" if light else "Sub", rtl(sc["sub"])))
            t += sc["dur"]
            continue

        style = ("Dark" if light else "Lite")
        style_hi = ("DarkHi" if light else "LiteHi")
        pos = sc.get("text_pos", "top")
        if pos == "top":
            xs, ys, step = 960, 108, 84
        elif pos == "left":
            xs, ys, step = 400, 470, 86
        else:
            xs, ys, step = 1520, 470, 86
        for i, (ln, hi) in enumerate(sc["lines"]):
            st = t + 0.24 + i * 0.20
            y = ys + i * step
            ev.append("Dialogue: 0,%s,%s,%s,,0,0,0,,"
                      "{\\fad(240,200)\\move(%d,%d,%d,%d,0,460)\\fscx103\\fscy103"
                      "\\t(0,420,\\fscx100\\fscy100)}%s"
                      % (ts(st), ts(end), style_hi if hi else style,
                         xs, y + 26, xs, y, rtl(ln)))
        t += sc["dur"]
    ev.append("Dialogue: 0,%s,%s,Mark,,0,0,0,,{\\fad(500,500)}%s"
              % (ts(0.5), ts(t - 0.5), rtl("لقطات فعلية من سَنَد ٢ · بيانات اصطناعية")))
    with open(path, "w", encoding="utf-8") as f:
        f.write(HEAD + "\n".join(ev) + "\n")
    return t


# ---------------------------------------------------------------- driver
def run(cmd, cwd=None):
    p = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", cwd=cwd)
    if p.returncode != 0:
        sys.stdout.write((p.stderr or "")[-1600:] + "\n")
        raise SystemExit("ffmpeg failed")


def render_frames():
    if os.path.isdir(FRAMES):
        shutil.rmtree(FRAMES)
    os.makedirs(FRAMES)
    n = 0
    for i, sc in enumerate(SCENES):
        n = render_scene(sc, i, n)
        print("scene %-9s %5d frames" % (sc["id"], n), flush=True)
    return n


def encode():
    run('ffmpeg -loglevel error -y -framerate %d -i frames/f%%05d.png '
        '-vf "ass=promo2.ass:fontsdir=../fonts,format=yuv420p" '
        '-c:v libx264 -preset slow -crf 18 -movflags +faststart -an sanad-v2-promo-hq.mp4'
        % FPS, cwd=OUT)
    run('ffmpeg -loglevel error -y -i sanad-v2-promo-hq.mp4 -vf "crop=1080:1080:420:0" '
        '-c:v libx264 -preset slow -crf 20 -movflags +faststart -an '
        'sanad-v2-promo-hq-square.mp4', cwd=OUT)
    print("out:", os.path.join(OUT, "sanad-v2-promo-hq.mp4"))


if __name__ == "__main__":
    for d in (OUT, FRAMES):
        os.makedirs(d, exist_ok=True)
    step = sys.argv[1] if len(sys.argv) > 1 else "all"
    if step in ("all", "captions"):
        total = build_ass(os.path.join(OUT, "promo2.ass"))
        print("captions ok - %.1fs" % total)
    if step in ("all", "frames"):
        print("frames:", render_frames())
    if step in ("all", "encode"):
        encode()
