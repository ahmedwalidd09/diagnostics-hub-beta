import os
from datetime import datetime
from typing import Dict, Any
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


def generate_html_report(scan_data: Dict[str, Any], output_path: str) -> str:
    """Generate a standalone dark-themed HTML diagnostic report."""
    score = scan_data.get("score", 0)
    status = scan_data.get("status", "Unknown")
    timestamp = scan_data.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    categories = scan_data.get("categories", {})
    recommendations = scan_data.get("recommendations", [])

    # Color mapping
    if score >= 85:
        score_color = "#3fb950"
        badge_text = "🟢 Healthy"
    elif score >= 60:
        score_color = "#d29922"
        badge_text = "🟡 Needs Optimization"
    else:
        score_color = "#f85149"
        badge_text = "🔴 Critical Performance Issues"

    cat_html = ""
    for cat_name, cat_info in categories.items():
        c_score = cat_info.get("score", 0)
        c_status = cat_info.get("status", "Healthy")
        c_findings = cat_info.get("findings", "")
        c_badge_color = "#3fb950" if c_score >= 80 else ("#d29922" if c_score >= 50 else "#f85149")

        cat_html += f"""
        <div class="category-card">
            <div class="cat-header">
                <span class="cat-title">{cat_name}</span>
                <span class="cat-badge" style="background-color: {c_badge_color}22; color: {c_badge_color}; border: 1px solid {c_badge_color};">
                    Score: {c_score}/100 — {c_status}
                </span>
            </div>
            <div class="cat-findings">{c_findings}</div>
        </div>
        """

    rec_html = "".join([f"<li>{r}</li>" for r in recommendations]) if recommendations else "<li>No issues found. Your system is running optimally!</li>"

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Windows Diagnostics Hub — Diagnostic Report</title>
    <style>
        body {{
            background-color: #0d1117;
            color: #e6edf3;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            margin: 0;
            padding: 30px;
        }}
        .container {{
            max-width: 900px;
            margin: 0 auto;
        }}
        .header {{
            text-align: center;
            padding-bottom: 25px;
            border-bottom: 1px solid #30363d;
        }}
        .header h1 {{
            color: #58a6ff;
            margin: 0 0 10px 0;
            font-size: 28px;
        }}
        .header .meta {{
            color: #8b949e;
            font-size: 14px;
        }}
        .score-box {{
            display: flex;
            align-items: center;
            justify-content: center;
            background-color: #161b22;
            border: 1px solid #30363d;
            border-radius: 12px;
            padding: 24px;
            margin: 25px 0;
        }}
        .score-circle {{
            font-size: 48px;
            font-weight: bold;
            color: {score_color};
            margin-right: 25px;
        }}
        .score-desc h2 {{
            margin: 0 0 8px 0;
            color: #ffffff;
            font-size: 22px;
        }}
        .score-desc p {{
            margin: 0;
            color: #8b949e;
        }}
        .section-title {{
            font-size: 18px;
            color: #ffffff;
            margin: 30px 0 15px 0;
            border-bottom: 1px solid #21262d;
            padding-bottom: 8px;
        }}
        .category-card {{
            background-color: #161b22;
            border: 1px solid #30363d;
            border-radius: 8px;
            padding: 16px;
            margin-bottom: 15px;
        }}
        .cat-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }}
        .cat-title {{
            font-size: 16px;
            font-weight: 600;
            color: #ffffff;
        }}
        .cat-badge {{
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 600;
        }}
        .cat-findings {{
            color: #c9d1d9;
            font-size: 14px;
            line-height: 1.5;
        }}
        .recommendations {{
            background-color: #161b22;
            border: 1px solid #30363d;
            border-radius: 8px;
            padding: 20px;
        }}
        .recommendations ul {{
            margin: 0;
            padding-left: 20px;
            color: #e6edf3;
            line-height: 1.6;
        }}
        .footer {{
            text-align: center;
            color: #8b949e;
            font-size: 12px;
            margin-top: 40px;
            border-top: 1px solid #21262d;
            padding-top: 15px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🛠️ Windows Diagnostics Hub</h1>
            <div class="meta">Diagnostic System Performance Report • Generated: {timestamp}</div>
        </div>

        <div class="score-box">
            <div class="score-circle">{score}/100</div>
            <div class="score-desc">
                <h2>{badge_text}</h2>
                <p>Status: {status}. Read below for detailed category findings and recommended optimizations.</p>
            </div>
        </div>

        <div class="section-title">📊 Category Diagnostics</div>
        {cat_html}

        <div class="section-title">💡 Actionable Recommendations</div>
        <div class="recommendations">
            <ul>
                {rec_html}
            </ul>
        </div>

        <div class="footer">
            Windows Diagnostics Hub • Built with PyQt6 and Python 3.11+
        </div>
    </div>
</body>
</html>
"""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    return output_path


def generate_pdf_report(scan_data: Dict[str, Any], output_path: str) -> str:
    """Generate a PDF diagnostic report using ReportLab."""
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        doc = SimpleDocTemplate(output_path, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
        story = []
        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            'ReportTitle',
            parent=styles['Heading1'],
            fontSize=22,
            leading=26,
            textColor=colors.HexColor('#1f6feb'),
            alignment=1
        )
        subtitle_style = ParagraphStyle(
            'ReportSubtitle',
            parent=styles['Normal'],
            fontSize=11,
            leading=14,
            textColor=colors.HexColor('#57606a'),
            alignment=1
        )
        h2_style = ParagraphStyle(
            'SectionHeader',
            parent=styles['Heading2'],
            fontSize=14,
            leading=18,
            textColor=colors.HexColor('#24292f'),
            spaceBefore=12,
            spaceAfter=6
        )
        body_style = ParagraphStyle(
            'Body',
            parent=styles['Normal'],
            fontSize=10,
            leading=14,
            textColor=colors.HexColor('#24292f')
        )

        story.append(Paragraph("Windows Diagnostics Hub", title_style))
        story.append(Paragraph(f"System Health Report • {scan_data.get('timestamp', '')}", subtitle_style))
        story.append(Spacer(1, 15))

        score = scan_data.get("score", 0)
        score_text = f"<b>Overall PC Health Score: {score}/100</b> ({scan_data.get('status', 'Healthy')})"
        story.append(Paragraph(score_text, h2_style))
        story.append(Spacer(1, 10))

        # Categories Table
        categories = scan_data.get("categories", {})
        table_data = [["Category", "Score", "Status", "Summary"]]
        for name, data in categories.items():
            clean_finding = data.get("findings", "").replace("<b>", "").replace("</b>", "")
            table_data.append([
                Paragraph(name, body_style),
                str(data.get("score", 0)),
                data.get("status", "Good"),
                Paragraph(clean_finding[:160] + "..." if len(clean_finding) > 160 else clean_finding, body_style)
            ])

        t = Table(table_data, colWidths=[120, 45, 75, 300])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0969da')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (1, 0), (2, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d0d7de')),
        ]))
        story.append(t)
        story.append(Spacer(1, 15))

        story.append(Paragraph("Actionable Recommendations", h2_style))
        recs = scan_data.get("recommendations", [])
        for r in recs:
            story.append(Paragraph(f"• {r}", body_style))
            story.append(Spacer(1, 4))

        doc.build(story)
        return output_path
    except Exception as e:
        logger.error(f"Failed to generate PDF report: {e}")
        # Fallback to HTML
        html_fallback = output_path.replace(".pdf", ".html")
        return generate_html_report(scan_data, html_fallback)
