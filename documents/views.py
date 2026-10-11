
import re
from io import BytesIO
from datetime import datetime
from difflib import SequenceMatcher
from xml.sax.saxutils import escape

from django.http import HttpResponse
from django.shortcuts import render
from pypdf import PdfReader

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    KeepTogether,
)

from .models import DocumentComparison


def home(request):
    return render(request, 'home.html')


def extract_fields(text):
    """Extract common labelled fields from PDF text."""

    patterns = {
        'Name': [
            r'^(?:full\s+name|applicant\s+name|name)\s*[:\-]\s*(.+)$',
        ],
        'Date of Birth': [
            r'^(?:date\s+of\s+birth|dob|birth\s+date)\s*[:\-]\s*(.+)$',
        ],
        'Date': [
            r'^(?:application\s+date|issue\s+date|date)\s*[:\-]\s*(.+)$',
        ],
        'Amount': [
            r'^(?:total\s+amount|application\s+fee|amount|fee)\s*[:\-]\s*(.+)$',
        ],
        'Email': [
            r'^(?:email|email\s+address)\s*[:\-]\s*(.+)$',
        ],
        'Phone': [
            r'^(?:phone|mobile|contact\s+number|phone\s+number)\s*[:\-]\s*(.+)$',
        ],
        'Address': [
            r'^(?:permanent\s+address|residential\s+address|address)\s*[:\-]\s*(.+)$',
        ],
    }

    extracted = {}

    for line in text.splitlines():
        line = line.strip()

        if not line:
            continue

        for field, field_patterns in patterns.items():
            if field in extracted:
                continue

            for pattern in field_patterns:
                match = re.search(pattern, line, re.IGNORECASE)

                if match:
                    value = match.group(1).strip()

                    if value:
                        extracted[field] = value
                        break

    if 'Email' not in extracted:
        email_match = re.search(
            r'\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b',
            text,
            re.IGNORECASE,
        )

        if email_match:
            extracted['Email'] = email_match.group(0)

    return extracted


def normalize_value(value):
    """Normalize text for basic comparison."""

    value = str(value).strip().lower()
    value = re.sub(r'\s+', ' ', value)

    return value.strip(' .,:;')


def normalize_date(value):
    """Recognize common date formats without changing the original value."""

    value = str(value).strip()

    formats = (
        '%d/%m/%Y',
        '%d-%m-%Y',
        '%d.%m.%Y',
        '%Y-%m-%d',
        '%Y/%m/%d',
        '%m/%d/%Y',
        '%m-%d-%Y',
    )

    for date_format in formats:
        try:
            parsed = datetime.strptime(value, date_format)
            return parsed.strftime('%Y-%m-%d')
        except ValueError:
            continue

    return None


def classify_difference(field, value1, value2):
    """Classify a detected difference and explain what to check."""

    if value1 == 'Not found':
        return {
            'status': 'Missing in Document 1',
            'reason': f'{field} was not extracted from Document 1.',
            'recommendation': 'Check Document 1 manually.',
        }

    if value2 == 'Not found':
        return {
            'status': 'Missing in Document 2',
            'reason': f'{field} was not extracted from Document 2.',
            'recommendation': 'Check Document 2 manually.',
        }

    normalized1 = normalize_value(value1)
    normalized2 = normalize_value(value2)

    if normalized1 == normalized2:
        return {
            'status': 'Match',
            'reason': 'Values match after basic normalization.',
            'recommendation': 'No action suggested.',
        }

    # Dates with different separators may represent the same date.
    if field.lower() in ('date', 'date of birth'):
        date1 = normalize_date(value1)
        date2 = normalize_date(value2)

        if date1 and date2 and date1 == date2:
            return {
                'status': 'Formatting variation',
                'reason': 'The dates match but use different formats.',
                'recommendation': 'Confirm the preferred date format.',
            }

    # Amounts can differ only because of currency symbols or separators.
    if field.lower() == 'amount':
        amount1 = re.sub(r'[,\s₹$€£]', '', value1)
        amount2 = re.sub(r'[,\s₹$€£]', '', value2)

        if amount1 == amount2:
            return {
                'status': 'Formatting variation',
                'reason': 'The amount text differs in formatting only.',
                'recommendation': 'Confirm the currency and amount.',
            }

    # Compare names without spaces and common punctuation.
    if field.lower() == 'name':
        name1 = re.sub(r'[^a-z0-9]', '', normalized1)
        name2 = re.sub(r'[^a-z0-9]', '', normalized2)

        if name1 == name2:
            return {
                'status': 'Formatting variation',
                'reason': 'The name differs only in spacing or punctuation.',
                'recommendation': 'Confirm the name against the original.',
            }

        similarity = SequenceMatcher(
            None, name1, name2
        ).ratio()

        if similarity >= 0.80:
            return {
                'status': 'Possible spelling mismatch',
                'reason': 'The names are similar but not identical.',
                'recommendation': 'Verify the spelling manually.',
            }

    return {
        'status': 'Mismatch',
        'reason': f'The values extracted for {field} are different.',
        'recommendation': 'Verify both original documents.',
    }


def compare_fields(fields1, fields2):
    """Compare extracted fields and classify differences."""

    mismatches = []
    all_fields = sorted(set(fields1) | set(fields2))

    for field in all_fields:
        value1 = fields1.get(field, '')
        value2 = fields2.get(field, '')

        if not value1:
            value1 = 'Not found'

        if not value2:
            value2 = 'Not found'

        classification = classify_difference(
            field, value1, value2
        )

        if classification['status'] == 'Match':
            continue

        mismatches.append({
            'field': field,
            'document1_value': value1,
            'document2_value': value2,
            'status': classification['status'],
            'reason': classification['reason'],
            'recommendation': classification['recommendation'],
        })

    return mismatches


def compare_documents(request):
    result = None
    error = None

    if request.method == 'POST':
        request.session.pop('comparison_report', None)

        file1 = request.FILES.get('document1')
        file2 = request.FILES.get('document2')

        if not file1 or not file2:
            error = 'Please upload both PDF documents.'

        elif (
            not file1.name.lower().endswith('.pdf')
            or not file2.name.lower().endswith('.pdf')
        ):
            error = 'Please upload PDF files only.'

        elif (
            file1.size > 10 * 1024 * 1024
            or file2.size > 10 * 1024 * 1024
        ):
            error = 'Each PDF must be smaller than 10 MB.'

        else:
            try:
                reader1 = PdfReader(file1)
                reader2 = PdfReader(file2)

                if reader1.is_encrypted and not reader1.decrypt(''):
                    error = 'Document 1 is password-protected.'

                if not error and reader2.is_encrypted:
                    if not reader2.decrypt(''):
                        error = 'Document 2 is password-protected.'

                if not error:
                    text1 = '\n'.join(
                        page.extract_text() or ''
                        for page in reader1.pages
                    )

                    text2 = '\n'.join(
                        page.extract_text() or ''
                        for page in reader2.pages
                    )

                    if not text1.strip() or not text2.strip():
                        error = (
                            'Text could not be extracted from one or both '
                            'PDFs. Scanned documents may require OCR.'
                        )

                    else:
                        lines1 = {
                            line.strip()
                            for line in text1.splitlines()
                            if line.strip()
                        }

                        lines2 = {
                            line.strip()
                            for line in text2.splitlines()
                            if line.strip()
                        }

                        only_first = sorted(lines1 - lines2)
                        only_second = sorted(lines2 - lines1)

                        fields1 = extract_fields(text1)
                        fields2 = extract_fields(text2)

                        field_mismatches = compare_fields(
                            fields1, fields2
                        )

                        result = {
                            'only_in_first': only_first,
                            'only_in_second': only_second,
                            'count_first': len(only_first),
                            'count_second': len(only_second),
                            'document1_name': file1.name,
                            'document2_name': file2.name,
                            'fields1': fields1,
                            'fields2': fields2,
                            'field_mismatches': field_mismatches,
                            'field_mismatch_count': len(field_mismatches),
                        }

                        DocumentComparison.objects.create(
                            document1_name=file1.name[:255],
                            document2_name=file2.name[:255],
                            count_first=len(only_first),
                            count_second=len(only_second),
                        )

                        request.session['comparison_report'] = result

            except Exception:
                error = (
                    'Unable to read these PDFs. Please check that both '
                    'files are valid PDF documents.'
                )

    return render(
        request,
        'upload.html',
        {'result': result, 'error': error},
    )


def comparison_history(request):
    history = DocumentComparison.objects.all()[:100]

    return render(
        request,
        'history.html',
        {'history': history},
    )


def download_report(request):
    report = request.session.get('comparison_report')

    if report is None:
        return HttpResponse(
            'No comparison report available. Compare two PDFs first.',
            status=400,
        )

    buffer = BytesIO()

    pdf = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=12 * mm,
        leftMargin=12 * mm,
        topMargin=18 * mm,
        bottomMargin=20 * mm,
        title='ApplySure Comparison Report',
        author='ApplySure',
    )

    green = colors.HexColor('#183D32')
    cream = colors.HexColor('#F6F0E5')
    terracotta = colors.HexColor('#C66A45')
    light_green = colors.HexColor('#EDF5EF')
    light_terracotta = colors.HexColor('#FFF0E8')
    dark_text = colors.HexColor('#25352E')

    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        name='ReportTitle',
        parent=styles['Title'],
        fontName='Helvetica-Bold',
        fontSize=21,
        leading=27,
        textColor=green,
        alignment=TA_CENTER,
        spaceAfter=8,
    ))

    styles.add(ParagraphStyle(
        name='SectionHeading',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        textColor=green,
        spaceBefore=14,
        spaceAfter=8,
    ))

    styles.add(ParagraphStyle(
        name='ReportBody',
        parent=styles['BodyText'],
        fontName='Helvetica',
        fontSize=8,
        leading=11,
        textColor=dark_text,
        wordWrap='LTR',
    ))

    styles.add(ParagraphStyle(
        name='SmallNote',
        parent=styles['BodyText'],
        fontName='Helvetica-Oblique',
        fontSize=8,
        leading=11,
        textColor=colors.HexColor('#6E786F'),
    ))

    def safe_text(value):
        value = str(value).encode(
            'latin-1', errors='replace'
        ).decode('latin-1')

        return escape(value)

    def add_page_number(canvas_obj, document):
        canvas_obj.saveState()
        canvas_obj.setStrokeColor(cream)

        canvas_obj.line(
            12 * mm, 14 * mm, A4[0] - 12 * mm, 14 * mm
        )

        canvas_obj.setFont('Helvetica', 8)
        canvas_obj.setFillColor(green)

        canvas_obj.drawString(
            12 * mm, 9 * mm, 'ApplySure | Document Comparison'
        )

        canvas_obj.drawRightString(
            A4[0] - 12 * mm, 9 * mm, f'Page {document.page}'
        )

        canvas_obj.restoreState()

    story = [
        Paragraph('ApplySure', styles['ReportTitle']),
        Paragraph(
            'Document Comparison Report',
            styles['Heading2'],
        ),
        Spacer(1, 8),
        Paragraph(
            'Document 1: <b>{}</b>'.format(
                safe_text(report.get('document1_name', 'Document 1'))
            ),
            styles['ReportBody'],
        ),
        Spacer(1, 5),
        Paragraph(
            'Document 2: <b>{}</b>'.format(
                safe_text(report.get('document2_name', 'Document 2'))
            ),
            styles['ReportBody'],
        ),
        Spacer(1, 14),
    ]

    summary_data = [
        [
            Paragraph('<b>Comparison summary</b>', styles['ReportBody']),
            Paragraph('<b>Count</b>', styles['ReportBody']),
        ],
        [
            Paragraph('Lines only in Document 1', styles['ReportBody']),
            str(report['count_first']),
        ],
        [
            Paragraph('Lines only in Document 2', styles['ReportBody']),
            str(report['count_second']),
        ],
        [
            Paragraph('Flagged field differences', styles['ReportBody']),
            str(report.get('field_mismatch_count', 0)),
        ],
    ]

    summary_table = Table(
        summary_data,
        colWidths=[125 * mm, 40 * mm],
        repeatRows=1,
    )

    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), green),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('BACKGROUND', (0, 1), (-1, 2), cream),
        ('BACKGROUND', (0, 3), (-1, 3), light_green),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.white),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
    ]))

    story.append(summary_table)

    story.append(
        Paragraph(
            'Smart Field Difference Analysis',
            styles['SectionHeading'],
        )
    )

    mismatches = report.get('field_mismatches', [])

    if mismatches:
        mismatch_data = [[
            Paragraph('<b>Field</b>', styles['ReportBody']),
            Paragraph('<b>Document 1</b>', styles['ReportBody']),
            Paragraph('<b>Document 2</b>', styles['ReportBody']),
            Paragraph('<b>Classification</b>', styles['ReportBody']),
            Paragraph('<b>Reason / Recommendation</b>', styles['ReportBody']),
        ]]

        for item in mismatches:
            reason = (
                safe_text(item.get('reason', ''))
                + '<br/><br/><b>Next:</b> '
                + safe_text(item.get('recommendation', ''))
            )

            mismatch_data.append([
                Paragraph(safe_text(item['field']), styles['ReportBody']),
                Paragraph(
                    safe_text(item['document1_value']),
                    styles['ReportBody'],
                ),
                Paragraph(
                    safe_text(item['document2_value']),
                    styles['ReportBody'],
                ),
                Paragraph(safe_text(item['status']), styles['ReportBody']),
                Paragraph(reason, styles['ReportBody']),
            ])

        mismatch_table = Table(
            mismatch_data,
            colWidths=[22 * mm, 31 * mm, 31 * mm, 35 * mm, 46 * mm],
            repeatRows=1,
        )

        mismatch_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), green),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('BACKGROUND', (0, 1), (-1, -1), light_terracotta),
            ('GRID', (0, 0), (-1, -1), 0.4, cream),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))

        story.append(mismatch_table)

    else:
        story.append(
            Paragraph(
                'No differences were detected in the extracted fields. '
                'This does not guarantee that all document information '
                'matches.',
                styles['ReportBody'],
            )
        )

    def add_difference_section(title, lines, background):
        story.append(Paragraph(title, styles['SectionHeading']))

        if not lines:
            story.append(
                Paragraph('No unique lines found.', styles['ReportBody'])
            )
            story.append(Spacer(1, 5))
            return

        for line in lines:
            paragraph = Paragraph(
                '&#8226; {}'.format(safe_text(line)),
                styles['ReportBody'],
            )

            item = Table([[paragraph]], colWidths=[165 * mm])

            item.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), background),
                ('BOX', (0, 0), (-1, -1), 0.4, cream),
                ('LINEBEFORE', (0, 0), (0, -1), 3, terracotta),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ]))

            story.append(KeepTogether([item, Spacer(1, 4)]))

    add_difference_section(
        'Information found only in Document 1',
        report['only_in_first'],
        light_terracotta,
    )

    add_difference_section(
        'Information found only in Document 2',
        report['only_in_second'],
        light_green,
    )

    story.append(Spacer(1, 12))

    story.append(
        Paragraph(
            'Important: Classification is based on extracted text and '
            'simple comparison rules. Similar names are not necessarily '
            'incorrect, and a formatting variation is not proof of a '
            'match. Scanned PDFs may require OCR. Always verify flagged '
            'values against the original documents.',
            styles['SmallNote'],
        )
    )

    pdf.build(
        story,
        onFirstPage=add_page_number,
        onLaterPages=add_page_number,
    )

    buffer.seek(0)

    response = HttpResponse(
        buffer.getvalue(),
        content_type='application/pdf',
    )

    response['Content-Disposition'] = (
        'attachment; filename="ApplySure_Comparison_Report.pdf"'
    )

    return response
