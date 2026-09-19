# -*- coding: utf-8 -*-
"""Builds an MP4 motion explainer for SANAD v2 from real UI screenshots."""
import json, os, subprocess, sys
from PIL import Image, ImageDraw

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BUILD = os.path.join(ROOT, "build")
SHOTS = os.path.join(BUILD, "shots")
FONTS = os.path.join(BUILD, "fonts")
OUT = os.path.join(BUILD, "scenes")
for _d in (BUILD, OUT, FONTS):
    os.makedirs(_d, exist_ok=True)

FONT_URLS = {
    "IBMPlexSansArabic-SemiBold.ttf":
        "https://cdn.jsdelivr.net/gh/IBM/plex@master/packages/plex-sans-arabic/"
        "fonts/complete/ttf/IBMPlexSansArabic-SemiBold.ttf",
    "IBMPlexSansArabic-Regular.ttf":
        "https://cdn.jsdelivr.net/gh/IBM/plex@master/packages/plex-sans-arabic/"
        "fonts/complete/ttf/IBMPlexSansArabic-Regular.ttf",
}


def fetch_fonts():
    """libass shapes Arabic through harfbuzz; it still needs the face on disk."""
    import urllib.request
    for name, url in FONT_URLS.items():
        dst = os.path.join(FONTS, name)
        if os.path.exists(dst) and os.path.getsize(dst) > 40000:
            continue
        with urllib.request.urlopen(url) as r, open(dst, "wb") as f:
            f.write(r.read())
        print("font:", name)

W, H, FPS = 1920, 1080, 30

# page, chapter, eyebrow, title, line, dur
SCENES = [
 [None, "البداية", "جولة داخل المنتج", "سَنَد ٢ — كما يظهر على الشاشة",
  "٣٤ محطة داخل المنصة، كل واحدة بلقطة فعلية من الواجهة. الأشخاص والوثائق اصطناعية بالكامل.", 12],
 ["p09", "الدخول", "الباب", "حساب لكل موظف، لا حساب مشترك",
  "الجلسة تعيش ٨ ساعات، والكوكي محمي، وتغيير الدور يبطل الجلسات فورًا.", 11],
 ["p11", "الدخول", "نقطة البداية", "أربعة أرقام تحدد عمل اليوم",
  "الحالات في مساحتك، ما تمت مراجعته، ما ينتظر المراجعة، وما نسخته ناقصة.", 11],
 ["p13", "الوثيقة", "الوحدة الأولى · سَنَد", "ملف الوافد يبدأ بمرجع دخول",
  "الحقول الأساسية أولًا، ثم تُبنى عليها الوثائق والحركات والمراجعات.", 10],
 ["p15", "الوثيقة", "المشكلة على الشاشة", "حالة تصل دون أصل الجواز",
  "البيانات النصية موجودة، والمستند الذي تطلبه الجهة القنصلية غير موجود.", 12],
 ["p16", "الوثيقة", "قراءة الصور", "خمس خانات تُقرأ داخل المتصفح",
  "الاسم ورقم الوثيقة والجنسية المكتوبة والميلاد والانتهاء. والعربية تُراجع يدويًا.", 13],
 ["p19", "الوثيقة", "الحفظ", "النسخة محفوظة ومعها من أرفقها ومتى",
  "بصمة الملف تكشف تبدّل البايتات — لا أصالة الجواز ولا هوية حامله.", 11],
 ["p20", "الوثيقة", "قبل الاعتماد", "قارن خانات النسخة بسجل الدخول",
  "الاختلاف مؤشر يستدعي مراجعة بشرية، وقد يكون له سبب مشروع.", 12],
 ["p22", "الثقة", "الوحدة الثانية · موثوقية السجلات", "لا حفظ بلا سبب مكتوب",
  "هوية الموظف من الجلسة، والسبب يُحفظ مع الخانة قبل وبعد في نفس المعاملة.", 11],
 ["p23", "الوثيقة", "المساعد", "إجابة مسندة إلى الملف",
  "بحث دلالي محلي يربط كل إجابة بمصدرها، والمزود الخارجي محجوب افتراضيًا.", 12],
 ["p25", "الوثيقة", "الخانات", "بيانات المسافر والجواز والتأشيرة",
  "مجموعات حقول واضحة، وكل تعديل يمر بنفس مسار السبب والتوثيق.", 10],
 ["p28", "الوثيقة", "علامتا الموجب والسالب", "ما يدعم الملف وما يضعفه",
  "قراءة أسرع لتفاصيل التأشيرة دون إخفاء أي تفصيل.", 10],
 ["p32", "الوثيقة", "الحركات", "ربط النسخة بحركة السفر",
  "جواز الدخول يُربط بالوثيقة البديلة عند الخروج، وتظهر الحركتان في الحزمة.", 11],
 ["p35", "الوثيقة", "في الملف نفسه", "مستندان لحالة واحدة",
  "لا مجلدات جانبية ولا نسخ متفرقة: كل المستندات داخل ملف الحالة بمصادرها.", 10],
 ["p36", "الوثيقة", "المراجع", "حفظ مرجع الأمر ولقطته",
  "يحفظ النظام المرجع والمصدر ولقطة من الوثيقتين — ولا ينفذ أوامر فعلية.", 11],
 ["p39", "الوثيقة", "المخرج", "مسودة واحدة قابلة للطباعة",
  "الخانات والحركات والنسخة والملاحظات في حزمة ثابتة يعتمدها المشرف.", 11],
 ["p42", "الوثيقة", "محاكاة معلنة", "احفظ النسخة قبل وصول الوافد",
  "نسخة مبكرة تُراجع وتُسلّم وتُستلم داخل محاكاة، ثم تُربط بملف الدخول.", 12],
 ["p47", "الوثيقة", "داخل المحاكاة", "خطوة التسليم موثقة كغيرها",
  "كل انتقال يترك أثرًا في السجل: من سلّم، ومن استلم، ومتى.", 10],
 ["p51", "القرار", "الوحدة الثالثة · التخطيط التشغيلي", "لكل مرحلة مدة ومسؤول",
  "استكمال، مراجعة، انتظار — وفصل بين ما هو داخلي وما ينتظر جهة خارجية.", 11],
 ["p53", "الثقة", "سلامة السجل", "فحص التوقيعات ومطابقة البيانات",
  "الشاشة تعرض آخر مئتي تغيير، والفحص يقرأ سجل المساحة كاملًا.", 13],
 ["p54", "الثقة", "تفاصيل الحدث", "الخانة كما كانت وكما صارت",
  "افتح أي حدث لترى الموظف والسبب وقيمة كل خانة قبل التعديل وبعده.", 11],
 ["p58", "الوثيقة", "فحوص قابلة للتفسير", "اختلاف الحقول وتكرار الملف وكثرة التعديلات",
  "قواعد معلنة وليست نموذج كشف تزوير مدرب. كل مؤشر يتطلب مراجعة بشرية.", 12],
 ["p60", "القرار", "أين تتعطل المعاملة", "الملفات المتبقية حسب الموارد والوارد",
  "محاكاة حسابية بمعاملات يدخلها المستخدم، وشرح مكشوف لطريقة الحساب.", 12],
 ["p62", "القرار", "قبل وبعد إضافة مراجع", "الداخل يتسارع، والخارج لا يختفي",
  "زيادة المراجعين تقلص المراجعة الداخلية، ويبقى انتظار القنصلية كما هو.", 13],
 ["p63", "القرار", "القرار البشري", "اعتماد أو رفض — مع الافتراضات",
  "يُحفظ القرار مع لقطة الحالة. لا نقل موظفين ولا إجراء حكومي.", 11],
 ["p65", "التوقع", "الوحدة الرابعة · توقع الإقبال", "اختر المطار والصالة والتاريخ",
  "نموذج مدرب على بيانات عامة، والهدف عدد الركاب غير الأمريكيين في الساعة.", 12],
 ["p67", "التوقع", "المخرج", "منحنى توقع لأربع وعشرين ساعة",
  "لا يعتمد التوقع على أعداد مستقبلية، والمفقود في البيانات ليس صفرًا.", 12],
 ["p71", "التوقع", "الأثر التشغيلي", "ماذا لو زدنا الكاونترات؟",
  "محاكاة حسابية فوق ناتج التوقع — لا قياس ميداني ولا التزام بأداء فعلي.", 11],
 ["p73", "التوقع", "الأرقام الحقيقية", "متوسط الخطأ ٨٦٫٩٢ مقابل ٩٣٫٩٧",
  "على ٦٬٧٧٣ ساعة اختبار: تحسّن ٧٫٥٠٪ في متوسط الخطأ — وليست نسبة دقة.", 14],
 ["p76", "الإدارة", "اللوحة", "توزيع الملفات والحركات",
  "أعداد الملفات حسب نوع التأشيرة وحالة النسخة، مع تصدير الجداول.", 10],
 ["p78", "الإدارة", "الأرشيف", "كل النسخ في مكان واحد",
  "استعراض الوثائق المرتبطة بالحالات مع مصادرها وحالتها.", 10],
 ["p81", "الحماية", "الوحدة الخامسة · الحسابات والحماية", "أدوار وجلسات وتحكم بخروج البيانات",
  "إخفاء الزر ليس حماية: الصلاحية تُفحص على الخادم في كل طلب.", 13],
 ["p87", "الحماية", "الاستخدام", "الواجهة نفسها على شاشة صغيرة",
  "نفس الصلاحيات ونفس السجل، بترتيب يناسب الجوال.", 10],
 [None, "الخاتمة", "جرّبها بنفسك", "نموذج يعمل، وحدوده مكتوبة",
  "الرابط في وصف المقطع، وحساب العرض للقراءة فقط. لا ترفع أي بيانات حقيقية.", 12],
]

ACCENT = (63, 191, 151)


def make_scrim():
    """Bottom-up dark gradient + soft vignette, overlaid on every shot."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for y in range(H):
        p = y / (H - 1)
        if p < 0.44:
            a = 0
        elif p < 0.72:
            a = int(236 * ((p - 0.44) / 0.28) ** 1.25)
        else:
            a = 236 + int(14 * (p - 0.72) / 0.28)
        d.line([(0, y), (W, y)], fill=(6, 22, 18, min(250, a)))
    # top strip so the corner chips stay readable
    for y in range(150):
        a = int(190 * (1 - y / 150) ** 1.2)
        d.line([(0, y), (W, y)], fill=(6, 22, 18, a))
    img.save(os.path.join(BUILD, "scrim.png"))


def make_card(name, bg, bar=True):
    img = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(img)
    if bar:
        d.rectangle([160, 470, 160 + 300, 470 + 8], fill=ACCENT)
    # faint grid
    for x in range(0, W, 96):
        d.line([(x, 0), (x, H)], fill=tuple(min(255, c + 8) for c in bg))
    for y in range(0, H, 96):
        d.line([(0, y), (W, y)], fill=tuple(min(255, c + 8) for c in bg))
    img.save(os.path.join(BUILD, name))


def esc(s):
    s = s.replace("\\", "").replace("{", "(").replace("}", ")")
    return "‫" + s + "‬"


def build_ass(path):
    head = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 2
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Eyebrow,IBM Plex Sans Arabic,34,&H00B6D96F,&H00FFFFFF,&H64100C06,&H00000000,0,0,0,0,100,100,0,0,1,1.8,0.8,3,120,120,258,1
Style: Title,IBM Plex Sans Arabic,68,&H00F2F6F0,&H00FFFFFF,&H78100C06,&H00000000,0,0,0,0,100,100,0,0,1,2.6,1.2,3,120,120,166,1
Style: Line,IBM Plex Sans Arabic,38,&H00C5CEB9,&H00FFFFFF,&H64100C06,&H00000000,0,0,0,0,100,100,0,0,1,1.8,0.8,3,120,120,86,1
Style: Tag,IBM Plex Sans Arabic,28,&H00DAE3CF,&H00FFFFFF,&H78100C06,&H00000000,0,0,0,0,100,100,0,0,1,1.8,0.8,1,110,110,112,1
Style: Idx,IBM Plex Sans Arabic,26,&H0096AFA4,&H00FFFFFF,&H64100C06,&H00000000,0,0,0,0,100,100,0,0,1,1.6,0.8,1,110,110,62,1
Style: Big,IBM Plex Sans Arabic,96,&H001C220B,&H00FFFFFF,&H00FFFFFF,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,160,160,300,1
Style: BigLine,IBM Plex Sans Arabic,42,&H004A5137,&H00FFFFFF,&H00FFFFFF,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,160,160,560,1
Style: BigEye,IBM Plex Sans Arabic,32,&H005F7A0E,&H00FFFFFF,&H00FFFFFF,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,160,160,236,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    def ts(sec):
        h = int(sec // 3600); m = int(sec % 3600 // 60); s = sec % 60
        return "%d:%02d:%05.2f" % (h, m, s)

    lines = []
    t = 0.0
    for i, sc in enumerate(SCENES):
        page, chap, eyebrow, title, line, dur = sc
        end = t + dur - 0.25
        card = page is None
        fade = "{\\fad(320,260)}"
        if card:
            lines.append("Dialogue: 0,%s,%s,BigEye,,0,0,0,,%s%s" % (ts(t + 0.25), ts(end), fade, esc(eyebrow)))
            lines.append("Dialogue: 0,%s,%s,Big,,0,0,0,,%s%s" % (ts(t + 0.5), ts(end), fade, esc(title)))
            lines.append("Dialogue: 0,%s,%s,BigLine,,0,0,0,,%s%s" % (ts(t + 0.85), ts(end), fade, esc(line)))
        else:
            lines.append("Dialogue: 0,%s,%s,Eyebrow,,0,0,0,,%s%s" % (ts(t + 0.3), ts(end), fade, esc(eyebrow)))
            lines.append("Dialogue: 0,%s,%s,Title,,0,0,0,,%s%s" % (ts(t + 0.5), ts(end), fade, esc(title)))
            lines.append("Dialogue: 0,%s,%s,Line,,0,0,0,,%s%s" % (ts(t + 0.75), ts(end), fade, esc(line)))
            lines.append("Dialogue: 0,%s,%s,Tag,,0,0,0,,%s‫لقطة فعلية من سَنَد ٢ · بيانات اصطناعية‬" % (ts(t + 0.5), ts(end), fade))
        lines.append("Dialogue: 0,%s,%s,Idx,,0,0,0,,%s‫%02d / %d · %s‬" % (ts(t + 0.4), ts(end), fade, i + 1, len(SCENES), chap))
        t += dur
    with open(path, "w", encoding="utf-8") as f:
        f.write(head + "\n".join(lines) + "\n")
    return t


def run(cmd):
    p = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        sys.stdout.write((p.stderr or "")[-1800:] + "\n")
        raise SystemExit("ffmpeg failed: " + cmd[:160])


def build_scenes():
    listing = []
    for i, sc in enumerate(SCENES):
        page, chap, eyebrow, title, line, dur = sc
        out = os.path.join(OUT, "s%02d.mp4" % i).replace("\\", "/")
        frames = int(dur * FPS)
        if page is None:
            src = os.path.join(BUILD, "card_end.png" if i else "card_open.png").replace("\\", "/")
            vf = ("zoompan=z='1.0+0.035*on/%d':d=%d:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
                  ":s=%dx%d:fps=%d,format=yuv420p" % (frames, frames, W, H, FPS))
            cmd = ('ffmpeg -loglevel error -y -i "%s" -vf "%s" -frames:v %d -r %d '
                   '-c:v libx264 -preset veryfast -crf 20 -pix_fmt yuv420p "%s"' % (src, vf, frames, FPS, out))
        else:
            src = os.path.join(SHOTS, page + ".png").replace("\\", "/")
            scrim = os.path.join(BUILD, "scrim.png").replace("\\", "/")
            zdir = 1 if i % 2 == 0 else -1
            if zdir > 0:
                z = "1.0+0.075*on/%d" % frames
            else:
                z = "1.075-0.075*on/%d" % frames
            ypos = "ih/2-(ih/zoom/2)-(ih*0.06)"
            vf = ("[0:v]scale=2560:-2,setsar=1,zoompan=z='%s':d=%d:x='iw/2-(iw/zoom/2)':y='%s'"
                  ":s=%dx%d:fps=%d[bg];[bg][1:v]overlay=0:0,format=yuv420p[v]"
                  % (z, frames, ypos, W, H, FPS))
            cmd = ('ffmpeg -loglevel error -y -i "%s" -i "%s" '
                   '-filter_complex "%s" -map "[v]" -frames:v %d -r %d -c:v libx264 -preset veryfast -crf 20 '
                   '-pix_fmt yuv420p "%s"' % (src, scrim, vf, frames, FPS, out))
        run(cmd)
        listing.append(out)
        print("scene %02d ok" % i, flush=True)
    lst = os.path.join(BUILD, "list.txt")
    with open(lst, "w", encoding="utf-8") as f:
        for p in listing:
            f.write("file '%s'\n" % p)
    return lst


def render_final():
    """Concatenate the scene clips, then burn the Arabic captions in one pass."""
    lst = os.path.join(BUILD, "list.txt").replace("\\", "/")
    raw = os.path.join(BUILD, "raw.mp4").replace("\\", "/")
    ass = os.path.join(BUILD, "captions.ass").replace("\\", "/")
    out = os.path.join(BUILD, "sanad-v2-motion.mp4").replace("\\", "/")
    light = os.path.join(BUILD, "sanad-v2-motion-light.mp4").replace("\\", "/")
    run('ffmpeg -loglevel error -y -f concat -safe 0 -i "%s" -c copy "%s"' % (lst, raw))
    # run from BUILD so the filter argument stays free of drive letters and colons
    cwd = os.getcwd()
    os.chdir(BUILD)
    try:
        run('ffmpeg -loglevel error -y -i raw.mp4 -vf "ass=captions.ass:fontsdir=fonts" '
            '-c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p -movflags +faststart '
            '-an sanad-v2-motion.mp4')
        run('ffmpeg -loglevel error -y -i sanad-v2-motion.mp4 -c:v libx264 -preset medium '
            '-crf 27 -pix_fmt yuv420p -movflags +faststart -an sanad-v2-motion-light.mp4')
    finally:
        os.chdir(cwd)
    print("video:", out)
    print("light:", light)


if __name__ == "__main__":
    step = sys.argv[1] if len(sys.argv) > 1 else "all"
    if step in ("all", "assets"):
        fetch_fonts()
        make_scrim()
        make_card("card_open.png", (238, 242, 239))
        make_card("card_end.png", (238, 242, 239))
        total = build_ass(os.path.join(BUILD, "captions.ass"))
        print("assets ok · total %.1fs" % total)
    if step in ("all", "scenes"):
        lst = build_scenes()
        print("list:", lst)
    if step in ("all", "final"):
        render_final()
