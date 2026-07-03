# 🏥 Agentic Hospital Management System

> **Multi-Agent AI Hospital Workflow Automation using LangGraph, LangChain & Google Gemini**

An intelligent hospital workflow system built using **LangGraph** that orchestrates multiple AI agents to automate patient management tasks such as appointment booking, doctor search, lab report verification, ECG scheduling, notifications, validation, and workflow summari(image.png)
---

## 📸 Demo

<img src="C:\Users\Mukesh\Desktop\WorkSpace\Experiment\Hospital_Management_system\image.png" width="100%"/>

*(Replace with your project screenshot if required.)*

---

# ✨ Features

- 🤖 Multi-Agent Architecture
- 🧠 Supervisor Agent for task planning
- 👤 Patient Information Retrieval
- 👨‍⚕️ Doctor Search Agent
- 📅 Automatic Appointment Booking
- 🧪 Lab Report Verification
- 🩺 ECG Scheduling (only if report doesn't already exist)
- 📩 SMS/Email Notification Agent
- ✅ Validator Agent to detect hallucinations and missing steps
- 📝 Summary Agent for patient-friendly response
- ⚡ Parallel execution using ThreadPoolExecutor
- 🔄 Automatic Retry & Failure Recovery
- 🌐 Built using LangGraph State Machine

---

# 🏗️ Architecture

```
                    User Query
                         │
                         ▼
                Supervisor Agent
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
 Patient Info      Doctor Search     Lab Report
     Agent             Agent            Agent
          │              │              │
          └──────┬───────┴───────┬──────┘
                 ▼               ▼
         Appointment Agent   Lab Scheduling
                 │               │
                 └──────┬────────┘
                        ▼
               Notification Agent
                        │
                        ▼
                 Validator Agent
                        │
              Validation Passed?
                 │             │
               Yes            No
                 │             │
                 ▼             ▼
           Summary Agent   Revision Router
                 │
                 ▼
              Final Output
```

---

# 🚀 Tech Stack

- Python
- LangGraph
- LangChain
- Google Gemini 2.5 Flash
- ThreadPoolExecutor
- dotenv
- JSON
- StateGraph

---

# 📂 Project Structure

```
Agentic-Hospital-System/
│
├── hospital_agentic_system.py
├── .env
├── README.md
├── requirements.txt
├── assets/
│      dashboard.png
│
└── screenshots/
       workflow.png
```

---

# 🤖 AI Agents

| Agent | Responsibility |
|---------|----------------|
| Supervisor Agent | Understands user request and creates workflow |
| Patient Info Agent | Fetches patient details |
| Doctor Search Agent | Finds specialist & earliest available slot |
| Lab Report Agent | Checks if requested report already exists |
| Appointment Agent | Books appointment |
| Lab Scheduling Agent | Schedules lab test if report missing |
| Notification Agent | Sends SMS/Email notification |
| Validator Agent | Detects hallucinations & validates workflow |
| Summarizer Agent | Generates final patient summary |

---

# 🔄 Workflow

```
User Request
      │
      ▼
Supervisor Agent
      │
      ▼
Parallel Execution
│
├── Patient Agent
├── Doctor Agent
└── Lab Agent
      │
      ▼
Appointment Booking
      │
      ▼
Lab Scheduling
      │
      ▼
Notification
      │
      ▼
Validation
      │
      ▼
Summary
```

---

# ⚙️ Installation

Clone the repository

```bash
git clone https://github.com/yourusername/Agentic-Hospital-System.git
```

Go inside project

```bash
cd Agentic-Hospital-System
```

Create virtual environment

```bash
python -m venv venv
```

Activate

Windows

```bash
venv\Scripts\activate
```

Linux/Mac

```bash
source venv/bin/activate
```

Install dependencies

```bash
pip install -r requirements.txt
```

---

# 🔑 Environment Variables

Create a `.env` file

```env
GOOGLE_API_KEY=YOUR_GEMINI_API_KEY
```

---

# ▶️ Run

```bash
python hospital_agentic_system.py
```

---

# 🧪 Example Input

```
I have chest pain.

Book the earliest appointment with a cardiologist.

Check whether I already have an ECG report.

If not, schedule an ECG.

Notify me after everything is completed.
```

---

# 📤 Example Output

```json
{
  "appointment_status": "confirmed",
  "lab_test_status": "scheduled",
  "notification_status": "sent",
  "summary": "Your appointment has been confirmed with Dr. Brown. Your ECG test has been scheduled and the notification has been sent successfully."
}
```

---

# ⚡ Parallel Execution

The following agents execute simultaneously:

- Patient Information Agent
- Doctor Search Agent
- Lab Report Agent

This significantly reduces workflow execution time.

---

# 🛡️ Failure Recovery

The workflow includes built-in resilience:

- Retry failed appointment booking
- Retry notification delivery
- Conditional workflow routing
- Validation before final response
- Graceful error handling
- Automatic recovery paths

---

# 📊 LangGraph State Flow

```
Supervisor
      │
      ▼
Gather Context
      │
      ▼
Appointment
      │
      ▼
Lab Scheduling
      │
      ▼
Notification
      │
      ▼
Validation
      │
      ▼
Summary
      │
      ▼
END
```

---

# 🎯 Highlights

- Multi-Agent AI System
- LangGraph State Machine
- Conditional Routing
- Parallel Execution
- Dynamic Task Planning
- Retry Mechanism
- Self Validation
- Hallucination Prevention
- Production-style Workflow
- Modular Architecture

---

# 📈 Future Improvements

- Real Database Integration (MySQL/PostgreSQL)
- FastAPI Backend
- React Dashboard
- Real SMS & Email Integration
- Doctor Recommendation using RAG
- Medical Knowledge Base
- Voice Assistant Support
- Electronic Health Records (EHR)
- Docker Deployment
- Kubernetes Support

---

# 👨‍💻 Author

**Mukesh Kumar**

B.Tech Electronics & Communication Engineering

AI • Machine Learning • Generative AI • Multi-Agent Systems

---

# ⭐ If you found this project useful

Please consider giving it a **Star ⭐** on GitHub!

---

## 📄 License

This project is developed for educational and learning purposes.

MIT License.