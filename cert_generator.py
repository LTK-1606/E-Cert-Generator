from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import landscape, A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from pypdf import PdfReader, PdfWriter
from config import TEMPLATE_PDF, get_resource_path

def draw_auto_scaled_string(can, text, x_center, y, max_width, font_name, initial_font_size):
    font_size = initial_font_size
    text_width = pdfmetrics.stringWidth(str(text), font_name, font_size)
    
    while text_width > max_width and font_size > 8:
        font_size -= 1
        text_width = pdfmetrics.stringWidth(str(text), font_name, font_size)
        
    can.setFont(font_name, font_size)
    can.drawCentredString(x_center, y, str(text))

def generate_cert(name, level, school, term, output_path):
    packet = BytesIO()
    can = canvas.Canvas(packet, pagesize=landscape(A4))

    font_path = get_resource_path('fonts/Charissil-Bold.ttf', internal=True)
    pdfmetrics.registerFont(TTFont('Charissil-Bold', font_path))
    
    can.setFont("Charissil-Bold", 29)
    draw_auto_scaled_string(can, name, 300, 470, 450, "Charissil-Bold", 29)
    can.setFont("Charissil-Bold", 12)
    level_text = f"Primary {level}"
    can.drawCentredString(300, 420, level_text)
    can.drawCentredString(300, 400, str(school))
    term_text = f"{term}."
    can.drawCentredString(420, 349, term_text)
    
    can.save()
    packet.seek(0)
    
    new_pdf = PdfReader(packet)
    existing_pdf = PdfReader(open(TEMPLATE_PDF, "rb"))
    output = PdfWriter()
    
    page = existing_pdf.pages[0]
    page.merge_page(new_pdf.pages[0])
    output.add_page(page)
    
    with open(output_path, "wb") as outputStream:
        output.write(outputStream)