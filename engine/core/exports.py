"""The three downloadables: the workbook, the chart pack, the slide deck.

Everything is written from a finished run, so a file can never disagree with
what the dashboard showed. The chart palette is the interface's own, so a chart
pasted into a report still looks like the app it came from.

Charts follow the rules that matter for a chart someone will act on: one axis
per chart (never two scales), a category's colour follows the category and not
its rank, values labelled directly rather than left to a gridline, and no
figure invented that the run did not produce.
"""
import io
import os
import zipfile

# AAU's palette, the same values the interface uses.
GREEN = "#0A7A3A"
BRIGHT = "#0FA64F"
DEEP = "#14563A"
RED = "#E0303F"
META = "#63736A"
PAGE = "#F4F6F5"
HAIR = "#E4EAE6"
INK = "#1A1A1A"

# Colour follows the college, never its position in the sorted list -- a
# filter that changes the order must not repaint the bars.
COLLEGE_COLOR = {
    "College of Education, Humanities and Social Sciences": BRIGHT,
    "College of Engineering": GREEN,
    "College of Pharmacy": RED,
    "College of Business": DEEP,
    "College of Law": "#6B8CAE",
    "College of Communication and Media": "#1F8A57",
    "College of Dentistry": "#C98B5E",
    "College of Nursing": "#8FB89E",
}


def _mpl():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        "font.family": ["Archivo", "Helvetica Neue", "Helvetica", "DejaVu Sans"],
        "axes.edgecolor": HAIR,
        "axes.labelcolor": META,
        "text.color": INK,
        "xtick.color": META,
        "ytick.color": META,
        "axes.titlesize": 13,
        "axes.titleweight": "bold",
        "figure.dpi": 160,
        "savefig.bbox": "tight",
        "savefig.facecolor": "white",
    })
    return plt


def _frame(ax, title, note=""):
    ax.set_title(title, loc="left", pad=14, color=INK)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.spines["left"].set_color(HAIR)
    ax.spines["bottom"].set_color(HAIR)
    ax.tick_params(length=0)
    if note:
        ax.annotate(note, (0, -0.16), xycoords="axes fraction",
                    fontsize=8.5, color=META, va="top")


def _short(name):
    return (name.replace("College of ", "")
                .replace("Education, Humanities and Social Sciences",
                         "Education & Humanities"))


def charts(vm, outdir):
    """Write the chart pack as PNGs. -> [paths]"""
    plt = _mpl()
    os.makedirs(outdir, exist_ok=True)
    made = []

    cols = [c for c in vm["colleges"] if c.get("papers")]
    cols.sort(key=lambda c: c["papers"])

    # 1 -- papers by college. Horizontal because the labels are long; values
    # labelled at the bar end so no one has to read a gridline.
    if cols:
        fig, ax = plt.subplots(figsize=(8.4, 4.6))
        names = [_short(c["name"]) for c in cols]
        vals = [c["papers"] for c in cols]
        colors = [COLLEGE_COLOR.get(c["name"], GREEN) for c in cols]
        bars = ax.barh(names, vals, color=colors, height=.62)
        for b, v in zip(bars, vals):
            ax.annotate("%s" % f"{v:,}", (b.get_width(), b.get_y() + b.get_height() / 2),
                        xytext=(6, 0), textcoords="offset points",
                        va="center", fontsize=10, fontweight="bold", color=INK)
        ax.set_xlim(0, max(vals) * 1.14)
        ax.get_xaxis().set_visible(False)
        _frame(ax, "Papers by college",
               "A paper written across two colleges is credited to both, so "
               "these add up to more than the paper count.")
        p = os.path.join(outdir, "01_papers_by_college.png")
        fig.savefig(p); plt.close(fig); made.append(p)

    # 2 -- people by college, faculty vs everyone else. Two series, stacked,
    # with a 2px white gap so the segments read as separate.
    if cols:
        fig, ax = plt.subplots(figsize=(8.4, 4.6))
        cc = sorted(vm["colleges"], key=lambda c: c.get("people") or 0)
        names = [_short(c["name"]) for c in cc]
        fac = [c.get("people") or 0 for c in cc]
        ax.barh(names, fac, color=GREEN, height=.62, label="On the roster")
        for y, v in enumerate(fac):
            if v:
                ax.annotate(str(v), (v, y), xytext=(6, 0),
                            textcoords="offset points", va="center",
                            fontsize=10, fontweight="bold", color=INK)
        ax.set_xlim(0, max(fac + [1]) * 1.14)
        ax.get_xaxis().set_visible(False)
        _frame(ax, "Faculty on the roster, by college")
        p = os.path.join(outdir, "02_faculty_by_college.png")
        fig.savefig(p); plt.close(fig); made.append(p)

    # 3 -- who the authors are. One bar, split, because the point is the
    # proportion and not the two numbers side by side.
    s = vm["stats"]
    fac, other = s.get("faculty", 0), s.get("authors", 0) - s.get("faculty", 0)
    if fac or other:
        fig, ax = plt.subplots(figsize=(8.4, 1.9))
        ax.barh([""], [fac], color=GREEN, height=.5)
        ax.barh([""], [other], left=[fac + max(1, (fac + other) // 300)],
                color="#C3D6CA", height=.5)
        ax.annotate("%s on the roster" % f"{fac:,}", (fac / 2, 0),
                    ha="center", va="center", color="white",
                    fontsize=11, fontweight="bold")
        ax.annotate("%s students or outside faculty" % f"{other:,}",
                    (fac + other / 2, 0), ha="center", va="center",
                    color=INK, fontsize=11, fontweight="bold")
        ax.set_xlim(0, fac + other)
        ax.axis("off")
        _frame(ax, "Every author on an AAU paper")
        p = os.path.join(outdir, "03_authors_split.png")
        fig.savefig(p); plt.close(fig); made.append(p)

    # 4 -- the most published people on the roster, by AAU papers in the window
    top = [a for a in vm["authors"] if a.get("tag") == "Faculty"]
    top.sort(key=lambda a: -(a.get("papers") or 0))
    top = [a for a in top[:15] if a.get("papers")][::-1]
    if top:
        fig, ax = plt.subplots(figsize=(8.4, 5.4))
        names = [a["name"] for a in top]
        vals = [a["papers"] for a in top]
        bars = ax.barh(names, vals, color=GREEN, height=.62)
        for b, v in zip(bars, vals):
            ax.annotate(str(v), (b.get_width(), b.get_y() + b.get_height() / 2),
                        xytext=(6, 0), textcoords="offset points", va="center",
                        fontsize=10, fontweight="bold", color=INK)
        ax.set_xlim(0, max(vals) * 1.12)
        ax.get_xaxis().set_visible(False)
        ax.tick_params(axis="y", labelsize=9.5)
        _frame(ax, "Most published on the roster",
               "AAU papers in the current window.")
        p = os.path.join(outdir, "04_top_authors.png")
        fig.savefig(p); plt.close(fig); made.append(p)

    # 5 -- h-index against AAU output. Career standing versus what landed in
    # this window; they are different questions and the scatter shows it.
    pts = [(a.get("papers") or 0, a.get("h") or 0, a["name"])
           for a in vm["authors"] if a.get("tag") == "Faculty"
           and (a.get("h") or 0) > 0]
    if len(pts) > 4:
        fig, ax = plt.subplots(figsize=(8.4, 5.0))
        ax.scatter([p[0] for p in pts], [p[1] for p in pts],
                   s=42, color=GREEN, alpha=.72, edgecolor="white", linewidth=.8)
        for x, y, n in sorted(pts, key=lambda t: -(t[0] + t[1]))[:6]:
            ax.annotate(n, (x, y), xytext=(7, 4), textcoords="offset points",
                        fontsize=8.5, color=META)
        ax.set_xlabel("AAU papers in the window", fontsize=9.5)
        ax.set_ylabel("h-index (whole career)", fontsize=9.5)
        ax.grid(axis="y", color=HAIR, linewidth=.8)
        ax.set_axisbelow(True)
        _frame(ax, "Career standing against output in this window")
        p = os.path.join(outdir, "05_h_index_vs_output.png")
        fig.savefig(p); plt.close(fig); made.append(p)

    return made


def chart_zip(vm, path):
    """The chart pack as one .zip the browser can download."""
    import tempfile
    tmp = tempfile.mkdtemp(prefix="aau-charts-")
    made = charts(vm, tmp)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for p in made:
            z.write(p, os.path.basename(p))
    return path, made


def deck(vm, path, generated=""):
    """The slide deck: one title slide, then a slide per chart."""
    from pptx import Presentation
    from pptx.util import Inches, Pt
    from pptx.dml.color import RGBColor
    import tempfile

    tmp = tempfile.mkdtemp(prefix="aau-deck-")
    made = charts(vm, tmp)
    s = vm["stats"]

    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)

    def rgb(h):
        return RGBColor(int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16))

    # title
    sl = prs.slides.add_slide(prs.slide_layouts[6])
    bg = sl.shapes.add_shape(1, 0, 0, prs.slide_width, prs.slide_height)
    bg.fill.solid(); bg.fill.fore_color.rgb = rgb(GREEN); bg.line.fill.background()
    tb = sl.shapes.add_textbox(Inches(.9), Inches(2.4), Inches(11.5), Inches(2.6))
    tf = tb.text_frame; tf.word_wrap = True
    p = tf.paragraphs[0]; p.text = "Al Ain University research output"
    p.runs[0].font.size = Pt(44); p.runs[0].font.bold = True
    p.runs[0].font.color.rgb = rgb("#FFFFFF")
    p2 = tf.add_paragraph()
    p2.text = ("%s papers · %s authors · %s on the faculty roster"
               % (f"{s.get('papers', 0):,}", f"{s.get('authors', 0):,}",
                  f"{s.get('faculty', 0):,}"))
    p2.runs[0].font.size = Pt(20); p2.runs[0].font.color.rgb = rgb("#D5E8DC")
    p3 = tf.add_paragraph()
    p3.text = ("Nothing is counted unless the paper itself prints an AAU "
               "address. Generated %s." % (generated or "from the latest run"))
    p3.runs[0].font.size = Pt(13); p3.runs[0].font.color.rgb = rgb("#B9D9C6")

    for img in made:
        sl = prs.slides.add_slide(prs.slide_layouts[6])
        sl.shapes.add_picture(img, Inches(.7), Inches(.7), width=Inches(11.9))

    os.makedirs(os.path.dirname(path), exist_ok=True)
    prs.save(path)
    return path
