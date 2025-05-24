import os
import logging
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from pymongo import MongoClient
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
from neo4j import GraphDatabase
import time
from datetime import datetime, timedelta

# ===== InfluxDB ENV SETUP =====
os.environ["INFLUX_URL"] = "http://localhost:8086"
os.environ["INFLUX_ORG"] = "3221fb6fa7736194"
os.environ["INFLUX_TOKEN"] = "VgqiaDweOTm5zUnAMIvee76me2udZJw8cQyVuXhcMvijSfe4zEI10i5mFn7Mrz7_o-C0WR5xk8qjS7euuxnz5A=="

# ===== Logging =====
logging.basicConfig(filename='app.log', filemode='a',
                    format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

# ===== DB Connections =====
def connect_mongo(retry=3, delay=2):
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    for attempt in range(retry):
        try:
            client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
            client.admin.command('ping')
            logging.info("Connected to MongoDB")
            return client
        except Exception as e:
            logging.error("MongoDB connection failed: %s", e)
            time.sleep(delay)
    return None

def connect_influx():
    try:
        return InfluxDBClient(
            url=os.getenv("INFLUX_URL"),
            token=os.getenv("INFLUX_TOKEN"),
            org=os.getenv("INFLUX_ORG")
        )
    except Exception as e:
        logging.critical("InfluxDB connection failed: %s", e)
        return None

def connect_neo4j():
    try:
        return GraphDatabase.driver(
            os.getenv("NEO4J_URI","neo4j+s://57c4e3ac.databases.neo4j.io"),
            auth=(os.getenv("NEO4J_USERNAME", "neo4j"),
                  os.getenv("NEO4J_PASSWORD", "k364TiTSoQDh0XwX7f4HCc6ZdjGX4-NWWgG7uLfRjts"))
        )
    except Exception as e:
        logging.critical("Neo4j connection failed: %s", e)
        return None

# ===== Init Connections =====
mongo_client = connect_mongo()
if mongo_client:
    mongo_db = mongo_client["healthcare"]
    patients_col = mongo_db["patients"]
    appointments_col = mongo_db["appointments"]
    patients_col.create_index("name")
else:
    patients_col = appointments_col = None

influx_client = connect_influx()
write_api = influx_client.write_api(write_options=SYNCHRONOUS) if influx_client else None
query_api = influx_client.query_api() if influx_client else None

neo4j_driver = connect_neo4j()

profile_cache = {}

def validate_patient_name(name):
    if not name or len(name.strip()) < 2:
        raise ValueError("Invalid patient name. Must be at least 2 characters.")

def get_patient_profile(name):
    if name in profile_cache:
        return profile_cache[name]

    report = []

    # MongoDB
    if patients_col is None:
        report.append("❌ MongoDB connection unavailable.\n")
    else:
        try:
            patient = patients_col.find_one({"name": name})
            if not patient:
                return f"❌ No patient found with name '{name}' in MongoDB.\n"
            report.append("📄 MongoDB Data:")
            report.append(str(patient))
            appts = list(appointments_col.find({"patient_name": name}))
            report.append("📅 Appointments:")
            if appts:
                for appt in appts:
                    report.append(f" - {appt['date']} | {appt['department']}")
            else:
                report.append(" - No appointments found.")
            report.append("")
        except Exception as e:
            report.append(f"⚠️ MongoDB error: {e}\n")

    # InfluxDB
    if not query_api:
        report.append("❌ InfluxDB connection unavailable.\n")
    else:
        try:
            report.append("📊 InfluxDB Body Measurements:")
            influx_query = f"""
            from(bucket: "HealthData")
              |> range(start: -30d)
              |> filter(fn: (r) => r["_measurement"] == "body_data" and r["patient"] == "{name}")
            """
            results = query_api.query(influx_query, org=os.getenv("INFLUX_ORG"))
            found = False
            for table in results:
                for record in table.records:
                    report.append(f" - {record.get_field()}: {record.get_value()} at {record.get_time()}")
                    found = True
            if not found:
                report.append(" - No recent data found.")
            report.append("")
        except Exception as e:
            report.append(f"⚠️ InfluxDB error: {e}\n")

    # Neo4j (Optional)
    if not neo4j_driver:
        report.append("❌ Neo4j connection unavailable.\n")
    else:
        try:
            report.append("🧠 Treated by Doctors:")
            with neo4j_driver.session() as session:
                result = session.run("""
                    MATCH (p:Patient {name: $name})-[:TREATED_BY]->(d:Doctor)
                    RETURN d.name AS doctor
                """, name=name)
                doctors = [r["doctor"] for r in result]
                if doctors:
                    for doc in doctors:
                        report.append(f" - {doc}")
                else:
                    report.append(" - No doctors found.")
            report.append("")
        except Exception as e:
            report.append(f"⚠️ Neo4j error: {e}\n")

    report.append("📘 Lessons Learned:")

    final = "\n".join(report)
    profile_cache[name] = final
    return final

def save_report_to_file(name, report):
    with open(f"{name}_report.txt", "w", encoding="utf-8") as f:
        f.write(report)

class HealthcareApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Healthcare Dashboard")
        self.geometry("700x600")
        frame = ttk.Frame(self)
        frame.pack(pady=10)
        ttk.Label(frame, text="Enter Patient Name:").grid(row=0, column=0, padx=5)
        self.name_var = tk.StringVar()
        self.name_entry = ttk.Entry(frame, width=30, textvariable=self.name_var)
        self.name_entry.grid(row=0, column=1, padx=5)
        self.name_entry.focus()
        ttk.Button(frame, text="Show Report", command=self.show_report).grid(row=0, column=2, padx=5)
        self.output_text = scrolledtext.ScrolledText(self, wrap=tk.WORD, width=80, height=30)
        self.output_text.pack(padx=10, pady=10)

    def show_report(self):
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning("Input Required", "Please enter a patient name.")
            return
        try:
            validate_patient_name(name)
        except ValueError as ve:
            messagebox.showerror("Validation Error", str(ve))
            return
        self.output_text.delete('1.0', tk.END)
        self.output_text.insert(tk.END, "Loading...\n")
        self.update()
        report = get_patient_profile(name)
        self.output_text.delete('1.0', tk.END)
        self.output_text.insert(tk.END, report)
        save_report_to_file(name, report)

def insert_sample():
    patients = [
        {"name": "Ahmed Ali", "age": 34, "medical_history": ["Diabetes"], "region": "North"},
        {"name": "Mona Hassan", "age": 28, "medical_history": ["Asthma"], "region": "South"},
        {"name": "Ahmed Mohamed", "age": 35, "medical_history": ["Diabetes", "High Blood Pressure"], "region": "North"},
        {"name": "Lina Hamed", "age": 29, "medical_history": ["Asthma"], "region": "South"},
        {"name": "Khaled Naser", "age": 45, "medical_history": ["Obesity"], "region": "East"}
    ]
    patients_col.insert_many(patients)

    appointments = [
        {"patient_name": "Ahmed Mohamed", "date": "2025-05-20", "department": "Cardiology"},
        {"patient_name": "Lina Hamed", "date": "2025-05-22", "department": "Pulmonology"},
        {"patient_name": "Ahmed Ali", "date": "2025-06-01", "department": "Endocrinology"},
        {"patient_name": "Mona Hassan", "date": "2025-06-02", "department": "Allergy"}
    ]
    appointments_col.insert_many(appointments)

    if write_api is not None:
        now = datetime.utcnow()
        for patient in patients:
            name = patient["name"]
            try:
                points = [
                    Point("body_data").tag("patient", name).field("heart_rate", 70 + hash(name) % 10).time(now - timedelta(minutes=30), WritePrecision.NS),
                    Point("body_data").tag("patient", name).field("blood_pressure", 110 + hash(name) % 10).time(now, WritePrecision.NS)
                ]
                write_api.write(bucket="HealthData", org=os.getenv("INFLUX_ORG"), record=points)
                print(f"✅ InfluxDB data written for {name}")
            except Exception as e:
                print(f"❌ InfluxDB write error for {name}: {e}")

if __name__ == "__main__":
    insert_sample()
    app = HealthcareApp()
    app.mainloop()
    if mongo_client:
        mongo_client.close()
    if influx_client:
        influx_client.close()
    if neo4j_driver:
        neo4j_driver.close()
