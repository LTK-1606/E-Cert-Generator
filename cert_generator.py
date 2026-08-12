import io
import os
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from pypdf import PdfReader, PdfWriter

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_PATH = os.path.join(BASE_DIR, 'fonts', 'Charissil-Bold.ttf')

def draw_wrapped_string(can, text, x_center, y, max_width, font_name, font_size, center_align=True):
    """
    Wraps text into multiple lines when it exceeds max_width at word boundaries,
    preserving the original font size instead of shrinking it.
    """
    can.setFont(font_name, font_size)
    words = str(text).split(' ')
    lines = []
    current_line = []

    for word in words:
        test_line = ' '.join(current_line + [word])
        if pdfmetrics.stringWidth(test_line, font_name, font_size) <= max_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(' '.join(current_line))
                current_line = [word]
            else:
                lines.append(word)
                current_line = []
    
    if current_line:
        lines.append(' '.join(current_line))

    line_height = font_size * 1.2

    for i, line in enumerate(lines):
        line_y = y - (i * line_height)
        if center_align:
            can.drawCentredString(x_center, line_y, line)
        else:
            can.drawString(x_center, line_y, line)

def generate_cert(template_bytes, row_dict, template_config, output_path=None):
    """
    template_config format:
    { "ColumnName": {"x": 300, "y": 400, "font_size": 24, "center_align": True, "max_width": 450} }
    """
    font_name = 'Helvetica-Bold'
    if os.path.exists(FONT_PATH):
        pdfmetrics.registerFont(TTFont('CustomFont', FONT_PATH))
        font_name = 'CustomFont'

    reader = PdfReader(io.BytesIO(template_bytes))
    page = reader.pages[0]
    page_width = float(page.mediabox.width)
    page_height = float(page.mediabox.height)

    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=(page_width, page_height))

    for field, cfg in template_config.items():
        val = str(row_dict.get(field, ''))
        if not val or val.lower() == 'nan':
            continue

        x = cfg['x']
        y = cfg['y']
        size = cfg['font_size']
        center = cfg.get('center_align', True)
        max_w = cfg.get('max_width', 450)

        draw_wrapped_string(can, val, x, y, max_w, font_name, size, center)

    can.save()
    packet.seek(0)

    overlay_reader = PdfReader(packet)
    page.merge_page(overlay_reader.pages[0])

    writer = PdfWriter()
    writer.add_page(page)

    if output_path:
        with open(output_path, "wb") as f:
            writer.write(f)
        return output_path
    else:
        output_stream = io.BytesIO()
        writer.write(output_stream)
        return output_stream.getvalue()