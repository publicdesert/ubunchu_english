#!/usr/bin/env python3
# This script is used to build the manga both in full and reading aid/public variants
# Run with --help to see all options
import os, io, sys, argparse, tempfile, subprocess, shutil, zipfile, re
import cairo
from PIL import Image, ImageOps
import xml.etree.ElementTree as ET

# Default dirs (can be swapped to *_p by --mode public)
COVER_DIR  = "./cover"
EXTRACT_DIR = "./extract"
MASK_DIR    = "./mask"
TEXT_DIR    = "./text"

try:
    RESAMPLE = Image.Resampling.LANCZOS  # Pillow >= 9.1
except AttributeError:
    RESAMPLE = Image.LANCZOS if hasattr(Image, "LANCZOS") else Image.BICUBIC

EXTRACT_EXTS = (".png", ".jpg", ".jpeg")

# -------------------- helpers: CLI dependencies --------------------

def require_tool(name: str) -> str:
    p = shutil.which(name)
    if not p:
        raise FileNotFoundError(f"Required tool '{name}' not found in PATH")
    return p

def have_tool(name: str) -> bool:
    return shutil.which(name) is not None

# -------------------- cover discovery & sizing --------------------

def find_cover_paths() -> tuple[str|None, str|None]:
    """Return (png_path, pdf_path); png has priority."""
    png = os.path.join(COVER_DIR, "0.png")
    pdf = os.path.join(COVER_DIR, "0.pdf")
    return (png if os.path.exists(png) else None,
            pdf if os.path.exists(pdf) else None)

def get_pdf_page_size_pts(pdf_path: str) -> tuple[float, float]:
    """Use 'pdfinfo' to read first page size in points (72 dpi)."""
    if not have_tool("pdfinfo"):
        raise FileNotFoundError("pdfinfo not found; install poppler-utils")
    cp = subprocess.run(
        ["pdfinfo", pdf_path],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    if cp.returncode != 0:
        raise RuntimeError(f"pdfinfo failed: {cp.stderr}")
    # Look for "Page size: 612 x 792 pts"
    m = re.search(r"Page size:\s*([\d.]+)\s*x\s*([\d.]+)\s*pts", cp.stdout)
    if not m:
        # Some locales may report units differently; try millimeters -> convert
        m_mm = re.search(r"Page size:\s*([\d.]+)\s*x\s*([\d.]+)\s*mm", cp.stdout)
        if m_mm:
            w_mm = float(m_mm.group(1)); h_mm = float(m_mm.group(2))
            w = w_mm * 72.0 / 25.4
            h = h_mm * 72.0 / 25.4
            return (w, h)
        raise RuntimeError("Could not parse page size from pdfinfo output")
    return (float(m.group(1)), float(m.group(2)))

def get_svg_size_px(svg_path: str) -> tuple[int, int]:
    """Infer SVG intrinsic size in pixels at 96 DPI using width/height or viewBox."""
    # 1 px = 1 CSS px; 1 in = 96 px; 1 mm = 96/25.4 px
    def parse_len(v: str) -> float:
        v = v.strip()
        m = re.match(r"^([\d.]+)\s*([a-z%]*)$", v)
        if not m:
            return float(v)
        val = float(m.group(1))
        unit = m.group(2).lower()
        if unit in ("", "px"): return val
        if unit == "in": return val * 96.0
        if unit == "mm": return val * 96.0 / 25.4
        if unit == "cm": return val * 96.0 / 2.54
        if unit == "pt": return val * (96.0/72.0)
        if unit == "pc": return val * (96.0/6.0)
        return val

    try:
        root = ET.parse(svg_path).getroot()
    except Exception:
        return (1600, 2400)

    w_attr = root.get("width")
    h_attr = root.get("height")
    if w_attr and h_attr:
        try:
            w = int(round(parse_len(w_attr)))
            h = int(round(parse_len(h_attr)))
            if w > 0 and h > 0:
                return (w, h)
        except Exception:
            pass

    vb = root.get("viewBox")
    if vb:
        parts = [p for p in re.split(r"[,\s]+", vb.strip()) if p]
        if len(parts) == 4:
            try:
                w = int(round(float(parts[2])))
                h = int(round(float(parts[3])))
                if w > 0 and h > 0:
                    return (w, h)
            except Exception:
                pass

    return (1600, 2400)

# -------------------- image/pdf rendering utils --------------------

def inkscape_svg_to_png_bytes(svg_path: str, out_w: int, out_h: int) -> bytes:
    inkscape = require_tool("inkscape")
    with tempfile.TemporaryDirectory() as td:
        out_png = os.path.join(td, "o.png")
        cmd = [
            inkscape,
            "--export-type=png",
            f"--export-filename={out_png}",
            f"--export-width={out_w}",
            f"--export-height={out_h}",
            "--export-background-opacity=0",
            "--export-text-to-path",
            svg_path,
        ]
        cp = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if cp.returncode != 0 or not os.path.exists(out_png):
            raise RuntimeError(
                f"Inkscape failed (code {cp.returncode}): {cp.stderr.decode('utf-8', 'ignore')}"
            )
        with open(out_png, "rb") as f:
            return f.read()
            
def render_text_png_pil_public_black_no_stroke(i: int, w: int, h: int) -> Image.Image | None:
    """Public-mode text render: kill strokes, force text fill to black in order to assure readability on white bg"""
    text_svg_path = os.path.join(TEXT_DIR, f"{i}.svg")
    if not os.path.exists(text_svg_path):
        return None

    css = """*{stroke:none !important}
text, tspan { fill:#000 !important; fill-opacity:1 !important }"""

    # Inject a <style> into a temp copy and export that
    with tempfile.TemporaryDirectory() as td:
        patched = os.path.join(td, "patched.svg")

        try:
            tree = ET.parse(text_svg_path)
            root = tree.getroot()
            m = re.match(r'^\{([^}]+)\}', root.tag)
            svg_ns = m.group(1) if m else "http://www.w3.org/2000/svg"
            style_el = ET.Element(f"{{{svg_ns}}}style", attrib={"type": "text/css"})
            style_el.text = css
            # put style first to win specificity battles with later <style> blocks
            root.insert(0, style_el)
            tree.write(patched, encoding="utf-8", xml_declaration=True)
        except Exception:
            # As a fallback, do a simple text injection after the opening <svg ...>
            with open(text_svg_path, "r", encoding="utf-8") as f:
                src = f.read()
            patched_src = re.sub(
                r"(<svg[^>]*>)",
                r'\1<style type="text/css">' + css + r"</style>",
                src,
                count=1,
                flags=re.IGNORECASE | re.DOTALL,
            )
            with open(patched, "w", encoding="utf-8") as f:
                f.write(patched_src)

        png_bytes = inkscape_svg_to_png_bytes(patched, w, h)
        return Image.open(io.BytesIO(png_bytes)).convert("RGBA")

def pil_to_cairo_surface(im: Image.Image) -> cairo.ImageSurface:
    if im.mode != "RGBA":
        im = im.convert("RGBA")
    bio = io.BytesIO()
    im.save(bio, format="PNG")
    bio.seek(0)
    return cairo.ImageSurface.create_from_png(bio)

def draw_fullpage(ctx: cairo.Context, surf: cairo.ImageSurface, page_w: float, page_h: float) -> None:
    iw, ih = surf.get_width(), surf.get_height()
    ctx.save()
    ctx.scale(page_w / iw, page_h / ih)
    ctx.set_source_surface(surf, 0, 0)
    ctx.paint()
    ctx.restore()

def ensure_size(im: Image.Image, target_w: int, target_h: int) -> Image.Image:
    if im.size == (target_w, target_h):
        return im
    return im.resize((target_w, target_h), RESAMPLE)

# -------------------- base & text page collection --------------------

def resolve_extract_path(index: int) -> str | None:
    base = os.path.join(EXTRACT_DIR, str(index))
    for ext in EXTRACT_EXTS:
        p = base + ext
        if os.path.exists(p):
            return p
    return None

def collect_base_pages():
    pages = []
    i = 1
    while True:
        if resolve_extract_path(i) is not None:
            pages.append(i)
            i += 1
        else:
            break
    return pages

def collect_text_pages():
    pages = []
    i = 1
    while True:
        if os.path.exists(os.path.join(TEXT_DIR, f"{i}.svg")):
            pages.append(i)
            i += 1
        else:
            break
    return pages

def load_base_with_mask(i: int) -> Image.Image:
    base_path = resolve_extract_path(i)
    if base_path is None:
        raise FileNotFoundError(os.path.join(EXTRACT_DIR, f"{i}.png/.jpg/.jpeg"))
    base = Image.open(base_path)
    try:
        base = ImageOps.exif_transpose(base)
    except Exception:
        pass
    base = base.convert("RGBA")
    mask_path = os.path.join(MASK_DIR, f"{i}.png")
    if os.path.exists(mask_path):
        mask = Image.open(mask_path).convert("RGBA")
        if mask.size != base.size:
            raise ValueError(f"Size mismatch on page {i}: base {base.size} vs mask {mask.size}")
        base.alpha_composite(mask)
    return base

def render_text_png_pil(i: int, w: int, h: int) -> Image.Image | None:
    text_svg_path = os.path.join(TEXT_DIR, f"{i}.svg")
    if not os.path.exists(text_svg_path):
        return None
    png_bytes = inkscape_svg_to_png_bytes(text_svg_path, w, h)
    return Image.open(io.BytesIO(png_bytes)).convert("RGBA")

# -------------------- cover rasterization & PDF merge --------------------

def rasterize_pdf_first_page_to_png(pdf_path: str, out_w: int, out_h: int) -> Image.Image:
    """Rasterize first page to PNG of exact pixel size (requires pdftoppm or gs)."""
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "cover")
        if have_tool("pdftoppm"):
            cmd = [
                "pdftoppm", "-f", "1", "-l", "1", "-png",
                "-scale-to-x", str(out_w), "-scale-to-y", str(out_h),
                pdf_path, out
            ]
            cp = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if cp.returncode != 0:
                raise RuntimeError(f"pdftoppm failed: {cp.stderr.decode('utf-8','ignore')}")
            png_path = out + "-1.png"
        elif have_tool("gs"):
            # -g sets pixel size; use pngalpha for transparency if any
            png_path = os.path.join(td, "cover.png")
            cmd = [
                "gs", "-dSAFER", "-dBATCH", "-dNOPAUSE",
                "-sDEVICE=pngalpha",
                f"-g{out_w}x{out_h}",
                "-dFirstPage=1", "-dLastPage=1",
                "-sOutputFile=" + png_path,
                pdf_path
            ]
            cp = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if cp.returncode != 0:
                raise RuntimeError(f"ghostscript failed: {cp.stderr.decode('utf-8','ignore')}")
        else:
            raise FileNotFoundError("Need 'pdftoppm' (poppler-utils) or 'gs' (ghostscript) to rasterize PDF cover for CBZ")
        im = Image.open(png_path).convert("RGBA")
        return ensure_size(im, out_w, out_h)

def merge_pdfs_preserve_links(cover_pdf: str, body_pdf: str, out_pdf: str) -> None:
    """Prepend cover_pdf to body_pdf preserving annotations; prefer qpdf, fallback pdftk."""
    if have_tool("qpdf"):
        cmd = ["qpdf", "--empty", "--pages", cover_pdf, body_pdf, "--", out_pdf]
        cp = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if cp.returncode != 0:
            raise RuntimeError(f"qpdf failed: {cp.stderr.decode('utf-8','ignore')}")
        return
    if have_tool("pdftk"):
        cmd = ["pdftk", cover_pdf, body_pdf, "cat", "output", out_pdf]
        cp = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if cp.returncode != 0:
            raise RuntimeError(f"pdftk failed: {cp.stderr.decode('utf-8','ignore')}")
        return
    raise FileNotFoundError("To preserve hyperlinks on a PDF cover, install 'qpdf' or 'pdftk'")

# -------------------- size selection per mode --------------------

def choose_target_size(mode: str, cover_png: str|None, cover_pdf: str|None) -> tuple[int|float, int|float, str]:
    """
    Returns (w, h, source) where source indicates where the size came from:
    'cover_png', 'cover_pdf', 'base', or 'text'.
    """
    if mode == "full":
        if cover_pdf:
            w, h = get_pdf_page_size_pts(cover_pdf)
            return (w, h, "cover_pdf")
        # fall back to base page size
        pages = collect_base_pages()
        if not pages:
            raise SystemExit("No pages created. Did you place PNGs in ./extract?")
        first_base = load_base_with_mask(pages[0])
        w, h = first_base.size
        return (w, h, "base")
    else:  # public
        if cover_png:
            im = Image.open(cover_png)
            return (*im.size, "cover_png")
        if cover_pdf:
            w, h = get_pdf_page_size_pts(cover_pdf)
            return (w, h, "cover_pdf")
        # fall back to SVG intrinsic size
        pages = collect_text_pages()
        if not pages:
            raise SystemExit("No pages created. Did you place SVGs in ./text_p?")
        w, h = get_svg_size_px(os.path.join(TEXT_DIR, f"{pages[0]}.svg"))
        return (w, h, "text")

# -------------------- builders --------------------

def build_pdf(out_path: str, mode: str, verbose: bool = True) -> None:
    cover_png, cover_pdf = find_cover_paths()
    w, h, size_src = choose_target_size(mode, cover_png, cover_pdf)

    # Create the body PDF (no PDF-cover included; PNG-cover is embedded directly)
    with tempfile.TemporaryDirectory() as td:
        body_path = os.path.join(td, "body.pdf")
        pdf_surface = cairo.PDFSurface(body_path, w, h)
        ctx = cairo.Context(pdf_surface)

        # Optional PNG cover goes first (resized to page size)
        if cover_png and not cover_pdf:
            im = Image.open(cover_png).convert("RGBA")
            im = ensure_size(im, int(round(w)), int(round(h)))
            draw_fullpage(ctx, pil_to_cairo_surface(im), w, h)
            pdf_surface.show_page()
            if verbose:
                print(f"[OK] PDF cover 0 ({int(round(w))}x{int(round(h))}) [png]", file=sys.stderr)

        if mode == "full":
            pages = collect_base_pages()
            if not pages:
                raise SystemExit("No pages created. Did you place PNGs in ./extract?")
            # draw each page: base+mask, then (optional) text overlay from TEXT_DIR
            for i in pages:
                ctx = cairo.Context(pdf_surface)
                base = load_base_with_mask(i)
                if base.size != (int(round(w)), int(round(h))):
                    base = ensure_size(base, int(round(w)), int(round(h)))
                draw_fullpage(ctx, pil_to_cairo_surface(base), w, h)
                # overlay text if exists (from TEXT_DIR)
                trgba = render_text_png_pil(i, int(round(w)), int(round(h)))
                if trgba is not None:
                    draw_fullpage(ctx, pil_to_cairo_surface(trgba), w, h)
                pdf_surface.show_page()
                if verbose:
                    print(f"[OK] PDF page {i} ({int(round(w))}x{int(round(h))})", file=sys.stderr)
        else:  # public: only text pages from TEXT_DIR (which is ./text_p)
            pages = collect_text_pages()
            if not pages:
                raise SystemExit("No pages created. Did you place SVGs in ./text_p?")
            for i in pages:
                ctx = cairo.Context(pdf_surface)
                trgba = render_text_png_pil_public_black_no_stroke(i, int(round(w)), int(round(h)))
                if trgba is None:
                    raise FileNotFoundError(os.path.join(TEXT_DIR, f"{i}.svg"))
                draw_fullpage(ctx, pil_to_cairo_surface(trgba), w, h)
                pdf_surface.show_page()
                if verbose:
                    print(f"[OK] PDF text page {i} ({int(round(w))}x{int(round(h))})", file=sys.stderr)

        pdf_surface.finish()

        # If cover is a PDF, prepend it preserving links by merging PDFs
        if cover_pdf:
            # Build final by merging: cover.pdf + body.pdf
            merge_pdfs_preserve_links(cover_pdf, body_path, out_path)
            if verbose:
                src_note = "cover size governs" if size_src == "cover_pdf" else "merged"
                print(f"[DONE] Wrote PDF (cover pdf merged, links preserved): {out_path}", file=sys.stderr)
        else:
            # PNG cover (if any) already embedded at start of body_path; move to out_path
            shutil.move(body_path, out_path)
            if verbose:
                print(f"[DONE] Wrote PDF: {out_path}", file=sys.stderr)

def build_cbz(out_path: str, mode: str, verbose: bool = True) -> None:
    cover_png, cover_pdf = find_cover_paths()

    # Decide target canvas size
    if mode == "full":
        pages = collect_base_pages()
        if not pages:
            raise SystemExit("No pages created. Did you place PNGs in ./extract?")
        first_base = load_base_with_mask(pages[0])
        w, h = first_base.size
    else:
        # public: prefer cover, else text SVG size
        if cover_png:
            im = Image.open(cover_png)
            w, h = im.size
        else:
            tpages = collect_text_pages()
            if not tpages and not cover_pdf:
                raise SystemExit("No pages created. Did you place SVGs in ./text_p?")
            if tpages:
                w, h = get_svg_size_px(os.path.join(TEXT_DIR, f"{tpages[0]}.svg"))
            else:
                # no text yet, derive from PDF cover in points; choose 96 DPI mapping
                w_pts, h_pts = get_pdf_page_size_pts(cover_pdf)
                # map points to pixels at 96 dpi (1 pt = 1/72 in => 96/72 px per pt = 1.3333)
                w = int(round(w_pts * 96.0 / 72.0))
                h = int(round(h_pts * 96.0 / 72.0))

    # Compute total pages to set padding (include cover if any)
    if mode == "full":
        tpages = []
        bpages = collect_base_pages()
    else:
        bpages = []
        tpages = collect_text_pages()

    has_cover = bool(cover_png or cover_pdf)
    total_pages = (len(bpages) if mode == "full" else len(tpages)) + (1 if has_cover else 0)
    pad = max(3, len(str(total_pages)))

    with tempfile.TemporaryDirectory() as td:
        written = []
        n = 1

        # Cover first
        if cover_png:
            cim = Image.open(cover_png).convert("RGBA")
            cim = ensure_size(cim, w, h)
            fname = f"{n:0{pad}d}.png"; fpath = os.path.join(td, fname)
            cim.save(fpath, format="PNG", optimize=False)
            written.append((fname, fpath))
            if verbose:
                print(f"[OK] CBZ cover {n} ({w}x{h}) [png] -> {fname}", file=sys.stderr)
            n += 1
        elif cover_pdf:
            cim = rasterize_pdf_first_page_to_png(cover_pdf, w, h)
            fname = f"{n:0{pad}d}.png"; fpath = os.path.join(td, fname)
            cim.save(fpath, format="PNG", optimize=False)
            written.append((fname, fpath))
            if verbose:
                print(f"[OK] CBZ cover {n} ({w}x{h}) [pdf→png] -> {fname}", file=sys.stderr)
            n += 1

        if mode == "full":
            # base+mask flattened; then optional text overlay from TEXT_DIR
            for i in bpages:
                im = load_base_with_mask(i)
                if im.size != (w, h):
                    im = ensure_size(im, w, h)
                trgba = render_text_png_pil(i, w, h)
                if trgba is not None:
                    im.alpha_composite(trgba)
                fname = f"{n:0{pad}d}.png"; fpath = os.path.join(td, fname)
                im.save(fpath, format="PNG", optimize=False)
                written.append((fname, fpath))
                if verbose:
                    print(f"[OK] CBZ page {n} ({w}x{h}) -> {fname}", file=sys.stderr)
                n += 1
        else:
            # public: only text pages
            for i in tpages:
                trgba = render_text_png_pil(i, w, h)
                if trgba is None:
                    raise FileNotFoundError(os.path.join(TEXT_DIR, f"{i}.svg"))
                fname = f"{n:0{pad}d}.png"; fpath = os.path.join(td, fname)
                trgba.save(fpath, format="PNG", optimize=False)
                written.append((fname, fpath))
                if verbose:
                    print(f"[OK] CBZ text {n} ({w}x{h}) -> {fname}", file=sys.stderr)
                n += 1

        with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
            for fname, fpath in written:
                zf.write(fpath, arcname=fname)

    if verbose:
        print(f"[DONE] Wrote CBZ: {out_path}", file=sys.stderr)

# -------------------- main --------------------

def main():
    global COVER_DIR, TEXT_DIR
    ap = argparse.ArgumentParser(
        description="This script is used to build the manga both in full and reading aid/public variants."
                    "Modes: 'full' (base+mask+text) or 'public' (custom cover + text only)."
    )
    ap.add_argument("-o", "--output", default="output.pdf",
                    help="Output path (default: output.pdf for PDF)")
    ap.add_argument("-f", "--format", choices=["pdf", "cbz"], default="pdf",
                    help="Output format: pdf (default) or cbz")
    ap.add_argument("-m", "--mode", choices=["full", "public"], default="full",
                    help="Build mode: full (default) or public (cover + text only, using *_p dirs)")
    ap.add_argument("-q", "--quiet", action="store_true", help="Quiet mode")
    args = ap.parse_args()

    # Switch dirs for public mode
    if args.mode == "public":
        COVER_DIR = "./cover_p"
        TEXT_DIR  = "./text_p"

    # Adjust default output filename for CBZ
    if args.format == "cbz" and args.output == "output.pdf":
        args.output = "output.cbz"

    if args.format == "cbz":
        build_cbz(out_path=args.output, mode=args.mode, verbose=not args.quiet)
    else:
        build_pdf(out_path=args.output, mode=args.mode, verbose=not args.quiet)

if __name__ == "__main__":
    main()

