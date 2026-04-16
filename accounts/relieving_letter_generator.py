from reportlab.lib.pagesizes import A4
from reportlab.platypus import BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.lib.units import mm
from reportlab.lib import colors
from io import BytesIO
import os
from django.conf import settings


def get_logo_path():
    return os.path.join(settings.BASE_DIR, 'accounts', 'static', 'images', 'logo.png')


def header_footer(canvas_obj, doc):
    canvas_obj.saveState()
    width, height = A4

    # Logo
    logo_path = get_logo_path()
    try:
        if os.path.exists(logo_path):
            canvas_obj.drawImage(logo_path, 15*mm, height - 22*mm, width=15*mm, height=15*mm,
                                 preserveAspectRatio=True, mask='auto')
    except Exception as e:
        print(f"Logo error: {e}")

    # Company name
    canvas_obj.setFont("Helvetica-Bold", 16)
    canvas_obj.setFillColorRGB(0, 0, 0)
    canvas_obj.drawCentredString(width / 2, height - 13*mm, "TEOPLE TECHNOLOGIES")

    # Address
    canvas_obj.setFont("Helvetica", 9)
    canvas_obj.drawCentredString(width / 2, height - 19*mm,
                                 "Raj Residency, Beside Ojasvi appt, Near City Pride School, Ravet, Pune-412101")

    # Header line
    canvas_obj.setStrokeColorRGB(0, 0, 0)
    canvas_obj.setLineWidth(1)
    canvas_obj.line(15*mm, height - 23*mm, width - 15*mm, height - 23*mm)

    # Footer line
    canvas_obj.line(15*mm, 15*mm, width - 15*mm, 15*mm)

    # Footer text
    canvas_obj.setFont("Helvetica", 8)
    canvas_obj.drawCentredString(width / 2, 10*mm,
                                 "Website: https://teople.co.in/          Email id: yogita.rasal@teople.co.in")

    canvas_obj.restoreState()


def generate_relieving_letter_pdf(employee_name, designation, joining_date, last_working_day, relieving_date):
    buffer = BytesIO()

    doc = BaseDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=20*mm,
        rightMargin=20*mm,
        topMargin=30*mm,
        bottomMargin=22*mm,
    )

    frame = Frame(
        doc.leftMargin,
        doc.bottomMargin,
        doc.width,
        doc.height,
        id='normal'
    )

    template = PageTemplate(id='main', frames=frame, onPage=header_footer)
    doc.addPageTemplates([template])

    # Styles
    normal = ParagraphStyle('normal', fontName='Helvetica', fontSize=11, leading=17,
                            spaceAfter=0, spaceBefore=0, textColor=colors.black)
    bold_heading = ParagraphStyle('bold_heading', fontName='Helvetica-Bold', fontSize=11, leading=17,
                                  spaceAfter=0, spaceBefore=0, textColor=colors.black)
    title_style = ParagraphStyle('title', fontName='Helvetica-Bold', fontSize=14, leading=18,
                                 alignment=TA_CENTER, spaceAfter=0, spaceBefore=0,
                                 textColor=colors.black)
    right_style = ParagraphStyle('right', fontName='Helvetica', fontSize=11, leading=14,
                                 alignment=TA_RIGHT, spaceAfter=0, spaceBefore=0)

    story = []

    # Date (right aligned)
    story.append(Paragraph(f"Date: {relieving_date}", right_style))
    story.append(Spacer(1, 10*mm))

    # Title
    story.append(Paragraph('<u>RELIEVING LETTER</u>', title_style))
    story.append(Spacer(1, 8*mm))

    # To Whom It May Concern
    story.append(Paragraph("<b>To Whom It May Concern,</b>", bold_heading))
    story.append(Spacer(1, 6*mm))

    # Body paragraphs
    story.append(Paragraph(
        f"This is to certify that <b>Mr./Ms. {employee_name}</b> was employed with "
        f"<b>TEOPLE TECHNOLOGIES LLP</b> as <b>{designation}</b>.",
        normal))
    story.append(Spacer(1, 5*mm))

    story.append(Paragraph(
        f"He/She joined our organization on <b>{joining_date}</b> and his/her last working "
        f"day with us was <b>{last_working_day}</b>.",
        normal))
    story.append(Spacer(1, 5*mm))

    story.append(Paragraph(
        "During his/her tenure with us, he/she has been a valuable member of our team "
        "and has contributed significantly to the organization. We appreciate his/her "
        "dedication, hard work, and professionalism.",
        normal))
    story.append(Spacer(1, 5*mm))

    story.append(Paragraph(
        "We have settled all his/her dues and he/she is relieved from all responsibilities "
        "with effect from the last working day mentioned above.",
        normal))
    story.append(Spacer(1, 5*mm))

    story.append(Paragraph(
        "We wish him/her all the best for his/her future endeavors.",
        normal))
    story.append(Spacer(1, 10*mm))

    # Closing
    story.append(Paragraph("Sincerely,", normal))
    story.append(Spacer(1, 20*mm))

    # Company name with stamp space
    story.append(Paragraph("<b>TEOPLE TECHNOLOGIES</b>", bold_heading))
    story.append(Spacer(1, 18*mm))

    story.append(Paragraph("Authorized Signatory", normal))
    story.append(Paragraph("HR Department", normal))

    doc.build(story)
    buffer.seek(0)
    return buffer
