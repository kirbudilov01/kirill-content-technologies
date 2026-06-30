from __future__ import annotations

import subprocess
from pathlib import Path

from content_distribution.config import Settings
from content_distribution.services.reframing import estimate_focus_x_ratio
from content_distribution.utils.media import MediaError, get_video_dimensions
from content_distribution.utils.srt import SrtItem, parse_srt, slice_srt, srt_to_ass, write_srt


# --------------------------------------------------------------------------- #
#  Geometry helpers                                                             #
# --------------------------------------------------------------------------- #

def _compute_crop(
    src_w: int, src_h: int,
    target_w: int, target_h: int,
    focus_x: float,
) -> tuple[int, int, int, int]:
    target_ratio = target_w / target_h
    src_ratio = src_w / src_h
    if src_ratio >= target_ratio:
        crop_h = src_h
        crop_w = int(src_h * target_ratio)
    else:
        crop_w = src_w
        crop_h = int(src_w / target_ratio)
    crop_w -= crop_w % 2
    crop_h -= crop_h % 2
    x_offset = max(0, min(int((src_w - crop_w) * focus_x), src_w - crop_w))
    y_offset = max(0, min(int((src_h - crop_h) * 0.5), src_h - crop_h))
    return crop_w, crop_h, x_offset, y_offset


# --------------------------------------------------------------------------- #
#  Subtitle burn-in via OpenCV (no libass / libfreetype needed)                #
# --------------------------------------------------------------------------- #

def _wrap_subtitle_text(
    text: str,
    font,
    scale: float,
    thickness: int,
    max_width: int,
    max_lines: int,
    max_words_per_line: int,
) -> list[str]:
    import cv2

    words = text.replace("\n", " ").split()
    if not words:
        return []

    chunks: list[str] = []
    for index in range(0, len(words), max_words_per_line):
        chunks.append(" ".join(words[index:index + max_words_per_line]))

    lines: list[str] = []
    for chunk in chunks:
        candidate_width = cv2.getTextSize(chunk, font, scale, thickness)[0][0]
        if candidate_width <= max_width:
            lines.append(chunk)
            continue

        # Fallback for very long tokens: split by measured width.
        token_words = chunk.split()
        current = ""
        for token in token_words:
            candidate = f"{current} {token}".strip()
            token_width = cv2.getTextSize(candidate, font, scale, thickness)[0][0]
            if current and token_width > max_width:
                lines.append(current)
                current = token
            else:
                current = candidate
        if current:
            lines.append(current)

    return lines[:max_lines]


def _paged_subtitle_lines(
    text: str,
    t: float,
    start: float,
    end: float,
    max_lines: int,
    max_words_per_line: int,
) -> list[str]:
    words = text.replace("\n", " ").split()
    if not words:
        return []

    chunks = [
        " ".join(words[index:index + max_words_per_line])
        for index in range(0, len(words), max_words_per_line)
    ]
    if len(chunks) <= max_lines:
        return chunks

    pages = [chunks[index:index + max_lines] for index in range(0, len(chunks), max_lines)]
    duration = max(0.05, end - start)
    progress = min(0.999, max(0.0, (t - start) / duration))
    page_index = int(progress * len(pages))
    return pages[page_index]


def _ease_out_cubic(value: float) -> float:
    value = min(1.0, max(0.0, value))
    return 1.0 - (1.0 - value) ** 3


def _draw_rounded_rect(image, x1: int, y1: int, x2: int, y2: int, radius: int, color) -> None:
    import cv2

    radius = max(2, min(radius, (x2 - x1) // 2, (y2 - y1) // 2))
    cv2.rectangle(image, (x1 + radius, y1), (x2 - radius, y2), color, -1)
    cv2.rectangle(image, (x1, y1 + radius), (x2, y2 - radius), color, -1)
    cv2.circle(image, (x1 + radius, y1 + radius), radius, color, -1)
    cv2.circle(image, (x2 - radius, y1 + radius), radius, color, -1)
    cv2.circle(image, (x1 + radius, y2 - radius), radius, color, -1)
    cv2.circle(image, (x2 - radius, y2 - radius), radius, color, -1)


def _blend_icon(frame, icon, x: int, y: int, size: int) -> None:
    import cv2
    import numpy as np

    if icon is None:
        return

    h, w = frame.shape[:2]
    if x < 0 or y < 0 or x + size > w or y + size > h:
        return

    icon_resized = cv2.resize(icon, (size, size), interpolation=cv2.INTER_AREA)
    roi = frame[y:y + size, x:x + size]
    if icon_resized.shape[2] == 4:
        alpha = icon_resized[:, :, 3:4].astype(np.float32) / 255.0
        fg = icon_resized[:, :, :3].astype(np.float32)
        bg = roi.astype(np.float32)
        blended = fg * alpha + bg * (1.0 - alpha)
        frame[y:y + size, x:x + size] = blended.astype("uint8")
        return

    frame[y:y + size, x:x + size] = icon_resized[:, :, :3]


def _wrap_banner_text(text: str, font, scale: float, thickness: int, max_width: int) -> list[str]:
    import cv2

    words = text.split()
    if not words:
        return []

    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        candidate_width = cv2.getTextSize(candidate, font, scale, thickness)[0][0]
        if current and candidate_width > max_width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines[:2]


_BOLD_FONT_PATH = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
_REG_FONT_PATH = "/System/Library/Fonts/Supplemental/Arial.ttf"


def _blend_static_overlay(frame, overlay_img, settings, opacity: float = 0.82) -> None:
    """Blend a pre-loaded image onto the frame with soft edges and semi-transparency."""
    import cv2
    import numpy as np

    h, w = frame.shape[:2]
    margin_x = max(28, int(w * 0.04))
    target_w = w - 2 * margin_x
    target_h = settings.render.promo_height
    y1 = settings.render.promo_top_margin
    y2 = y1 + target_h
    x1 = margin_x

    # Maintain aspect ratio — scale by width only
    ow, oh = overlay_img.shape[1], overlay_img.shape[0]
    natural_h = int(oh * target_w / ow)
    ov = cv2.resize(overlay_img, (target_w, natural_h), interpolation=cv2.INTER_AREA)
    # Use natural height instead of fixed target_h
    clip_h_limit = natural_h
    y2 = y1 + natural_h

    clip_y2 = min(h, y2)
    clip_h = clip_y2 - max(0, y1)
    if clip_h <= 0:
        return

    ov_crop = ov[:clip_h]


    # Base alpha from image (or full opaque if no alpha channel)
    if ov_crop.shape[2] == 4:
        base_alpha = ov_crop[:, :, 3:4].astype(np.float32) / 255.0
    else:
        base_alpha = np.ones((clip_h, target_w, 1), dtype=np.float32)

    # Horizontal edge feather — fade in/out over ~60px on each side
    feather_px = min(60, target_w // 6)
    edge_mask = np.ones(target_w, dtype=np.float32)
    ramp = np.linspace(0.0, 1.0, feather_px)
    edge_mask[:feather_px] = ramp
    edge_mask[-feather_px:] = ramp[::-1]
    # Vertical edge feather — fade out over bottom ~40px
    v_mask = np.ones(clip_h, dtype=np.float32)
    vfade = min(40, clip_h // 4)
    v_mask[-vfade:] = np.linspace(1.0, 0.0, vfade)

    edge_mask_2d = (edge_mask[np.newaxis, :, np.newaxis] *
                    v_mask[:, np.newaxis, np.newaxis])

    alpha = base_alpha * edge_mask_2d * opacity

    fg = ov_crop[:, :, :3].astype(np.float32)
    roi = frame[y1:clip_y2, x1:x1 + target_w].astype(np.float32)
    frame[y1:clip_y2, x1:x1 + target_w] = (fg * alpha + roi * (1.0 - alpha)).astype(np.uint8)


def _pil_font(path: str, size: int):
    from PIL import ImageFont
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


def _draw_promo_banner(frame, t: float, settings: Settings, icon) -> None:
    import cv2
    import numpy as np
    from PIL import Image, ImageDraw

    if not settings.render.promo_enabled:
        return

    start = settings.render.promo_start_seconds
    duration = settings.render.promo_duration_seconds
    end = float("inf") if duration <= 0 else start + duration
    if t < start or t > end:
        return

    h, w = frame.shape[:2]
    margin_x = max(28, int(w * 0.04))
    banner_h = settings.render.promo_height
    y_target = settings.render.promo_top_margin
    x1 = margin_x
    x2 = w - margin_x
    banner_w = x2 - x1

    appear_progress = _ease_out_cubic((t - start) / max(0.05, settings.render.promo_anim_seconds))
    fade_out_start = max(start + settings.render.promo_anim_seconds, end - 0.5)
    alpha_mul = (1.0 - min(1.0, max(0.0, (t - fade_out_start) / max(0.05, end - fade_out_start)))) if t > fade_out_start else 1.0

    y_hidden = -banner_h - 24
    y1 = int(y_hidden + (y_target - y_hidden) * appear_progress)
    y2 = y1 + banner_h
    if y2 <= 0 or y1 >= h:
        return

    # ------------------------------------------------------------------ #
    #  Draw entire banner onto a Pillow RGBA canvas, then blend into frame #
    # ------------------------------------------------------------------ #
    canvas = Image.new("RGBA", (banner_w, banner_h), (0, 0, 0, 0))
    d = ImageDraw.Draw(canvas)
    radius = max(18, int(banner_h * 0.09))

    # Background: near-black with deep violet tint
    d.rounded_rectangle([0, 0, banner_w - 1, banner_h - 1], radius=radius, fill=(24, 8, 38, 245))

    # Subtle grid lines
    grid = 36
    for gx in range(0, banner_w, grid):
        d.line([(gx, 0), (gx, banner_h)], fill=(120, 50, 160, 16), width=1)
    for gy in range(0, banner_h, grid):
        d.line([(0, gy), (banner_w, gy)], fill=(120, 50, 160, 16), width=1)

    # Faint diagonal grid (like reference)
    for diag in range(-banner_h, banner_w, 48):
        d.line([(diag, 0), (diag + banner_h, banner_h)], fill=(120, 50, 160, 10), width=1)

    # Pink accent dot (top-right)
    dot_r = max(8, int(banner_h * 0.05))
    d.ellipse([banner_w - dot_r * 3, dot_r, banner_w - dot_r, dot_r * 3], fill=(220, 80, 255, 200))

    # Large faint "VPN" watermark in background
    wm_size = int(banner_h * 0.72)
    wm_font = _pil_font(_BOLD_FONT_PATH, wm_size)
    wm_bb = d.textbbox((0, 0), "VPN", font=wm_font)
    wm_x = (banner_w - (wm_bb[2] - wm_bb[0])) // 2 - wm_bb[0]
    wm_y = int(banner_h * 0.02) - wm_bb[1]
    d.text((wm_x, wm_y), "VPN", font=wm_font, fill=(90, 30, 120, 30))

    # Pink border glow
    d.rounded_rectangle([0, 0, banner_w - 1, banner_h - 1], radius=radius, outline=(180, 0, 160, 70), width=2)

    # ---- TITLE ----
    title1 = settings.render.promo_text.strip()
    title2 = settings.render.promo_title_line2.strip()
    highlight = settings.render.promo_title_highlight_word.strip()

    btn_h_px = max(56, int(banner_h * 0.30))
    btn_area_top = banner_h - btn_h_px - 16
    title_area_h = btn_area_top - 14

    # Auto-fit font size
    title_font = None
    for fsize in range(int(banner_h * 0.30), 18, -2):
        f = _pil_font(_BOLD_FONT_PATH, fsize)
        bb1 = d.textbbox((0, 0), title1 or "X", font=f)
        bb2 = d.textbbox((0, 0), title2 or "X", font=f) if title2 else bb1
        needed_h = (bb1[3] - bb1[1]) + (bb2[3] - bb2[1] + 8 if title2 else 0)
        if max(bb1[2] - bb1[0], bb2[2] - bb2[0]) <= banner_w - 32 and needed_h <= title_area_h:
            title_font = f
            break
    if title_font is None:
        title_font = _pil_font(_BOLD_FONT_PATH, 40)

    def put_text_centered(draw_obj, text, y_top, font, color, x_offset=0):
        bb = draw_obj.textbbox((0, 0), text, font=font)
        x = (banner_w - (bb[2] - bb[0])) // 2 - bb[0] + x_offset
        y = y_top - bb[1]
        draw_obj.text((x + 3, y + 3), text, font=font, fill=(20, 6, 32, 180))
        draw_obj.text((x, y), text, font=font, fill=color)
        return bb[3] - bb[1]

    y_off = 12
    if title1:
        lh = put_text_centered(d, title1, y_off, title_font, (255, 255, 255, 255))
        y_off += lh + 6

    if title2 and highlight and highlight in title2:
        parts = title2.split(highlight, 1)
        # Measure total width to center everything
        bb_full = d.textbbox((0, 0), title2, font=title_font)
        start_x = (banner_w - (bb_full[2] - bb_full[0])) // 2 - bb_full[0]
        bb_full_h = bb_full[3] - bb_full[1]
        cy = y_off - d.textbbox((0, 0), title2, font=title_font)[1]
        cx = start_x
        for seg, color in [(parts[0], (255, 255, 255, 255)), (highlight, (255, 80, 210, 255)), (parts[1], (255, 255, 255, 255))]:
            if not seg:
                continue
            bb = d.textbbox((0, 0), seg, font=title_font)
            d.text((cx - bb[0] + 3, cy + 3), seg, font=title_font, fill=(20, 6, 32, 180))
            d.text((cx - bb[0], cy), seg, font=title_font, fill=color)
            cx += bb[2] - bb[0]
        y_off += bb_full_h + 6
    elif title2:
        lh = put_text_centered(d, title2, y_off, title_font, (255, 255, 255, 255))
        y_off += lh + 6

    # ---- CTA BUTTONS ----
    if settings.render.promo_cta_enabled:
        cta_items = [s.strip() for s in (settings.render.promo_cta_primary, settings.render.promo_cta_secondary) if s.strip()]
        cta_font = _pil_font(_REG_FONT_PATH, max(22, int(btn_h_px * 0.40)))
        gap = 14
        btn_y1 = btn_area_top
        btn_y2 = btn_y1 + btn_h_px
        btn_r = btn_h_px // 2

        if len(cta_items) >= 2:
            mid = banner_w // 2
            btn_coords = [(8, mid - gap // 2), (mid + gap // 2, banner_w - 8)]
        elif len(cta_items) == 1:
            btn_coords = [(int(banner_w * 0.1), int(banner_w * 0.9))]
        else:
            btn_coords = []

        for i, ((bx1, bx2), txt) in enumerate(zip(btn_coords, cta_items)):
            bw_btn = bx2 - bx1
            # Outer glow
            d.rounded_rectangle([bx1 - 5, btn_y1 - 4, bx2 + 5, btn_y2 + 4], radius=btn_r + 5, fill=(180, 40, 210, 55))
            # Button fill (pink-magenta)
            d.rounded_rectangle([bx1, btn_y1, bx2, btn_y2], radius=btn_r, fill=(170, 28, 170))
            # Top highlight shimmer
            d.rounded_rectangle([bx1 + 4, btn_y1 + 4, bx2 - 4, btn_y1 + btn_h_px // 2], radius=btn_r - 4, fill=(210, 70, 215, 100))

            # Icon circle (white pill on left)
            icon_r_px = int(btn_h_px * 0.32)
            icon_cx = bx1 + int(bw_btn * 0.20)
            icon_cy = (btn_y1 + btn_y2) // 2
            d.ellipse([icon_cx - icon_r_px, icon_cy - icon_r_px, icon_cx + icon_r_px, icon_cy + icon_r_px], fill=(255, 255, 255, 220))

            sp = int(icon_r_px * 0.58)
            if i == 0:
                # Shield with checkmark
                pts = [(icon_cx, icon_cy - sp), (icon_cx + sp, icon_cy - int(sp * 0.45)),
                       (icon_cx + sp, icon_cy + int(sp * 0.18)), (icon_cx, icon_cy + sp),
                       (icon_cx - sp, icon_cy + int(sp * 0.18)), (icon_cx - sp, icon_cy - int(sp * 0.45))]
                d.polygon(pts, fill=(170, 28, 170))
                ck = [(icon_cx - int(sp * 0.38), icon_cy), (icon_cx - int(sp * 0.05), icon_cy + int(sp * 0.32)),
                      (icon_cx + int(sp * 0.42), icon_cy - int(sp * 0.28))]
                d.line(ck, fill=(255, 255, 255), width=max(2, int(icon_r_px * 0.18)))
            else:
                # Telegram paper-airplane
                d.polygon([(icon_cx - sp, icon_cy - sp), (icon_cx + sp, icon_cy), (icon_cx - sp, icon_cy + sp)], fill=(29, 155, 240))
                d.polygon([(icon_cx - sp, icon_cy), (icon_cx - int(sp * 0.3), icon_cy), (icon_cx - sp, icon_cy + sp)], fill=(255, 255, 255, 180))

            # Button text
            bb = d.textbbox((0, 0), txt, font=cta_font)
            tw = bb[2] - bb[0]
            th = bb[3] - bb[1]
            tx = icon_cx + icon_r_px + 8 - bb[0]
            ty = icon_cy - th // 2 - bb[1]
            d.text((tx + 1, ty + 1), txt, font=cta_font, fill=(40, 10, 60, 200))
            d.text((tx, ty), txt, font=cta_font, fill=(255, 248, 255, 255))

    # ---- Blend Pillow canvas into OpenCV frame ----
    banner_np = np.array(canvas, dtype=np.uint8)
    alpha_ch = banner_np[:, :, 3:4].astype(np.float32) / 255.0 * alpha_mul

    clip_y1 = max(0, y1)
    clip_y2 = min(h, y2)
    clip_x1 = max(0, x1)
    clip_x2 = min(w, x2)
    if clip_y1 >= clip_y2 or clip_x1 >= clip_x2:
        return

    by1, by2 = clip_y1 - y1, clip_y2 - y1
    bx1_c, bx2_c = clip_x1 - x1, clip_x2 - x1

    roi = frame[clip_y1:clip_y2, clip_x1:clip_x2].astype(np.float32)
    # Pillow = RGB, OpenCV = BGR → swap channels
    fg = banner_np[by1:by2, bx1_c:bx2_c, :3][:, :, ::-1].astype(np.float32)
    a = alpha_ch[by1:by2, bx1_c:bx2_c]
    frame[clip_y1:clip_y2, clip_x1:clip_x2] = (fg * a + roi * (1.0 - a)).astype(np.uint8)


def _draw_subtitle_on_frame(
    frame,
    lines: list[str],
    font_size: int,
    margin_v: int,
    settings: Settings,
) -> None:
    """Draw styled subtitle text on a frame in-place using Pillow (supports Unicode/Cyrillic)."""
    import cv2
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont

    if not lines:
        return

    h, w = frame.shape[:2]

    # Resolve a TrueType font; prefer bold Arial which supports Cyrillic
    _FONT_CANDIDATES = [
        "/System/Library/Fonts/Supplemental/Arial Black.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/Library/Fonts/Arial Unicode.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    font_obj = None
    for fp in _FONT_CANDIDATES:
        try:
            font_obj = ImageFont.truetype(fp, font_size)
            break
        except Exception:
            continue
    if font_obj is None:
        font_obj = ImageFont.load_default()

    text_color = tuple(int(c) for c in reversed(settings.render.subtitle_color_bgr))        # BGR→RGB
    outline_color = tuple(int(c) for c in reversed(settings.render.subtitle_outline_color_bgr))
    shadow_color = tuple(int(c) for c in reversed(settings.render.subtitle_shadow_color_bgr))

    # Measure each line and shrink font if any line exceeds 90% of frame width
    max_text_w = int(w * 0.90)
    tmp_img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    tmp_d = ImageDraw.Draw(tmp_img)
    line_dims = []
    for line in lines:
        bb = tmp_d.textbbox((0, 0), line, font=font_obj)
        line_dims.append((bb[2] - bb[0], bb[3] - bb[1], bb[0], bb[1]))
    max_line_w = max((lw for lw, _, _, _ in line_dims), default=0)
    if max_line_w > max_text_w and max_line_w > 0:
        shrink = max_text_w / max_line_w
        font_size = max(24, int(font_size * shrink))
        font_obj = ImageFont.truetype(font_obj.path, font_size)
        line_dims = []
        for line in lines:
            bb = tmp_d.textbbox((0, 0), line, font=font_obj)
            line_dims.append((bb[2] - bb[0], bb[3] - bb[1], bb[0], bb[1]))

    total_h = sum(lh for _, lh, _, _ in line_dims) + (len(lines) - 1) * 8
    box_y2 = h - margin_v
    box_y1 = box_y2 - total_h

    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(canvas)

    outline_px = max(1, int(settings.render.subtitle_outline))
    shadow_px = max(1, int(settings.render.subtitle_shadow))

    y = box_y1
    for i, line in enumerate(lines):
        lw, lh, off_x, off_y = line_dims[i]
        x = (w - lw) // 2 - off_x
        # Shadow
        d.text((x + shadow_px, y - off_y + shadow_px), line, font=font_obj, fill=(*shadow_color, 200))
        # Outline (8 directions)
        for dx, dy in [(-1, -1), (1, -1), (-1, 1), (1, 1),
                       (0, -1), (0, 1), (-1, 0), (1, 0)]:
            d.text((x + dx * outline_px, y - off_y + dy * outline_px),
                   line, font=font_obj, fill=(*outline_color, 255))
        # Main text
        d.text((x, y - off_y), line, font=font_obj, fill=(*text_color, 255))
        y += lh + 6

    # Blend the canvas into the OpenCV frame
    canvas_np = np.array(canvas, dtype=np.uint8)
    alpha = canvas_np[:, :, 3:4].astype(np.float32) / 255.0
    fg = canvas_np[:, :, :3][:, :, ::-1].astype(np.float32)  # RGB→BGR
    bg = frame.astype(np.float32)
    frame[:] = (fg * alpha + bg * (1.0 - alpha)).astype(np.uint8)


def _draw_subtitle_footer(frame, settings: Settings) -> None:
    """Draw the footer label using Pillow so Cyrillic renders correctly."""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont

    if not settings.render.subtitle_footer_enabled:
        return
    footer_text = settings.render.subtitle_footer_text.strip()
    if not footer_text:
        return

    h, w = frame.shape[:2]
    footer_size = max(18, int(settings.render.subtitle_footer_font_scale * 32))
    _FONT_CANDIDATES = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/Library/Fonts/Arial Unicode.ttf",
    ]
    font_obj = None
    for fp in _FONT_CANDIDATES:
        try:
            font_obj = ImageFont.truetype(fp, footer_size)
            break
        except Exception:
            continue
    if font_obj is None:
        font_obj = ImageFont.load_default()

    tmp = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    td = ImageDraw.Draw(tmp)
    bb = td.textbbox((0, 0), footer_text, font=font_obj)
    fw, fh = bb[2] - bb[0], bb[3] - bb[1]
    footer_bottom_margin = max(24, settings.render.subtitle_footer_bottom_margin)
    fy_top = h - footer_bottom_margin - fh
    fx = (w - fw) // 2 - bb[0]

    pad_x, pad_y = 14, 6
    bx1, by1 = max(0, fx - pad_x), max(0, fy_top - bb[1] - pad_y)
    bx2, by2 = min(w - 1, fx + fw + pad_x), min(h - 1, fy_top - bb[1] + fh + pad_y)

    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(canvas)
    d.rounded_rectangle([bx1, by1, bx2, by2], radius=10, fill=(68, 31, 112, 190))
    d.text((fx + 1, fy_top - bb[1] + 1), footer_text, font=font_obj, fill=(30, 13, 50, 200))
    d.text((fx, fy_top - bb[1]), footer_text, font=font_obj, fill=(241, 226, 255, 255))

    canvas_np = np.array(canvas, dtype=np.uint8)
    alpha = canvas_np[:, :, 3:4].astype(np.float32) / 255.0
    fg = canvas_np[:, :, :3][:, :, ::-1].astype(np.float32)
    bg = frame.astype(np.float32)
    frame[:] = (fg * alpha + bg * (1.0 - alpha)).astype(np.uint8)


def _burn_subtitles_opencv(
    input_path: Path,
    output_path: Path,
    items: list[SrtItem],
    settings: Settings,
    subtitle_margin_override: int | None = None,
) -> None:
    """Post-process a rendered clip to burn subtitles using OpenCV pipe → FFmpeg."""
    import cv2

    cap = cv2.VideoCapture(str(input_path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    tmp_out = output_path.with_name(output_path.stem + "_subs.mp4")

    encode_cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo", "-vcodec", "rawvideo",
        "-pix_fmt", "bgr24",
        "-s", f"{width}x{height}",
        "-r", str(fps),
        "-i", "pipe:0",
        "-i", str(input_path),
        "-map", "0:v", "-map", "1:a?",
        "-c:v", settings.render.video_codec,
        "-pix_fmt", "yuv420p",
        "-preset", settings.render.preset,
        "-crf", str(settings.render.crf),
        "-c:a", "copy",
        "-movflags", "+faststart",
        str(tmp_out),
    ]

    encoder = subprocess.Popen(encode_cmd, stdin=subprocess.PIPE,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    frame_idx = 0
    font_size = settings.render.subtitle_font_size
    margin_v = subtitle_margin_override if subtitle_margin_override is not None else settings.render.subtitle_margin_v
    max_lines = settings.render.subtitle_max_lines
    max_words_per_line = settings.render.subtitle_max_words_per_line
    promo_icon = None
    if settings.render.promo_enabled and settings.render.promo_icon_path:
        promo_icon = cv2.imread(settings.render.promo_icon_path, cv2.IMREAD_UNCHANGED)

    # Static overlay image mode: if promo_overlay_image_path is set,
    # load it once and blend it onto every frame instead of drawing programmatically.
    promo_overlay_img = None
    if settings.render.promo_enabled and settings.render.promo_overlay_image_path:
        raw = cv2.imread(settings.render.promo_overlay_image_path, cv2.IMREAD_UNCHANGED)
        if raw is not None:
            promo_overlay_img = raw

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        t = frame_idx / fps
        frame_idx += 1

        start = settings.render.promo_start_seconds
        duration = settings.render.promo_duration_seconds
        promo_end = float("inf") if duration <= 0 else start + duration
        if promo_overlay_img is not None and t >= start and t <= promo_end:
            _blend_static_overlay(frame, promo_overlay_img, settings)
        elif promo_overlay_img is None:
            _draw_promo_banner(frame, t, settings, promo_icon)

        active = next((it for it in items if it.start <= t < it.end), None)
        if active:
            page_lines = _paged_subtitle_lines(
                text=active.text,
                t=t,
                start=active.start,
                end=active.end,
                max_lines=max_lines,
                max_words_per_line=max_words_per_line,
            )
            _draw_subtitle_on_frame(
                frame,
                page_lines,
                font_size,
                margin_v,
                settings,
            )

        if settings.render.subtitle_footer_enabled:
            _draw_subtitle_footer(frame, settings)

        try:
            encoder.stdin.write(frame.tobytes())
        except BrokenPipeError:
            break

    cap.release()
    try:
        encoder.stdin.close()
    except Exception:
        pass
    encoder.wait()

    if encoder.returncode == 0 and tmp_out.exists():
        tmp_out.replace(output_path)
    else:
        tmp_out.unlink(missing_ok=True)


def _mix_background_music(input_path: Path, output_path: Path, settings: Settings) -> None:
    music_path = settings.render.background_music_path
    if not music_path:
        return

    tmp_out = output_path.with_name(output_path.stem + "_music.mp4")
    volume = max(0.0, min(1.0, settings.render.background_music_volume))
    command = [
        "ffmpeg", "-y",
        "-i", str(input_path),
        "-stream_loop", "-1",
        "-i", music_path,
        "-filter_complex",
        f"[1:a]volume={volume}[bgm];[0:a][bgm]amix=inputs=2:duration=first:dropout_transition=2[aout]",
        "-map", "0:v",
        "-map", "[aout]",
        "-c:v", "copy",
        "-c:a", settings.render.audio_codec,
        "-shortest",
        "-movflags", "+faststart",
        str(tmp_out),
    ]
    proc = subprocess.run(command, text=True, capture_output=True)
    if proc.returncode != 0:
        tmp_out.unlink(missing_ok=True)
        raise MediaError(
            f"FFmpeg background music mix failed ({proc.returncode})\n"
            f"cmd: {' '.join(command)}\n"
            f"stderr: {proc.stderr[-3000:]}"
        )
    tmp_out.replace(output_path)


# --------------------------------------------------------------------------- #
#  FFmpeg filter graph                                                          #
# --------------------------------------------------------------------------- #

def _build_complex_filter(
    src_w: int, src_h: int,
    settings: Settings,
    focus_x: float,
) -> tuple[str, str]:
    tw = settings.render.target_width
    th = settings.render.target_height
    sigma = settings.render.blur_sigma
    crop_w, crop_h, cx, cy = _compute_crop(src_w, src_h, tw, th, focus_x)

    mode = settings.render.reframe_mode.lower().strip()
    keep_ratio = crop_w / max(1, src_w)
    if mode not in {"crop", "fit", "auto"}:
        mode = "auto"
    if mode == "auto":
        mode = "fit" if keep_ratio < settings.render.auto_crop_min_keep_ratio else "crop"

    bg = (
        f"[0:v]scale={tw}:{th}:force_original_aspect_ratio=increase,"
        f"crop={tw}:{th},gblur=sigma={sigma}[bg]"
    )
    if mode == "fit":
        fg = f"[0:v]scale={tw}:{th}:force_original_aspect_ratio=decrease[fg]"
    else:
        fg = f"[0:v]crop={crop_w}:{crop_h}:{cx}:{cy},scale={tw}:{th}[fg]"
    overlay = "[bg][fg]overlay=(W-w)/2:(H-h)/2[vfinal]"
    return f"{bg};{fg};{overlay}", "vfinal"


def _resolve_reframe_mode(src_w: int, src_h: int, settings: Settings, focus_x: float) -> str:
    tw = settings.render.target_width
    th = settings.render.target_height
    crop_w, _crop_h, _cx, _cy = _compute_crop(src_w, src_h, tw, th, focus_x)
    mode = settings.render.reframe_mode.lower().strip()
    keep_ratio = crop_w / max(1, src_w)
    if mode not in {"crop", "fit", "auto"}:
        mode = "auto"
    if mode == "auto":
        mode = "fit" if keep_ratio < settings.render.auto_crop_min_keep_ratio else "crop"
    return mode


def _subtitle_margin_for_mode(src_w: int, src_h: int, settings: Settings, mode: str) -> int:
    """Compute subtitle margin; in fit mode keep text directly under foreground video."""
    tw = settings.render.target_width
    th = settings.render.target_height

    if mode != "fit":
        return settings.render.subtitle_margin_v

    scale = min(tw / max(1, src_w), th / max(1, src_h))
    fg_h = max(1, int(round(src_h * scale)))
    fg_y2 = (th + fg_h) // 2
    # Place subtitles just below the movie area, not deep in the bottom blur zone.
    sub_bottom_y = min(th - 56, fg_y2 + 78)
    return max(48, th - sub_bottom_y)


# --------------------------------------------------------------------------- #
#  Public entry point                                                           #
# --------------------------------------------------------------------------- #

def render_clip(
    settings: Settings,
    input_video_path: str | Path,
    output_clip_path: str | Path,
    subtitles_path: str | Path | None,
    start: float,
    end: float,
) -> None:
    output_path = Path(output_clip_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Slice subtitles → SRT + ASS sidecar files
    subtitle_items: list[SrtItem] = []
    if subtitles_path:
        all_items = parse_srt(subtitles_path)
        sliced = slice_srt(all_items, start, end)
        if sliced:
            write_srt(sliced, output_path.with_suffix(".srt"))
            srt_to_ass(
                sliced, output_path.with_suffix(".ass"),
                font_name=settings.render.subtitle_font_name,
                font_size=settings.render.subtitle_font_size,
                outline=settings.render.subtitle_outline,
                shadow=settings.render.subtitle_shadow,
                margin_v=settings.render.subtitle_margin_v,
            )
            subtitle_items = sliced

    # Smart crop focus detection
    focus_x = 0.5
    if settings.render.smart_crop_enabled:
        ratio = estimate_focus_x_ratio(
            video_path=str(input_video_path), start=start, end=end,
            sample_seconds=settings.render.smart_crop_sample_seconds,
            max_samples=settings.render.smart_crop_max_samples,
        )
        if ratio is not None:
            focus_x = min(0.9, max(0.1, ratio))

    src_w, src_h = get_video_dimensions(input_video_path)
    selected_mode = _resolve_reframe_mode(src_w, src_h, settings, focus_x)
    complex_filter, out_pad = _build_complex_filter(src_w, src_h, settings, focus_x)

    # Step 1: blur+crop render (no subtitle yet)
    command = [
        "ffmpeg", "-y",
        "-ss", f"{start:.3f}", "-to", f"{end:.3f}",
        "-i", str(input_video_path),
        "-filter_complex", complex_filter,
        "-map", f"[{out_pad}]", "-map", "0:a?",
    ]
    if settings.render.loudnorm:
        target = getattr(settings.render, 'loudnorm_target_lufs', -13)
        command += ["-af", f"loudnorm=I={target}:TP=-1.5:LRA=11"]
    command += [
        "-c:v", settings.render.video_codec,
        "-pix_fmt", "yuv420p",
        "-preset", settings.render.preset,
        "-crf", str(settings.render.crf),
        "-c:a", settings.render.audio_codec,
        "-movflags", "+faststart",
        str(output_path),
    ]
    proc = subprocess.run(command, text=True, capture_output=True)
    if proc.returncode != 0:
        raise MediaError(
            f"FFmpeg render failed ({proc.returncode})\n"
            f"cmd: {' '.join(command)}\n"
            f"stderr: {proc.stderr[-3000:]}"
        )

    # Step 2: burn subtitles via OpenCV (works without libass/libfreetype)
    if subtitle_items or settings.render.promo_enabled:
        subtitle_margin = _subtitle_margin_for_mode(src_w, src_h, settings, selected_mode)
        _burn_subtitles_opencv(
            output_path,
            output_path,
            subtitle_items,
            settings,
            subtitle_margin_override=subtitle_margin,
        )

    if settings.render.background_music_path:
        _mix_background_music(output_path, output_path, settings)
