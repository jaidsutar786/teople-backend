from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.lib.units import mm
from reportlab.platypus import BaseDocTemplate, PageTemplate, Frame
from reportlab.lib import colors
from io import BytesIO
from datetime import datetime
import os
from django.conf import settings


def get_logo_path():
    return os.path.join(settings.BASE_DIR, 'accounts', 'static', 'images', 'logo.png')


def header_footer(canvas_obj, doc):
    canvas_obj.saveState()
    width, height = A4
    logo_path = get_logo_path()

    # Logo
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


def generate_offer_letter_pdf(employee_name, designation, salary, date):
    buffer = BytesIO()
    width, height = A4

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
    normal = ParagraphStyle('normal', fontName='Helvetica', fontSize=10, leading=15,
                            spaceAfter=0, spaceBefore=0, textColor=colors.black)
    bold_heading = ParagraphStyle('bold_heading', fontName='Helvetica-Bold', fontSize=10, leading=15,
                                  spaceAfter=4, spaceBefore=8, textColor=colors.black)
    title_style = ParagraphStyle('title', fontName='Helvetica-Bold', fontSize=14, leading=18,
                                 alignment=TA_CENTER, spaceAfter=10, spaceBefore=0,
                                 underlineProportion=1, textColor=colors.black)
    right_style = ParagraphStyle('right', fontName='Helvetica-Bold', fontSize=10, leading=14,
                                 alignment=TA_RIGHT, spaceAfter=0, spaceBefore=0)
    name_red = ParagraphStyle('name_red', fontName='Helvetica-Bold', fontSize=10, leading=14,
                              textColor=colors.red, spaceAfter=2, spaceBefore=6)
    indent = ParagraphStyle('indent', fontName='Helvetica', fontSize=10, leading=15,
                            leftIndent=10, spaceAfter=0, spaceBefore=0, textColor=colors.black)
    indent2 = ParagraphStyle('indent2', fontName='Helvetica', fontSize=10, leading=15,
                             leftIndent=20, spaceAfter=0, spaceBefore=0, textColor=colors.black)

    first_name = employee_name.split()[0]
    story = []

    # Date
    story.append(Paragraph(f"Date: {date}.", right_style))
    story.append(Spacer(1, 8*mm))

    # Title with underline
    story.append(Paragraph('<u>Appointment Letter</u>', title_style))
    story.append(Spacer(1, 4*mm))

    # Welcome
    story.append(Paragraph("Welcome to Teople Technologies...", normal))
    story.append(Spacer(1, 3*mm))

    # Employee name in red
    story.append(Paragraph(f"{employee_name},", name_red))

    # Dear
    story.append(Paragraph(f"Dear {first_name},", normal))
    story.append(Spacer(1, 3*mm))

    # Intro
    story.append(Paragraph(
        f"We are pleased to appoint you as a <b>{designation}</b> or in such other capacity as the "
        f"management of TEOPLE TECHNOLOGIES LLP, here in after called the Company, shall from "
        f"time to time determine, under the following terms and conditions",
        normal))
    story.append(Spacer(1, 4*mm))

    # 1. Date of Appointment
    story.append(Paragraph("1. Date of Appointment:", bold_heading))
    story.append(Paragraph(f"Your date of appointment is effective from date {date}.", indent))
    story.append(Spacer(1, 4*mm))

    # 2. Code of Conduct
    story.append(Paragraph("2. Code of Conduct:", bold_heading))

    conduct = [
        ("2.1", "The company may require you, at any time, to perform technical and other functions and you will be bound to carry out such functions."),
        ("2.2", "You shall maintain proper discipline and dignity of your office and shall deal with all matters with sobriety."),
        ("2.3", "You shall maintain and keep in your safe custody such books, registers, documents and other papers as may be issued to you or may come in your possession and shall return the same when required."),
        ("2.4", "You shall inform the Company of any changes in your personal data within 3 days of the occurrence of such change. Any notice required to be given to you shall be deemed to have been duly and properly given if delivered to you personally or sent by post to you at your address in India as recorded in the Company."),
        ("2.5", "You will observe work timings and holidays as applicable to your location and place of work."),
        ("2.6", "You shall be solely responsible for any issues that may arise between you and your Previous employer with regard to your previous employment and the Company is not responsible for the same."),
        ("2.7", "You will not borrow or accept any money, gift, reward or compensation for your personal gains from or otherwise place yourself under pecuniary obligation to any person/client with whom you may be having official dealings."),
    ]
    for num, text in conduct:
        story.append(Paragraph(f"<b>{num}</b> {text}", indent))
        story.append(Spacer(1, 3*mm))

    story.append(Paragraph(
        "<b>2.8</b> The Employee has also agreed and undertaken to enter into a service-bond with company for a period of 2 year from date of joining on terms and conditions as stated and expressed here under:",
        indent))
    story.append(Paragraph(
        "a) If an employee leaves a company before the end of the bond, he/she should pay the organization the salaried amount worked till date.",
        indent2))
    story.append(Spacer(1, 2*mm))
    story.append(Paragraph(
        "b) If anytime during the training or probation period he/she does not show expected performance or remains absent without prior permission or Misbehaves his/her service can be terminated by giving 1 day notice period. That during the period of employment, the employee shall be bound to Observe and abide by all terms and conditions and stipulation hereinafter contained as also by such other rules and regulations as may be framed by the company from time to time to be observed by company.",
        indent2))
    story.append(Spacer(1, 4*mm))

    # 3. Place of posting
    story.append(Paragraph("3. Place of posting:", bold_heading))
    story.append(Paragraph(
        "Your initial posting will be at Pune, Maharashtra, India. You will be liable to transfer in such capacity as the Company may time to time determine to any other location, departments, establishment, factory or branch of the Company or subsidiary, associate or Affiliate of the Company in India or abroad without claiming any extra remuneration for such transfers.",
        indent))
    story.append(Spacer(1, 4*mm))

    # 4. Leave
    story.append(Paragraph("4. Leave:", bold_heading))
    story.append(Paragraph(
        "You will be entitled to leave and other benefits in accordance with the rules of the Company.",
        indent))
    story.append(Spacer(1, 4*mm))

    # 5. Other Work
    story.append(Paragraph("5. Other Work:", bold_heading))
    story.append(Paragraph(
        "Your position is a fulltime employment with the Company and you shall devote your whole time and attention to the Company's business entrusted to you. You will not take up any other work for remuneration (part-time or otherwise) or work in an advisory capacity or be interested directly or indirectly (except as shareholder or debenture holder) in any other trade or business during the employment with the Company without the prior written permission of the Director of the Company.",
        indent))
    story.append(Spacer(1, 4*mm))

    # 6. Intellectual Property
    story.append(Paragraph("6. Intellectual Property and Confidential Information:", bold_heading))

    ip_points = [
        ("6.1", "You must always maintain the highest degree of confidentiality and keep as confidential the records, documents and other Confidential Information relating to the business of the Company which may be known to you or confided in you by any means and you will use such records, documents and information only in a duly authorized manner in the interest of the Company. For the purposes of this clause 'Confidential Information' means information about the Company's business and that of its customers which is not available to the general public and which may be learnt by you in the course of your employment. This includes, but is not limited to, information relating to the organization, its customer lists, employment policies, personnel, and information about the Company's products, processes including ideas, concepts, projections, technology, manuals, drawing, designs, specifications, and all papers, resumes, records and other documents containing such Confidential Information."),
        ("6.2", "At no time, you will be removed if any Confidential Information from the office is leaked without permission."),
        ("6.3", "Your duty to safeguard and not disclose Confidential Information will survive the expiration or termination of this Agreement and/or your employment with the Company."),
        ("6.4", "Breach of the conditions of this clause will render you liable to summary dismissal under clause above in addition to any other remedy the Company may have against you in law."),
        ("6.5", "You shall irrevocably, unconditionally and free of any cost, royalty or compensation, assign to the Company all rights, title and interests including the transfer rights and Intellectual Property Rights in all products, designs, software, embedded, electronics, intermediary, base software technology which is created or developed by you during the course of your employment in the Company. The Company shall have the right to obtain and hold in its own name, copyrights, trade-marks and other applicable registrations and seek such other protection as may be appropriate to the work, product and all designs, software created by you and you shall also provide the Company or any person designated by the Company all assistance as may be required and/or perfect the rights defined in this clause."),
    ]
    for num, text in ip_points:
        story.append(Paragraph(f"<b>{num}</b> {text}", indent))
        story.append(Spacer(1, 3*mm))

    # 7. Termination
    story.append(Paragraph("7. Termination", bold_heading))

    termination_points = [
        ("7.1", "Your appointment can be terminated by the Company, without any reason, by giving you not less than 3 month prior notice in writing or salary in lieu thereof. For the purpose of this clause, salary shall mean basic salary."),
        ("7.2", "You may terminate your employment with the Company, without any cause, by giving no less than 3 month prior notice in writing."),
        ("7.3", "The Company reserves the right to terminate your employment summarily without any notice period or termination payment, if it has reasonable ground to believe you are guilty of misconduct or negligence, or have committed any fundamental breach of contract or caused any loss to the Company."),
        ("7.4", "On the termination of your employment for whatever reason, you will return to the Company all property; documents and paper, both original and copies thereof, including any samples, literature, contracts, records, lists, drawings, blueprints, letters, notes, data and the like; and Confidential Information, in your possession or under your control relating to your employment or to clients' business affairs."),
        ("7.5", "The company may not terminate Trainee Engineer when under training period mention in the training clause 8.1. But can initiate termination if trainee engineer falls into clause 7.3."),
        ("7.6", "You may not be able to terminate your employment with the company when under the training period if appointed as Trainee Engineer."),
        ("7.7", "Trainee engineer can be terminated after training period if the performance criteria by the trainee is not met as set by his reporting supervisors or in case company don't have a position for the one Trainee was given training."),
    ]
    for num, text in termination_points:
        story.append(Paragraph(f"<b>{num}</b> {text}", indent))
        story.append(Spacer(1, 3*mm))

    # 8. Service Bond
    story.append(Paragraph("8. Service Bond:", bold_heading))
    story.append(Paragraph(
        "1. By accepting this Order you have unconditionally agreed to serve the Company for a minimum period of 2 year otherwise paid salary for those working months will be charged back. A separate Service Bond shall be assigned to that extra as and when required by the Company. The Service Bond shall form part of this Appointment Letter.",
        indent))
    story.append(Spacer(1, 3*mm))
    story.append(Paragraph(
        "2. In case if you wish to leave the company after completion of assured service, you need to give THREE MONTHS notice, failing which you need to pay back the Company, your last salary drawn for three months by way of Demand Draft in favor of the company towards compensation.",
        indent))
    story.append(Spacer(1, 4*mm))

    # 9. Salary
    story.append(Paragraph("9. Salary:", bold_heading))
    story.append(Paragraph(
        "9.1. The 1st month will be the training period, from the 2nd month you will get stipend. The probation period will be of six months from the date of joining.",
        indent))
    story.append(Spacer(1, 3*mm))
    story.append(Paragraph(
        "9.2 After successful completion of 3 month training and depending on the performance remuneration will be discussed and will be sent across as annexure to this appointment letter.",
        indent))
    story.append(Spacer(1, 3*mm))
    story.append(Paragraph(
        "9.3 Final settlement of Salary will be done after 10 days of the last working day.",
        indent))
    story.append(Spacer(1, 4*mm))

    # 10. Applicability
    story.append(Paragraph("10. Applicability of Company Policy:", bold_heading))
    story.append(Paragraph(
        "The Company shall be entitled to make policy declarations from time to time pertaining to matters like leave entitlement, maternity leave, employees' benefits, working hours, transfer policies, etc., and may alter the same from time to time at its sole discretion. All such policy decisions of the Company shall be binding on you and shall override this Agreement to that extent.",
        indent))
    story.append(Spacer(1, 6*mm))

    # Closing
    story.append(Paragraph(
        "We take pleasure in welcoming you to our Organization and look forward to a mutually beneficial association.",
        normal))
    story.append(Spacer(1, 3*mm))
    story.append(Paragraph("We wish you all the best in your career.", normal))
    story.append(Spacer(1, 20*mm))
    story.append(Paragraph("<b>TEOPLE TECHNOLOGIES.</b>", normal))
    story.append(Spacer(1, 18*mm))
    story.append(Paragraph("Authorized Signatory", normal))

    # Declaration page
    story.append(PageBreak())

    story.append(Paragraph('<u>Declaration</u>', title_style))
    story.append(Spacer(1, 6*mm))
    story.append(Paragraph(
        "I have read and understood the above terms and conditions of employment and I am accepting the same. I will be reporting for duty as mentioned in Date of Appointment clause.",
        normal))
    story.append(Spacer(1, 15*mm))
    story.append(Paragraph("Date of Acceptance: _____________________", normal))
    story.append(Spacer(1, 12*mm))
    story.append(Paragraph("Name: _____________________", normal))
    story.append(Spacer(1, 12*mm))
    story.append(Paragraph("Signature: _____________________", normal))

    doc.build(story)
    buffer.seek(0)
    return buffer
