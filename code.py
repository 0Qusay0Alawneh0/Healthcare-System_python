from pymongo import MongoClient
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
from influxdb_client.client.query_api import QueryApi
from neo4j import GraphDatabase
from datetime import datetime, timedelta

# ================================
# MongoDB Setup & CRUD
# ================================
mongo_client = MongoClient("mongodb+srv://221006:G3QjzRfwy8K6PElQ@cluster0.bbwazwe.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0", ssl=True, tls=True, tlsAllowInvalidCertificates=True)
mongo_db = mongo_client["healthcare"]
patients_col = mongo_db["patients"]
appointments_col = mongo_db["appointments"]

# Insert multiple patients
patients = [
    {"name": "Ahmed Mohamed", "age": 35, "medical_history": ["Diabetes", "High Blood Pressure"], "region": "North"},
    {"name": "Lina Hamed", "age": 29, "medical_history": ["Asthma"], "region": "South"},
    {"name": "Khaled Naser", "age": 45, "medical_history": ["Obesity"], "region": "East"},
]
patients_col.insert_many(patients)

# Insert some appointments
appointments_col.insert_many([
    {"patient_name": "Ahmed Mohamed", "date": "2025-05-20", "department": "Cardiology"},
    {"patient_name": "Lina Hamed", "date": "2025-05-22", "department": "Pulmonology"},
])

# ================================
# InfluxDB Setup & Data Insert
# ================================
influx_client = InfluxDBClient(
    url="https://us-east-1-1.aws.cloud2.influxdata.com",
    token="G3N70vpdr98aQsT6mrlBsvbbDyPX8DAOf67CRx6W81nbHlS9ehq2Arf1DFIUw5XtY_M5F9yoIqDsP9uC_Kwjsw==",
    org="ppu"
)
write_api = influx_client.write_api(write_options=SYNCHRONOUS)
query_api = influx_client.query_api()

def add_measurements(patient_name):
    now = datetime.utcnow()
    points = [
        Point("body_data").tag("patient", patient_name).field("heart_rate", 72).time(now - timedelta(hours=1), WritePrecision.NS),
        Point("body_data").tag("patient", patient_name).field("blood_pressure", 120).time(now, WritePrecision.NS)
    ]
    write_api.write(bucket="HealthData", record=points)

for p in ["Ahmed Mohamed", "Lina Hamed", "Khaled Naser"]:
    add_measurements(p)

# ================================
# Neo4j Setup & Graph Relations
# ================================
neo4j_driver = GraphDatabase.driver(
    "neo4j+s://05062f6a.databases.neo4j.io",
    auth=("neo4j", "J-NAMbAKY7bE6D9-ScdW4RR22vl1Khk-yJX9-zxqVf0")
)

def setup_graph(tx):
    tx.run("""
        MERGE (d1:Doctor {name: 'Dr. Omar'})
        MERGE (d2:Doctor {name: 'Dr. Sara'})
        MERGE (d3:Doctor {name: 'Dr. Nour'})

        MERGE (p1:Patient {name: 'Ahmed Mohamed'})
        MERGE (p2:Patient {name: 'Lina Hamed'})
        MERGE (p3:Patient {name: 'Khaled Naser'})

        MERGE (d1)-[:TREATS]->(p1)
        MERGE (d2)-[:TREATS]->(p2)
        MERGE (d3)-[:TREATS]->(p3)
        MERGE (d2)-[:TREATS]->(p3)
    """)

def create_index(tx):
    tx.run("CREATE INDEX doctor_name_index IF NOT EXISTS FOR (d:Doctor) ON (d.name)")

with neo4j_driver.session() as session:
    session.write_transaction(setup_graph)
    session.write_transaction(create_index)

# ================================
# Unified Patient Profile Display
# ================================
def get_patient_profile(name):
    print(f"\n📋 Full Report for: {name}")
    print("=" * 50)

    # MongoDB Data
    patient = patients_col.find_one({"name": name})
    if not patient:
        print("❌ Patient not found in MongoDB.")
        return
    print(f"📄 MongoDB Data:\n{patient}")

    # Appointments
    appts = list(appointments_col.find({"patient_name": name}))
    print(f"\n📅 Appointments:")
    for appt in appts:
        print(f" - {appt['date']} | {appt['department']}")

    # InfluxDB Measurements
    print("\n📊 InfluxDB Measurements:")
    influx_query = f'''
    from(bucket: "HealthData")
      |> range(start: -2d)
      |> filter(fn: (r) => r["_measurement"] == "body_data" and r["patient"] == "{name}")
    '''
    results = query_api.query(influx_query, org="PPU")
    for table in results:
        for record in table.records:
            print(f" - {record.get_field()}: {record.get_value()} at {record.get_time()}")

    # Neo4j Doctors
    print("\n🧠 Treated by Doctors:")
    with neo4j_driver.session() as session:
        result = session.run("""
            MATCH (d:Doctor)-[:TREATS]->(p:Patient {name: $name})
            RETURN d.name AS doctor
        """, name=name)
        doctors = [r["doctor"] for r in result]
        if doctors:
            for doc in doctors:
                print(f" - {doc}")
        else:
            print(" - No doctors found.")

# ================================
# Execution
# ================================
if __name__ == "__main__":
    for patient_name in ["Ahmed Mohamed", "Lina Hamed", "Khaled Naser"]:
        get_patient_profile(patient_name)

    mongo_client.close()
    influx_client.close()
    neo4j_driver.close()
