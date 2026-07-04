import os
import json
import sqlite3
from datetime import datetime
from typing import List, Dict, Any, Optional

DB_FILE = os.path.join(os.path.dirname(__file__), "hospital.db")

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize SQLite tables and seed them with initial data if they are empty."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Create tables
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS patients (
        patient_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        age INTEGER NOT NULL,
        gender TEXT NOT NULL,
        medical_history TEXT NOT NULL
    )
    """)

    # Migrate columns if not present
    cursor.execute("PRAGMA table_info(patients)")
    columns = [row["name"] for row in cursor.fetchall()]
    new_cols = [
        ("phone", "TEXT"),
        ("email", "TEXT"),
        ("blood_group", "TEXT"),
        ("address", "TEXT"),
        ("allergies", "TEXT"),
        ("insurance_provider", "TEXT"),
        ("insurance_number", "TEXT"),
        ("emergency_contact", "TEXT"),
        ("notes", "TEXT"),
        ("created_at", "TEXT"),
        ("updated_at", "TEXT"),
    ]
    for col_name, col_type in new_cols:
        if col_name not in columns:
            cursor.execute(f"ALTER TABLE patients ADD COLUMN {col_name} {col_type}")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS doctors (
        doctor_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        specialization TEXT NOT NULL,
        experience INTEGER NOT NULL,
        fee REAL NOT NULL,
        hospital TEXT NOT NULL,
        available_slots TEXT NOT NULL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS appointments (
        appointment_id TEXT PRIMARY KEY,
        patient_id TEXT NOT NULL,
        doctor_id TEXT NOT NULL,
        slot TEXT NOT NULL,
        status TEXT NOT NULL,
        FOREIGN KEY (patient_id) REFERENCES patients (patient_id) ON DELETE CASCADE,
        FOREIGN KEY (doctor_id) REFERENCES doctors (doctor_id) ON DELETE CASCADE
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS lab_reports (
        lab_order_id TEXT PRIMARY KEY,
        patient_id TEXT NOT NULL,
        test_name TEXT NOT NULL,
        status TEXT NOT NULL,
        FOREIGN KEY (patient_id) REFERENCES patients (patient_id) ON DELETE CASCADE
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS notifications (
        notification_id TEXT PRIMARY KEY,
        patient_id TEXT NOT NULL,
        message TEXT NOT NULL,
        channel TEXT NOT NULL,
        status TEXT NOT NULL,
        sent_at TEXT NOT NULL,
        FOREIGN KEY (patient_id) REFERENCES patients (patient_id) ON DELETE CASCADE
    )
    """)

    conn.commit()

    # Seed data
    # 1. Patients
    cursor.execute("SELECT COUNT(*) FROM patients")
    if cursor.fetchone()[0] == 0:
        patients_json_path = os.path.join(os.path.dirname(__file__), "patients.json")
        if os.path.exists(patients_json_path):
            with open(patients_json_path, "r") as f:
                patients = json.load(f)
                for p in patients:
                    cursor.execute(
                        """
                        INSERT INTO patients (
                            patient_id, name, age, gender, medical_history,
                            phone, email, blood_group, address, allergies,
                            insurance_provider, insurance_number, emergency_contact, notes,
                            created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            p["patient_id"], p["name"], p["age"], p["gender"], json.dumps(p["medical_history"]),
                            p.get("phone", ""), p.get("email", ""), p.get("blood_group", ""), p.get("address", ""), json.dumps(p.get("allergies", [])),
                            p.get("insurance_provider", ""), p.get("insurance_number", ""), p.get("emergency_contact", ""), p.get("notes", ""),
                            datetime.now().isoformat(), datetime.now().isoformat()
                        )
                    )
            conn.commit()

    # 2. Doctors
    cursor.execute("SELECT COUNT(*) FROM doctors")
    if cursor.fetchone()[0] == 0:
        doctors_json_path = os.path.join(os.path.dirname(__file__), "doctors.json")
        if os.path.exists(doctors_json_path):
            with open(doctors_json_path, "r") as f:
                doctors = json.load(f)
                for d in doctors:
                    cursor.execute(
                        "INSERT INTO doctors VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (d["doctor_id"], d["name"], d["specialization"], d["experience"], d["fee"], d["hospital"], json.dumps(d["available_slots"]))
                    )
            conn.commit()

    # 3. Appointments
    cursor.execute("SELECT COUNT(*) FROM appointments")
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            "INSERT INTO appointments VALUES (?, ?, ?, ?, ?)",
            ("A101", "P001", "D101", "2026-07-10 09:00", "confirmed")
        )
        # Also remove this slot from doctor's available slots in DB
        cursor.execute("SELECT available_slots FROM doctors WHERE doctor_id = ?", ("D101",))
        row = cursor.fetchone()
        if row:
            slots = json.loads(row["available_slots"])
            if "2026-07-10 09:00" in slots:
                slots.remove("2026-07-10 09:00")
                cursor.execute(
                    "UPDATE doctors SET available_slots = ? WHERE doctor_id = ?",
                    (json.dumps(slots), "D101")
                )
        conn.commit()

    # 4. Lab Reports
    cursor.execute("SELECT COUNT(*) FROM lab_reports")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO lab_reports VALUES (?, ?, ?, ?)", ("L101", "P001", "ECG", "Completed"))
        cursor.execute("INSERT INTO lab_reports VALUES (?, ?, ?, ?)", ("L102", "P001", "Blood Test", "Completed"))
        conn.commit()

    # 5. Notifications
    cursor.execute("SELECT COUNT(*) FROM notifications")
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            "INSERT INTO notifications VALUES (?, ?, ?, ?, ?, ?)",
            ("N101", "P001", "Welcome to the hospital! Your profile is set up.", "SMS+Email", "sent", "2026-07-04T10:00:00")
        )
        cursor.execute(
            "INSERT INTO notifications VALUES (?, ?, ?, ?, ?, ?)",
            ("N102", "P001", "Appointment A101 with Dr. Sarah Brown is confirmed for 2026-07-10 09:00.", "SMS+Email", "sent", "2026-07-04T12:00:00")
        )
        conn.commit()

    conn.close()

# ----------------- Helper functions for ID Generation -----------------

def get_next_id(table_name: str, prefix: str) -> str:
    conn = get_db_connection()
    cursor = conn.cursor()
    id_col = {
        "appointments": "appointment_id",
        "lab_reports": "lab_order_id",
        "notifications": "notification_id",
        "patients": "patient_id",
        "doctors": "doctor_id"
    }.get(table_name, "id")
    
    cursor.execute(f"SELECT {id_col} FROM {table_name}")
    rows = cursor.fetchall()
    conn.close()
    
    max_num = 0
    for row in rows:
        val = row[0]
        if val.startswith(prefix):
            try:
                num = int(val[len(prefix):])
                if num > max_num:
                    max_num = num
            except ValueError:
                pass
    return f"{prefix}{max_num + 1}"

# ----------------- Patients CRUD -----------------

def get_all_patients() -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM patients")
    rows = cursor.fetchall()
    conn.close()
    
    result = []
    for r in rows:
        keys = r.keys()
        result.append({
            "patient_id": r["patient_id"],
            "name": r["name"],
            "age": r["age"],
            "gender": r["gender"],
            "phone": r["phone"] if "phone" in keys else "",
            "email": r["email"] if "email" in keys else "",
            "blood_group": r["blood_group"] if "blood_group" in keys else "Unknown",
            "address": r["address"] if "address" in keys else "",
            "medical_history": json.loads(r["medical_history"]) if r["medical_history"] else [],
            "allergies": json.loads(r["allergies"]) if "allergies" in keys and r["allergies"] else [],
            "insurance_provider": r["insurance_provider"] if "insurance_provider" in keys else "",
            "insurance_number": r["insurance_number"] if "insurance_number" in keys else "",
            "emergency_contact": r["emergency_contact"] if "emergency_contact" in keys else "",
            "notes": r["notes"] if "notes" in keys else "",
            "created_at": r["created_at"] if "created_at" in keys else "",
            "updated_at": r["updated_at"] if "updated_at" in keys else "",
        })
    return result

def get_patient(patient_id: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM patients WHERE patient_id = ?", (patient_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    keys = row.keys()
    return {
        "patient_id": row["patient_id"],
        "name": row["name"],
        "age": row["age"],
        "gender": row["gender"],
        "phone": row["phone"] if "phone" in keys else "",
        "email": row["email"] if "email" in keys else "",
        "blood_group": row["blood_group"] if "blood_group" in keys else "Unknown",
        "address": row["address"] if "address" in keys else "",
        "medical_history": json.loads(row["medical_history"]) if row["medical_history"] else [],
        "allergies": json.loads(row["allergies"]) if "allergies" in keys and row["allergies"] else [],
        "insurance_provider": row["insurance_provider"] if "insurance_provider" in keys else "",
        "insurance_number": row["insurance_number"] if "insurance_number" in keys else "",
        "emergency_contact": row["emergency_contact"] if "emergency_contact" in keys else "",
        "notes": row["notes"] if "notes" in keys else "",
        "created_at": row["created_at"] if "created_at" in keys else "",
        "updated_at": row["updated_at"] if "updated_at" in keys else "",
    }

def create_patient(
    patient_id: str,
    name: str,
    age: int,
    gender: str,
    medical_history: List[str],
    phone: str = "",
    email: str = "",
    blood_group: str = "Unknown",
    address: str = "",
    allergies: List[str] = [],
    insurance_provider: str = "",
    insurance_number: str = "",
    emergency_contact: str = "",
    notes: str = "",
    created_at: Optional[str] = None,
    updated_at: Optional[str] = None,
) -> Dict[str, Any]:
    if not created_at:
        created_at = datetime.now().isoformat()
    if not updated_at:
        updated_at = datetime.now().isoformat()
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("PRAGMA table_info(patients)")
    columns = [r["name"] for r in cursor.fetchall()]
    
    if "phone" in columns:
        cursor.execute(
            """INSERT INTO patients (
                patient_id, name, age, gender, medical_history,
                phone, email, blood_group, address, allergies,
                insurance_provider, insurance_number, emergency_contact, notes,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                patient_id, name, age, gender, json.dumps(medical_history),
                phone, email, blood_group, address, json.dumps(allergies),
                insurance_provider, insurance_number, emergency_contact, notes,
                created_at, updated_at
            )
        )
    else:
        cursor.execute(
            "INSERT INTO patients VALUES (?, ?, ?, ?, ?)",
            (patient_id, name, age, gender, json.dumps(medical_history))
        )
        
    conn.commit()
    conn.close()
    return {
        "patient_id": patient_id, "name": name, "age": age, "gender": gender,
        "medical_history": medical_history, "phone": phone, "email": email,
        "blood_group": blood_group, "address": address, "allergies": allergies,
        "insurance_provider": insurance_provider, "insurance_number": insurance_number,
        "emergency_contact": emergency_contact, "notes": notes,
        "created_at": created_at, "updated_at": updated_at
    }

def update_patient(
    patient_id: str,
    name: str,
    age: int,
    gender: str,
    medical_history: List[str],
    phone: str = "",
    email: str = "",
    blood_group: str = "Unknown",
    address: str = "",
    allergies: List[str] = [],
    insurance_provider: str = "",
    insurance_number: str = "",
    emergency_contact: str = "",
    notes: str = "",
    updated_at: Optional[str] = None,
) -> bool:
    if not updated_at:
        updated_at = datetime.now().isoformat()
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("PRAGMA table_info(patients)")
    columns = [r["name"] for r in cursor.fetchall()]
    
    if "phone" in columns:
        cursor.execute(
            """UPDATE patients SET 
                name = ?, age = ?, gender = ?, medical_history = ?,
                phone = ?, email = ?, blood_group = ?, address = ?, allergies = ?,
                insurance_provider = ?, insurance_number = ?, emergency_contact = ?, notes = ?,
                updated_at = ?
             WHERE patient_id = ?""",
            (
                name, age, gender, json.dumps(medical_history),
                phone, email, blood_group, address, json.dumps(allergies),
                insurance_provider, insurance_number, emergency_contact, notes,
                updated_at, patient_id
            )
        )
    else:
        cursor.execute(
            "UPDATE patients SET name = ?, age = ?, gender = ?, medical_history = ? WHERE patient_id = ?",
            (name, age, gender, json.dumps(medical_history), patient_id)
        )
        
    conn.commit()
    rows_changed = cursor.rowcount
    conn.close()
    return rows_changed > 0

def delete_patient(patient_id: str) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM patients WHERE patient_id = ?", (patient_id,))
    conn.commit()
    rows_changed = cursor.rowcount
    conn.close()
    return rows_changed > 0

# ----------------- Doctors CRUD -----------------

def get_all_doctors(specialization: Optional[str] = None) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    if specialization:
        cursor.execute("SELECT * FROM doctors WHERE LOWER(specialization) = LOWER(?)", (specialization,))
    else:
        cursor.execute("SELECT * FROM doctors")
    rows = cursor.fetchall()
    conn.close()
    
    result = []
    for r in rows:
        result.append({
            "doctor_id": r["doctor_id"],
            "name": r["name"],
            "specialization": r["specialization"],
            "experience": r["experience"],
            "fee": r["fee"],
            "hospital": r["hospital"],
            "available_slots": json.loads(r["available_slots"])
        })
    return result

def get_doctor(doctor_id: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM doctors WHERE doctor_id = ?", (doctor_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "doctor_id": row["doctor_id"],
        "name": row["name"],
        "specialization": row["specialization"],
        "experience": row["experience"],
        "fee": row["fee"],
        "hospital": row["hospital"],
        "available_slots": json.loads(row["available_slots"])
    }

def create_doctor(doctor_id: str, name: str, specialization: str, experience: int, fee: float, hospital: str, available_slots: List[str]) -> Dict[str, Any]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO doctors VALUES (?, ?, ?, ?, ?, ?, ?)",
        (doctor_id, name, specialization, experience, fee, hospital, json.dumps(available_slots))
    )
    conn.commit()
    conn.close()
    return {
        "doctor_id": doctor_id, "name": name, "specialization": specialization,
        "experience": experience, "fee": fee, "hospital": hospital, "available_slots": available_slots
    }

def update_doctor(doctor_id: str, name: str, specialization: str, experience: int, fee: float, hospital: str, available_slots: List[str]) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE doctors SET name = ?, specialization = ?, experience = ?, fee = ?, hospital = ?, available_slots = ? WHERE doctor_id = ?",
        (name, specialization, experience, fee, hospital, json.dumps(available_slots), doctor_id)
    )
    conn.commit()
    rows_changed = cursor.rowcount
    conn.close()
    return rows_changed > 0

def delete_doctor(doctor_id: str) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM doctors WHERE doctor_id = ?", (doctor_id,))
    conn.commit()
    rows_changed = cursor.rowcount
    conn.close()
    return rows_changed > 0

# ----------------- Appointments CRUD -----------------

def get_all_appointments() -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT a.*, p.name as patient_name, d.name as doctor_name, d.specialization as doctor_specialization
        FROM appointments a
        JOIN patients p ON a.patient_id = p.patient_id
        JOIN doctors d ON a.doctor_id = d.doctor_id
    """)
    rows = cursor.fetchall()
    conn.close()
    
    result = []
    for r in rows:
        result.append({
            "appointment_id": r["appointment_id"],
            "patient_id": r["patient_id"],
            "patient_name": r["patient_name"],
            "doctor_id": r["doctor_id"],
            "doctor_name": r["doctor_name"],
            "doctor_specialization": r["doctor_specialization"],
            "slot": r["slot"],
            "status": r["status"]
        })
    return result

def get_patient_appointments(patient_id: str) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT a.*, d.name as doctor_name, d.specialization as doctor_specialization
        FROM appointments a
        JOIN doctors d ON a.doctor_id = d.doctor_id
        WHERE a.patient_id = ?
    """, (patient_id,))
    rows = cursor.fetchall()
    conn.close()
    
    result = []
    for r in rows:
        result.append({
            "appointment_id": r["appointment_id"],
            "patient_id": r["patient_id"],
            "doctor_id": r["doctor_id"],
            "doctor_name": r["doctor_name"],
            "doctor_specialization": r["doctor_specialization"],
            "slot": r["slot"],
            "status": r["status"]
        })
    return result

def create_appointment(appointment_id: str, patient_id: str, doctor_id: str, slot: str, status: str) -> Dict[str, Any]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO appointments VALUES (?, ?, ?, ?, ?)",
        (appointment_id, patient_id, doctor_id, slot, status)
    )
    conn.commit()
    conn.close()
    return {"appointment_id": appointment_id, "patient_id": patient_id, "doctor_id": doctor_id, "slot": slot, "status": status}

def update_appointment(appointment_id: str, patient_id: str, doctor_id: str, slot: str, status: str) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE appointments SET patient_id = ?, doctor_id = ?, slot = ?, status = ? WHERE appointment_id = ?",
        (patient_id, doctor_id, slot, status, appointment_id)
    )
    conn.commit()
    rows_changed = cursor.rowcount
    conn.close()
    return rows_changed > 0

def delete_appointment(appointment_id: str) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Optional: Re-add slot back to doctor if cancelling? Let's check doctor_id and slot first
    cursor.execute("SELECT doctor_id, slot FROM appointments WHERE appointment_id = ?", (appointment_id,))
    row = cursor.fetchone()
    if row:
        doctor_id = row["doctor_id"]
        slot = row["slot"]
        cursor.execute("SELECT available_slots FROM doctors WHERE doctor_id = ?", (doctor_id,))
        doc_row = cursor.fetchone()
        if doc_row:
            slots = json.loads(doc_row["available_slots"])
            if slot not in slots:
                slots.append(slot)
                # Sort slots
                slots = sorted(slots)
                cursor.execute("UPDATE doctors SET available_slots = ? WHERE doctor_id = ?", (json.dumps(slots), doctor_id))
    
    cursor.execute("DELETE FROM appointments WHERE appointment_id = ?", (appointment_id,))
    conn.commit()
    rows_changed = cursor.rowcount
    conn.close()
    return rows_changed > 0

# ----------------- Lab Reports CRUD -----------------

def get_all_lab_reports() -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT lr.*, p.name as patient_name
        FROM lab_reports lr
        JOIN patients p ON lr.patient_id = p.patient_id
    """)
    rows = cursor.fetchall()
    conn.close()
    
    result = []
    for r in rows:
        result.append({
            "lab_order_id": r["lab_order_id"],
            "patient_id": r["patient_id"],
            "patient_name": r["patient_name"],
            "test_name": r["test_name"],
            "status": r["status"]
        })
    return result

def get_patient_lab_reports(patient_id: str) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM lab_reports WHERE patient_id = ?", (patient_id,))
    rows = cursor.fetchall()
    conn.close()
    
    result = []
    for r in rows:
        result.append({
            "lab_order_id": r["lab_order_id"],
            "patient_id": r["patient_id"],
            "test_name": r["test_name"],
            "status": r["status"]
        })
    return result

def create_lab_report(lab_order_id: str, patient_id: str, test_name: str, status: str) -> Dict[str, Any]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO lab_reports VALUES (?, ?, ?, ?)",
        (lab_order_id, patient_id, test_name, status)
    )
    conn.commit()
    conn.close()
    return {"lab_order_id": lab_order_id, "patient_id": patient_id, "test_name": test_name, "status": status}

def update_lab_report(lab_order_id: str, patient_id: str, test_name: str, status: str) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE lab_reports SET patient_id = ?, test_name = ?, status = ? WHERE lab_order_id = ?",
        (patient_id, test_name, status, lab_order_id)
    )
    conn.commit()
    rows_changed = cursor.rowcount
    conn.close()
    return rows_changed > 0

def delete_lab_report(lab_order_id: str) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM lab_reports WHERE lab_order_id = ?", (lab_order_id,))
    conn.commit()
    rows_changed = cursor.rowcount
    conn.close()
    return rows_changed > 0

# ----------------- Notifications CRUD -----------------

def get_all_notifications() -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT n.*, p.name as patient_name
        FROM notifications n
        JOIN patients p ON n.patient_id = p.patient_id
        ORDER BY n.sent_at DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    
    result = []
    for r in rows:
        result.append({
            "notification_id": r["notification_id"],
            "patient_id": r["patient_id"],
            "patient_name": r["patient_name"],
            "message": r["message"],
            "channel": r["channel"],
            "status": r["status"],
            "sent_at": r["sent_at"]
        })
    return result

def get_patient_notifications(patient_id: str) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM notifications WHERE patient_id = ? ORDER BY sent_at DESC", (patient_id,))
    rows = cursor.fetchall()
    conn.close()
    
    result = []
    for r in rows:
        result.append({
            "notification_id": r["notification_id"],
            "patient_id": r["patient_id"],
            "message": r["message"],
            "channel": r["channel"],
            "status": r["status"],
            "sent_at": r["sent_at"]
        })
    return result

def create_notification(notification_id: str, patient_id: str, message: str, channel: str, status: str, sent_at: str) -> Dict[str, Any]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO notifications VALUES (?, ?, ?, ?, ?, ?)",
        (notification_id, patient_id, message, channel, status, sent_at)
    )
    conn.commit()
    conn.close()
    return {
        "notification_id": notification_id, "patient_id": patient_id, "message": message,
        "channel": channel, "status": status, "sent_at": sent_at
    }

def delete_notification(notification_id: str) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM notifications WHERE notification_id = ?", (notification_id,))
    conn.commit()
    rows_changed = cursor.rowcount
    conn.close()
    return rows_changed > 0

# ----------------- Consolidated Patient History -----------------

def get_patient_history(patient_id: str) -> Optional[Dict[str, Any]]:
    patient = get_patient(patient_id)
    if not patient:
        return None
        
    appointments = get_patient_appointments(patient_id)
    lab_reports = get_patient_lab_reports(patient_id)
    notifications = get_patient_notifications(patient_id)
    
    return {
        "patient": patient,
        "appointments": appointments,
        "lab_reports": lab_reports,
        "notifications": notifications
    }
