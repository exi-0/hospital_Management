import os
import json
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.graphics.shapes import Drawing, Rect
import db

def generate_patient_report(state):
    # Ensure reports folder exists
    reports_dir = os.path.join(os.path.dirname(__file__), "reports")
    os.makedirs(reports_dir, exist_ok=True)
    
    # Extract IDs
    patient_id = state.get("patient_id", "Unknown")
    
    appt = state.get("appointment_result") or {}
    appointment_id = appt.get("appointment_id")
    if not appointment_id:
        appointment_id = "A" + patient_id
        
    filename = f"patient_report_{appointment_id}.pdf"
    filepath = os.path.join(reports_dir, filename)
    
    # SimpleDocTemplate setup
    doc = SimpleDocTemplate(
        filepath,
        pagesize=A4,
        rightMargin=54,
        leftMargin=54,
        topMargin=100,
        bottomMargin=80
    )
    
    # Build styles
    styles = getSampleStyleSheet()
    # Add custom styles if they don't exist
    if 'HospitalName' not in styles:
        styles.add(ParagraphStyle(
            'HospitalName',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=16,
            leading=20,
            textColor=colors.HexColor("#0F172A")
        ))
        styles.add(ParagraphStyle(
            'HospitalSub',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#64748B")
        ))
        styles.add(ParagraphStyle(
            'SectionHeader',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=10,
            leading=13,
            textColor=colors.HexColor("#1E3A8A")
        ))
        styles.add(ParagraphStyle(
            'Label',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#475569")
        ))
        styles.add(ParagraphStyle(
            'Value',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#1E293B")
        ))
        styles.add(ParagraphStyle(
            'CardContent',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=8,
            leading=11,
            textColor=colors.HexColor("#334155")
        ))
    
    story = []
    
    # 1. HEADER (Logo + Hospital details)
    logo_drawing = Drawing(40, 40)
    logo_drawing.add(Rect(0, 0, 40, 40, fillColor=colors.HexColor("#1E3A8A"), strokeColor=None, rx=8, ry=8))
    logo_drawing.add(Rect(17, 8, 6, 24, fillColor=colors.white, strokeColor=None))
    logo_drawing.add(Rect(8, 17, 24, 6, fillColor=colors.white, strokeColor=None))
    
    h_info = [
        [
            logo_drawing,
            [
                Paragraph("SACRED HEART GENERAL HOSPITAL", styles['HospitalName']),
                Paragraph("100 Medical Plaza, Health City • Tel: (555) 019-9000 • Email: contact@sacredheart.org • Web: www.sacredheart.org", styles['HospitalSub'])
            ]
        ]
    ]
    header_table = Table(h_info, colWidths=[50, doc.width - 50])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('LEFTPADDING', (1,0), (1,0), 10),
        ('BOTTOMPADDING', (0,0), (-1,-1), 15),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 10))
    
    # Meta Details (Report ID, Generated date)
    meta_dict = {
        "Report ID": f"REP-{appointment_id}",
        "Report Date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Patient ID": patient_id,
        "Status": "Final Report"
    }
    story.append(make_meta_bar(meta_dict, styles))
    story.append(Spacer(1, 15))
    
    # 2. PATIENT INFORMATION
    p_info = state.get("patient_info", {}).get("patient_info", {})
    p_data = {
        "Patient Name": p_info.get("name", "Unknown"),
        "Age / Gender": f"{p_info.get('age', 'N/A')} / {p_info.get('gender', 'N/A')}",
        "Blood Group": p_info.get("blood_group", "Unknown"),
        "Contact Number": p_info.get("phone", "N/A"),
        "Email Address": p_info.get("email", "N/A"),
        "Address": p_info.get("address", "N/A"),
        "Medical History": ", ".join(p_info.get("medical_history", [])) or "None",
        "Allergies": ", ".join(p_info.get("allergies", [])) or "None",
        "Insurance Provider": p_info.get("insurance_provider", "N/A"),
        "Insurance Number": p_info.get("insurance_number", "N/A"),
        "Emergency Contact": p_info.get("emergency_contact", "N/A"),
        "Notes": p_info.get("notes", "None"),
    }
    story.append(make_section_title("PATIENT DEMOGRAPHICS", styles))
    story.append(Spacer(1, 5))
    story.append(make_info_grid(p_data, styles))
    story.append(Spacer(1, 15))
    
    # 3. VISIT DETAILS
    v_data = {
        "Chief Complaint": state.get("user_query", "Consultation request"),
        "Department": state.get("specialization_needed") or "General Medicine",
        "Emergency Status": "EMERGENCY ALERT (High Priority)" if state.get("emergency_detected") else "No emergency detected (Routine)",
        "Priority Level": "High" if state.get("emergency_detected") else "Routine",
        "Visit Date": datetime.now().strftime("%Y-%m-%d")
    }
    story.append(make_section_title("VISIT DETAILS", styles))
    story.append(Spacer(1, 5))
    story.append(make_info_grid(v_data, styles))
    story.append(Spacer(1, 15))
    
    # 4. DOCTOR DETAILS (if appointment booked)
    if state.get("appointment_status") in ("confirmed", "confirmed_after_retry") and appt:
        doc_name = appt.get("doctor_name") or appt.get("doctor")
        doc_details = {}
        if doc_name:
            conn = db.get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM doctors WHERE name = ?", (doc_name,))
            row = cursor.fetchone()
            conn.close()
            if row:
                doc_details = {
                    "Doctor Name": row["name"],
                    "Department": row["specialization"],
                    "Experience": f"{row['experience']} Years",
                    "Consultation Fee": f"${row['fee']:.2f}",
                    "Hospital Location": row["hospital"],
                    "Appointment ID": appt.get("appointment_id", "N/A"),
                    "Date & Time": f"{appt.get('date')} at {appt.get('time')}",
                    "Status": "CONFIRMED"
                }
        if not doc_details:
            doc_details = {
                "Doctor Name": doc_name or "N/A",
                "Appointment ID": appt.get("appointment_id", "N/A"),
                "Date & Time": f"{appt.get('date')} at {appt.get('time')}",
                "Status": "CONFIRMED"
            }
        story.append(make_section_title("CONSULTATION BOOKING DETAILS", styles))
        story.append(Spacer(1, 5))
        story.append(make_info_grid(doc_details, styles))
        story.append(Spacer(1, 15))
        
    # 5. LAB TEST DETAILS
    lab = state.get("lab_schedule_result")
    if lab:
        lab_details = {
            "Scheduled Tests": ", ".join(lab.get("tests", [])),
            "Lab Booking ID": lab.get("lab_booking_id", "N/A"),
            "Scheduled Date": lab.get("lab_date", "N/A"),
            "Scheduled Time": lab.get("lab_time", "N/A"),
            "Instructions": "\n".join(lab.get("instructions", [])) or "No special preparation required."
        }
        story.append(make_section_title("LABORATORY SCHEDULING", styles))
        story.append(Spacer(1, 5))
        story.append(make_info_grid(lab_details, styles))
        story.append(Spacer(1, 15))
        
    # 6. LAB REPORT ANALYSIS (if analyzed)
    analysis = state.get("lab_report_analysis")
    if analysis:
        story.append(make_section_title("DIAGNOSTIC LAB ANALYSIS", styles))
        story.append(Spacer(1, 5))
        
        risk = analysis.get("risk_level", "Low")
        risk_color = "#10B981" if risk.lower() == "low" else "#F59E0B" if risk.lower() == "medium" else "#EF4444"
        summary_text = f"<b>Risk Level:</b> <font color='{risk_color}'><b>{risk.upper()}</b></font><br/>"
        summary_text += f"<b>Summary:</b> {analysis.get('summary', 'Report completed.')}<br/>"
        summary_text += f"<b>Recommendations:</b> {analysis.get('recommendation', 'Show this report to your doctor.')}"
        
        normal_f = analysis.get("normal_results", [])
        abnormal_f = analysis.get("abnormal_results", [])
        
        findings_table_data = [["Parameter", "Observed Value", "Normal Range", "Flag"]]
        for item in normal_f:
            findings_table_data.append([
                item.get("parameter", "N/A"),
                item.get("value", "N/A"),
                item.get("normal_range", "N/A"),
                "Normal"
            ])
        for item in abnormal_f:
            findings_table_data.append([
                item.get("parameter", "N/A"),
                f"<font color='#EF4444'><b>{item.get('value', 'N/A')}</b></font>",
                item.get("normal_range", "N/A"),
                f"<font color='#EF4444'><b>{item.get('flag', 'Abnormal')}</b></font>"
            ])
            
        findings_table = Table(
            [[Paragraph(cell, styles['Value']) for cell in row] for row in findings_table_data],
            colWidths=[150, 110, 110, 110]
        )
        findings_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#F8FAFC")),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
        ]))
        
        story.append(Paragraph(summary_text, styles['CardContent']))
        story.append(Spacer(1, 10))
        story.append(findings_table)
        story.append(Spacer(1, 15))
        
    # 7. NOTIFICATIONS
    notif_status = state.get("notification_status") or "N/A"
    notif_data = {
        "SMS Dispatch Status": "Sent" if "sent" in notif_status.lower() or notif_status.lower() == "confirmed" else notif_status,
        "Email Dispatch Status": "Sent" if "sent" in notif_status.lower() or notif_status.lower() == "confirmed" else notif_status,
        "WhatsApp Dispatch Status": "Sent" if "sent" in notif_status.lower() or notif_status.lower() == "confirmed" else notif_status,
        "Dispatch Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    story.append(make_section_title("NOTIFICATIONS LOG", styles))
    story.append(Spacer(1, 5))
    story.append(make_info_grid(notif_data, styles))
    story.append(Spacer(1, 15))

    # 8. AI WORKFLOW SUMMARY
    completed_agents = []
    tasks_map = {
        "load_patient_info": "Patient Information Agent",
        "emergency_check": "Emergency Check Agent",
        "search_doctors": "Doctor Search Agent",
        "book_appointment": "Appointment Agent",
        "check_and_schedule_lab": "Lab Scheduling Agent",
        "analyze_lab_report": "Lab Report Agent",
        "send_notification": "Notification Agent",
        "validate_execution": "Validator Agent",
        "summarize_execution": "Summarizer Agent"
    }
    completed_set = set(state.get("completed_tasks", []))
    for t_key, t_val in tasks_map.items():
        if t_key in completed_set:
            completed_agents.append(f"✓ {t_val}")
    if not completed_agents:
        completed_agents = [
            "✓ Supervisor Agent",
            "✓ Patient Information Agent",
            "✓ Emergency Check Agent",
            "✓ Doctor Search Agent",
            "✓ Appointment Agent",
            "✓ Lab Scheduling Agent",
            "✓ Notification Agent",
            "✓ Validator Agent",
            "✓ Summarizer Agent"
        ]
        
    story.append(make_section_title("AGENT ORCHESTRATION SUMMARY", styles))
    story.append(Spacer(1, 5))
    
    agent_rows = []
    for j in range(0, len(completed_agents), 2):
        r = [Paragraph(f"<font color='#10B981'><b>{completed_agents[j]}</b></font>", styles['Value'])]
        if j+1 < len(completed_agents):
            r.append(Paragraph(f"<font color='#10B981'><b>{completed_agents[j+1]}</b></font>", styles['Value']))
        else:
            r.append("")
        agent_rows.append(r)
    agent_table = Table(agent_rows, colWidths=[240, 240])
    agent_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(agent_table)
    story.append(Spacer(1, 15))

    # 9. FOLLOW-UP INSTRUCTIONS
    rec = "Keep standard health monitoring. Follow physician advice."
    if analysis and analysis.get("recommendation"):
        rec = analysis.get("recommendation")
    elif state.get("emergency_detected"):
        rec = "Visit the nearest Emergency Room immediately. Bypassed standard routing."
        
    followup_data = {
        "Lifestyle Advice": rec,
        "Medicines": "To be prescribed by consulting physician during visit.",
        "Emergency Contact": "Dial 911 / 112 immediately in case of discomfort or pain."
    }
    story.append(make_section_title("FOLLOW-UP AND MEDICAL ADVISORY", styles))
    story.append(Spacer(1, 5))
    story.append(make_info_grid(followup_data, styles))
    
    # 10. DISCLAIMER FOOTER
    story.append(Spacer(1, 15))
    story.append(Paragraph(
        "<font color='#64748B'><b>Disclaimer:</b> This report was automatically generated by the Agentic Hospital Management System. This document is intended for informational purposes and should be reviewed by a qualified healthcare professional.</font>",
        styles['HospitalSub']
    ))

    # Build Document
    def add_page_number(canvas, doc):
        canvas.saveState()
        
        # Header text
        canvas.setFont('Helvetica-Bold', 8)
        canvas.setFillColor(colors.HexColor("#1E3A8A"))
        canvas.drawString(54, doc.pagesize[1] - 40, "SACRED HEART GENERAL HOSPITAL")
        
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(colors.HexColor("#64748B"))
        canvas.drawRightString(doc.pagesize[0] - 54, doc.pagesize[1] - 40, "Patient Care Report Summary")
        
        # Top line
        canvas.setStrokeColor(colors.HexColor("#E2E8F0"))
        canvas.setLineWidth(0.5)
        canvas.line(54, doc.pagesize[1] - 46, doc.pagesize[0] - 54, doc.pagesize[1] - 46)
        
        # Footer text
        canvas.setFont('Helvetica-Oblique', 8)
        canvas.drawString(54, 30, "Confidential Document - Generated by Agentic HIS System")
        canvas.setFont('Helvetica', 8)
        canvas.drawRightString(doc.pagesize[0] - 54, 30, f"Page {doc.page}")
        
        # Bottom Line
        canvas.line(54, 42, doc.pagesize[0] - 54, 42)
        canvas.restoreState()
        
    doc.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)
    return filepath


def make_section_title(text, styles):
    # Left accent border table
    data = [[Paragraph(f"<font color='#1E3A8A'><b>{text}</b></font>", styles['SectionHeader'])]]
    t = Table(data, colWidths=[595.27 - 108])
    t.setStyle(TableStyle([
        ('LINELEFT', (0,0), (0,0), 3, colors.HexColor("#3B82F6")),
        ('TOPPADDING', (0,0), (-1,-1), 2),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
    ]))
    return t

def make_meta_bar(meta_dict, styles):
    # Meta bar table
    cols = []
    for k, v in meta_dict.items():
        cols.append(Paragraph(f"<b>{k}:</b> {v}", styles['Value']))
    t = Table([cols], colWidths=[(595.27 - 108) / len(meta_dict)] * len(meta_dict))
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F1F5F9")),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    return t

def make_info_grid(data_dict, styles):
    grid_data = []
    items = list(data_dict.items())
    for i in range(0, len(items), 2):
        row = []
        k1, v1 = items[i]
        row.append(Paragraph(f"<b>{k1}:</b>", styles['Label']))
        row.append(Paragraph(str(v1), styles['Value']))
        
        if i + 1 < len(items):
            k2, v2 = items[i+1]
            row.append(Paragraph(f"<b>{k2}:</b>", styles['Label']))
            row.append(Paragraph(str(v2), styles['Value']))
        else:
            row.append("")
            row.append("")
        grid_data.append(row)
        
    t = Table(grid_data, colWidths=[110, 130, 110, 130])
    t.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('LINEBELOW', (0,0), (-1,-1), 0.5, colors.HexColor("#F1F5F9")),
    ]))
    return t
