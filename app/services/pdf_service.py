"""
PDF Export Service - Generate professional diagnosis reports
"""
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfgen import canvas
from datetime import datetime
import io
from typing import Dict, Any
from app.core.logging import get_logger
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
import os

logger = get_logger(__name__)


class PDFService:
    """Generate PDF reports for diagnoses."""
    
    def generate_diagnosis_report(
        self,
        diagnosis: Dict[str, Any],
        patient: Dict[str, Any],
        doctor: Dict[str, Any]
    ) -> bytes:
        """Generate professional PDF diagnosis report."""
        try:
            buffer = io.BytesIO()
            doc = SimpleDocTemplate(
                buffer,
                pagesize=letter,
                rightMargin=0.75*inch,
                leftMargin=0.75*inch,
                topMargin=1*inch,
                bottomMargin=1*inch,
            )
            
            # Container for PDF elements
            elements = []
            
            # Styles
            styles = getSampleStyleSheet()
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=24,
                textColor=colors.HexColor('#1e40af'),
                spaceAfter=30,
                alignment=TA_CENTER,
            )
            heading_style = ParagraphStyle(
                'CustomHeading',
                parent=styles['Heading2'],
                fontSize=14,
                textColor=colors.HexColor('#1e40af'),
                spaceAfter=12,
                spaceBefore=12,
            )
            
            # Header/Letterhead
            elements.append(Paragraph("CLINICAL DIAGNOSIS REPORT", title_style))
            elements.append(Spacer(1, 0.2*inch))
            
            # Hospital/Clinic Info
            header_data = [
                ["Clinical Decision Support System", ""],
                ["AI-Powered Diagnostic Analysis", f"Report Date: {datetime.now().strftime('%B %d, %Y')}"],
                ["", f"Report Time: {datetime.now().strftime('%I:%M %p')}"],
            ]
            header_table = Table(header_data, colWidths=[4*inch, 2.5*inch])
            header_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#1e40af')),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ]))
            elements.append(header_table)
            elements.append(Spacer(1, 0.3*inch))
            
            # Patient Information
            elements.append(Paragraph("PATIENT INFORMATION", heading_style))
            patient_data = [
                ["Patient Name:", patient.get('full_name', 'N/A'), "MRN:", patient.get('mrn', 'N/A')],
                ["Date of Birth:", patient.get('date_of_birth', 'N/A'), "Gender:", patient.get('gender', 'N/A')],
                ["Age:", f"{self._calculate_age(patient.get('date_of_birth', ''))} years", "Blood Group:", patient.get('blood_group', 'N/A')],
            ]
            if patient.get('allergies'):
                patient_data.append(["Allergies:", ", ".join(patient['allergies']), "", ""])
            
            patient_table = Table(patient_data, colWidths=[1.2*inch, 2.3*inch, 1*inch, 2*inch])
            patient_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f3f4f6')),
                ('BACKGROUND', (2, 0), (2, -1), colors.HexColor('#f3f4f6')),
                ('PADDING', (0, 0), (-1, -1), 8),
            ]))
            elements.append(patient_table)
            elements.append(Spacer(1, 0.3*inch))
            
            # Chief Complaint
            elements.append(Paragraph("CHIEF COMPLAINT", heading_style))
            elements.append(Paragraph(diagnosis.get('chief_complaint', 'N/A'), styles['Normal']))
            elements.append(Spacer(1, 0.2*inch))
            
            # Symptoms
            if diagnosis.get('symptoms'):
                elements.append(Paragraph("PRESENTING SYMPTOMS", heading_style))
                symptom_data = [["Symptom", "Severity", "Duration", "Notes"]]
                for symptom in diagnosis['symptoms']:
                    symptom_data.append([
                        symptom.get('name', ''),
                        symptom.get('severity', 'N/A'),
                        symptom.get('duration', 'N/A'),
                        symptom.get('notes', '')[:30] if symptom.get('notes') else ''
                    ])
                
                symptom_table = Table(symptom_data, colWidths=[2*inch, 1.2*inch, 1.2*inch, 2.1*inch])
                symptom_table.setStyle(TableStyle([
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 10),
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e40af')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9fafb')]),
                    ('PADDING', (0, 0), (-1, -1), 8),
                ]))
                elements.append(symptom_table)
                elements.append(Spacer(1, 0.2*inch))
            
            # Lab Results
            if diagnosis.get('lab_results_parsed'):
                elements.append(Paragraph("LABORATORY RESULTS", heading_style))
                lab_data = [["Test", "Value", "Unit", "Reference Range", "Status"]]
                
                for test_key, test_data in diagnosis['lab_results_parsed'].items():
                    status = "NORMAL"
                    if diagnosis.get('lab_abnormalities'):
                        for abnormality in diagnosis['lab_abnormalities']:
                            if abnormality['test'] == test_data['name']:
                                status = f"{abnormality['status']} ({abnormality['severity']})"
                                break
                    
                    ref_range = f"{test_data['reference_range']['min']}-{test_data['reference_range']['max']}"
                    lab_data.append([
                        test_data['name'],
                        str(test_data['value']),
                        test_data['unit'],
                        ref_range,
                        status
                    ])
                
                lab_table = Table(lab_data, colWidths=[2*inch, 0.8*inch, 0.8*inch, 1.4*inch, 1.5*inch])
                lab_table.setStyle(TableStyle([
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e40af')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9fafb')]),
                    ('PADDING', (0, 0), (-1, -1), 6),
                ]))
                elements.append(lab_table)
                elements.append(Spacer(1, 0.3*inch))
            
            # Page Break before diagnoses
            elements.append(PageBreak())
            
            # Differential Diagnoses
            elements.append(Paragraph("DIFFERENTIAL DIAGNOSES", heading_style))
            
            for idx, dx in enumerate(diagnosis.get('differential_diagnoses', [])[:5], 1):
                # Diagnosis header
                dx_title = f"{idx}. {dx.get('diagnosis', 'N/A')} - {int(dx.get('confidence', 0) * 100)}% Confidence"
                elements.append(Paragraph(dx_title, ParagraphStyle(
                    'DxTitle',
                    parent=styles['Heading3'],
                    fontSize=12,
                    textColor=colors.HexColor('#1e40af'),
                    spaceAfter=6,
                )))
                
                # ICD-10 Code
                elements.append(Paragraph(f"<b>ICD-10 Code:</b> {dx.get('icd10_code', 'N/A')}", styles['Normal']))
                elements.append(Spacer(1, 0.1*inch))
                
                # Clinical Reasoning
                elements.append(Paragraph("<b>Clinical Reasoning:</b>", styles['Normal']))
                elements.append(Paragraph(dx.get('reasoning', 'N/A'), styles['Normal']))
                elements.append(Spacer(1, 0.1*inch))
                
                # Supporting Evidence
                if dx.get('supporting_evidence'):
                    elements.append(Paragraph("<b>Supporting Evidence:</b>", styles['Normal']))
                    for evidence in dx['supporting_evidence']:
                        elements.append(Paragraph(f"• {evidence}", styles['Normal']))
                    elements.append(Spacer(1, 0.1*inch))
                
                elements.append(Spacer(1, 0.2*inch))
            
            # Clinical Reasoning
            elements.append(Paragraph("OVERALL CLINICAL REASONING", heading_style))
            elements.append(Paragraph(diagnosis.get('clinical_reasoning', 'N/A'), styles['Normal']))
            elements.append(Spacer(1, 0.2*inch))
            
            # Recommended Tests
            if diagnosis.get('recommended_tests'):
                elements.append(Paragraph("RECOMMENDED DIAGNOSTIC TESTS", heading_style))
                for test in diagnosis['recommended_tests']:
                    elements.append(Paragraph(f"• {test}", styles['Normal']))
                elements.append(Spacer(1, 0.2*inch))
            
            # Recommended Treatments
            if diagnosis.get('recommended_treatments'):
                elements.append(Paragraph("RECOMMENDED TREATMENTS", heading_style))
                for treatment in diagnosis['recommended_treatments']:
                    elements.append(Paragraph(f"• {treatment}", styles['Normal']))
                elements.append(Spacer(1, 0.2*inch))
            
            # Red Flags
            if diagnosis.get('red_flags'):
                elements.append(Paragraph("⚠️ RED FLAGS / URGENT WARNINGS", heading_style))
                for flag in diagnosis['red_flags']:
                    elements.append(Paragraph(f"• {flag}", ParagraphStyle(
                        'RedFlag',
                        parent=styles['Normal'],
                        textColor=colors.red,
                    )))
                elements.append(Spacer(1, 0.2*inch))
            
            # Follow-up
            if diagnosis.get('follow_up_instructions'):
                elements.append(Paragraph("FOLLOW-UP INSTRUCTIONS", heading_style))
                elements.append(Paragraph(diagnosis['follow_up_instructions'], styles['Normal']))
                elements.append(Spacer(1, 0.3*inch))
            
            # Page Break before signatures
            elements.append(PageBreak())
            
            # Evidence Summary
            if diagnosis.get('rag_enabled'):
                elements.append(Paragraph("EVIDENCE-BASED ANALYSIS", heading_style))
                elements.append(Paragraph(
                    f"This diagnosis was generated using {diagnosis.get('citation_count', 0)} "
                    f"medical literature citations from PubMed and clinical guidelines.",
                    styles['Normal']
                ))
                elements.append(Spacer(1, 0.3*inch))
            
            # Signature Section
            elements.append(Spacer(1, 0.5*inch))
            sig_data = [
                ["", ""],
                ["_" * 40, "_" * 40],
                [f"Reviewing Physician: {doctor.get('full_name', 'N/A')}", f"Date: {datetime.now().strftime('%B %d, %Y')}"],
                [f"License: {doctor.get('license_number', 'N/A')}", f"Signature"],
            ]
            sig_table = Table(sig_data, colWidths=[3.25*inch, 3.25*inch])
            sig_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]))
            elements.append(sig_table)
            
            # Disclaimer
            elements.append(Spacer(1, 0.5*inch))
            disclaimer = """
            <b>DISCLAIMER:</b> This report is generated by an AI-powered Clinical Decision Support System 
            and should be used as a supplementary tool only. Final diagnostic and treatment decisions 
            must be made by licensed healthcare professionals based on clinical judgment, patient history, 
            physical examination, and additional diagnostic testing as appropriate.
            """
            elements.append(Paragraph(disclaimer, ParagraphStyle(
                'Disclaimer',
                parent=styles['Normal'],
                fontSize=8,
                textColor=colors.grey,
                alignment=TA_CENTER,
            )))
            
            # Build PDF
            doc.build(elements, onFirstPage=self._add_footer, onLaterPages=self._add_footer)
            
            pdf_bytes = buffer.getvalue()
            buffer.close()
            
            logger.info("pdf_generated", size_bytes=len(pdf_bytes))
            return pdf_bytes
            
        except Exception as e:
            logger.error("pdf_generation_error", error=str(e))
            raise
    
    def _add_footer(self, canvas, doc):
        """Add footer to each page."""
        canvas.saveState()
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(colors.grey)
        
        # Page number
        page_num = canvas.getPageNumber()
        text = f"Page {page_num}"
        canvas.drawRightString(7.5*inch, 0.5*inch, text)
        
        # Footer text
        canvas.drawString(0.75*inch, 0.5*inch, "Clinical Decision Support System - Confidential Medical Report")
        
        canvas.restoreState()
    
    def _calculate_age(self, dob_str: str) -> int:
        """Calculate age from date of birth."""
        try:
            from datetime import datetime
            dob = datetime.strptime(dob_str, "%Y-%m-%d")
            today = datetime.now()
            return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        except:
            return 0

    def email_diagnosis_report(
            self,
            pdf_bytes: bytes,
            recipient_email: str,
            patient_name: str,
            doctor_name: str) -> bool:
        """Email PDF report."""
        try:
            # Email configuration (add to .env)
            smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
            smtp_port = int(os.getenv("SMTP_PORT", "587"))
            sender_email = os.getenv("SENDER_EMAIL")
            sender_password = os.getenv("SENDER_PASSWORD")
            
            msg = MIMEMultipart()
            msg['From'] = sender_email
            msg['To'] = recipient_email
            msg['Subject'] = f"Diagnosis Report - {patient_name}"
            
            body = f"""
            Dear Colleague,
            
            Please find attached the diagnosis report for patient {patient_name}.
            
            This report was generated by {doctor_name} using our Clinical Decision Support System.
            
            Best regards,
            Clinical Team
            """
        
            msg.attach(MIMEText(body, 'plain'))
            
            # Attach PDF
            pdf_attachment = MIMEApplication(pdf_bytes, _subtype="pdf")
            pdf_attachment.add_header('Content-Disposition', 'attachment', 
                                    filename=f'diagnosis_report_{patient_name}.pdf')
            msg.attach(pdf_attachment)
            
            # Send email
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(sender_email, sender_password)
                server.send_message(msg)
            
            logger.info("email_sent", recipient=recipient_email)
            return True
        
        except Exception as e:
            logger.error("email_error", error=str(e))
            return False

# Global instance
pdf_service = PDFService()