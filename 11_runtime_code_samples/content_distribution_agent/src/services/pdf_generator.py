"""Generate Timecodes.pdf from timecode entries + intake assessment."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from content_distribution.models.contracts import IntakeResult, TimecodeEntry, VideoStatus

# Status → human-readable Russian label + colour (R, G, B)
_STATUS_META: dict[VideoStatus, tuple[str, tuple[float, float, float]]] = {
    VideoStatus.ready_to_post:  ("✅ ГОТОВО К ПОСТИНГУ",  (0.08, 0.55, 0.22)),
    VideoStatus.cut_to_clips:   ("✂️  РЕЗАТЬ НА КЛИПЫ",   (0.80, 0.45, 0.00)),
    VideoStatus.ready_as_video: ("🎬 ГОТОВО КАК ВИДЕО",   (0.08, 0.35, 0.70)),
    VideoStatus.weak_content:   ("⚠️  СЛАБЫЙ КОНТЕНТ",     (0.72, 0.10, 0.10)),
}


def _format_duration(seconds: float) -> str:
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}ч {m}мин {s}сек"
    return f"{m}мин {s}сек"


def generate_timecodes_pdf(
    output_path: Path,
    video_filename: str,
    duration_seconds: float,
    result: IntakeResult,
    created_at: datetime | None = None,
) -> None:
    """Write Timecodes.pdf using reportlab."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
        )
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.lib.enums import TA_LEFT, TA_CENTER
    except ImportError:
        _generate_txt_fallback(output_path, video_filename, duration_seconds, result, created_at)
        return

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    styles = getSampleStyleSheet()
    style_title = ParagraphStyle(
        "DocTitle",
        parent=styles["Title"],
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#1a1a2e"),
        spaceAfter=6,
    )
    style_meta = ParagraphStyle(
        "Meta",
        parent=styles["Normal"],
        fontSize=9,
        textColor=colors.HexColor("#666666"),
        spaceAfter=4,
    )
    style_status = ParagraphStyle(
        "Status",
        parent=styles["Normal"],
        fontSize=13,
        leading=18,
        spaceAfter=4,
    )
    style_assessment = ParagraphStyle(
        "Assessment",
        parent=styles["Normal"],
        fontSize=10,
        leading=15,
        textColor=colors.HexColor("#333333"),
        spaceAfter=10,
    )
    style_tc_ts = ParagraphStyle(
        "TcTs",
        parent=styles["Normal"],
        fontSize=10,
        textColor=colors.HexColor("#1a6fb5"),
        fontName="Helvetica-Bold",
    )
    style_tc_title = ParagraphStyle(
        "TcTitle",
        parent=styles["Normal"],
        fontSize=10,
        fontName="Helvetica-Bold",
        textColor=colors.HexColor("#1a1a2e"),
    )
    style_tc_desc = ParagraphStyle(
        "TcDesc",
        parent=styles["Normal"],
        fontSize=9,
        textColor=colors.HexColor("#555555"),
        leading=13,
    )

    status_label, status_rgb = _STATUS_META.get(
        result.status, ("НЕИЗВЕСТНО", (0.3, 0.3, 0.3))
    )
    status_color = colors.Color(*status_rgb)

    created_str = (created_at or datetime.now()).strftime("%d.%m.%Y %H:%M")

    story = []

    # Header
    story.append(Paragraph("ТАЙМКОДЫ", style_title))
    story.append(Paragraph(f"Файл: <b>{video_filename}</b>", style_meta))
    story.append(Paragraph(
        f"Дата: {created_str}  |  Длительность: {_format_duration(duration_seconds)}", style_meta
    ))
    story.append(Spacer(1, 0.3 * cm))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#dddddd")))
    story.append(Spacer(1, 0.3 * cm))

    # Status + rating
    style_status_colored = ParagraphStyle(
        "StatusColored",
        parent=style_status,
        textColor=status_color,
    )
    story.append(Paragraph(f"{status_label}   •   Оценка: <b>{result.rating}/10</b>", style_status_colored))
    story.append(Spacer(1, 0.2 * cm))

    # Assessment
    story.append(Paragraph(result.assessment.replace("\n", "<br/>"), style_assessment))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#dddddd")))
    story.append(Spacer(1, 0.4 * cm))

    # Timecodes section header
    story.append(Paragraph("<b>ТАЙМКОДЫ / ГЛАВЫ</b>", ParagraphStyle(
        "TCHeader",
        parent=styles["Normal"],
        fontSize=11,
        fontName="Helvetica-Bold",
        textColor=colors.HexColor("#1a1a2e"),
        spaceAfter=6,
    )))

    if result.timecodes:
        table_data = [["Время", "Тема", "Краткое содержание"]]
        for tc in result.timecodes:
            table_data.append([
                Paragraph(tc.timestamp, style_tc_ts),
                Paragraph(tc.title, style_tc_title),
                Paragraph(tc.description, style_tc_desc),
            ])

        col_widths = [2.5 * cm, 5.5 * cm, 9.0 * cm]
        tc_table = Table(table_data, colWidths=col_widths, repeatRows=1)
        tc_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1a2e")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 9),
            ("ALIGN", (0, 0), (-1, 0), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f7ff")]),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(tc_table)
    else:
        story.append(Paragraph("Таймкоды не сгенерированы (транскрипция недоступна).", style_meta))

    doc.build(story)


def _generate_txt_fallback(
    output_path: Path,
    video_filename: str,
    duration_seconds: float,
    result: IntakeResult,
    created_at: datetime | None,
) -> None:
    """Fallback plain-text file if reportlab is not installed."""
    txt_path = output_path.with_suffix(".txt")
    created_str = (created_at or datetime.now()).strftime("%d.%m.%Y %H:%M")
    status_label, _ = _STATUS_META.get(result.status, ("НЕИЗВЕСТНО", (0.3, 0.3, 0.3)))
    lines = [
        "ТАЙМКОДЫ",
        f"Файл: {video_filename}",
        f"Дата: {created_str}  |  Длительность: {_format_duration(duration_seconds)}",
        "",
        f"СТАТУС: {status_label}   |   ОЦЕНКА: {result.rating}/10",
        "",
        result.assessment,
        "",
        "--- ГЛАВЫ ---",
    ]
    for tc in result.timecodes:
        lines.append(f"{tc.timestamp}  {tc.title}")
        if tc.description:
            lines.append(f"           {tc.description}")
    txt_path.write_text("\n".join(lines), encoding="utf-8")
    # Rename so callers still get a "Timecodes.pdf"-named path (just .txt)
    if txt_path != output_path:
        txt_path.rename(output_path.with_suffix(".txt"))
