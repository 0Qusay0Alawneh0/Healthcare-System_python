# Healthcare-System_python
# Healthcare Multi-Database Integration Demo

This Python project demonstrates integration with three different databases commonly used in healthcare and IoT applications:

- **MongoDB** for storing patient records and appointments (document database).
- **InfluxDB** for time-series body measurements (heart rate, blood pressure).
- **Neo4j** for graph relationships between doctors and patients.

---

## Features

- Insert sample patient data and appointments into MongoDB.
- Insert simulated body measurement data points into InfluxDB.
- Create graph nodes and relationships in Neo4j representing doctors and their patients.
- Query and display a unified patient profile by fetching data from all three databases.

---

## Prerequisites

- Python 3.7+
- Install required Python packages:

```bash
pip install pymongo influxdb-client neo4j
