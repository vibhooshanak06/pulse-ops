# PulseOps AI

**AI-Powered API Observability & Incident Intelligence Platform**

PulseOps AI collects API telemetry from your applications, detects abnormal
behavior using statistical and ML techniques, correlates related anomalies into
incidents, and generates evidence-grounded AI explanations to help engineers
investigate issues faster.

---

## What It Does

Instead of showing raw charts, PulseOps answers:

- What is behaving abnormally?
- When did the problem start?
- Which service and endpoint are affected?
- Are multiple anomalies related to the same incident?
- What does the evidence actually show?
- What should I investigate next?

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, React Query, Recharts |
| Backend | Python, FastAPI, SQLAlchemy, Alembic, Pydantic |
| Database | PostgreSQL |
| Cache / Rate limiting | Redis |
| ML / Anomaly detection | Pandas, NumPy, Scikit-learn (Isolation Forest + Z-score) |
| AI Explanation | OpenAI API (evidence-grounded prompting) |
| SDK | Custom Python ASGI middleware |

---

## Project Structure

```
pulse-ops/
├── backend/          FastAPI backend — auth, telemetry, metrics, incidents, AI
├── frontend/         React dashboard — 7-page SaaS UI
├── sdk/              Python SDK/middleware for automatic telemetry capture
├── ml-engine/        Anomaly detection, incident correlation, evidence, AI
├── demo-service/     Sample FastAPI app with SDK installed + failure simulation
└── docs/             Architecture diagrams and API reference
```

---

## Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL 15+ (running locally or via Docker)
- Redis 7+ (running locally or via Docker)

---

## Quick Start

### 1. PostgreSQL setup

```sql
CREATE USER pulseops_user WITH PASSWORD 'pulseops_password';
CREATE DATABASE pulseops OWNER pulseops_user;
```

### 2. Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS/Linux
pip install -r requirements.txt
cp .env.example .env           # edit values as needed

# Run database migrations
alembic upgrade head

# Start the API server
uvicorn app.main:app --reload --port 8000
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev                    # starts on http://localhost:5173
```

### 4. Demo Service

```bash
cd demo-service
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
pip install -e ../sdk          # install PulseOps SDK from local path
cp .env.example .env           # add your API key from the dashboard

uvicorn app.main:app --reload --port 8001
```

### 5. ML Engine

```bash
cd ml-engine
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env

python anomaly_detection/runner.py
```

---

## Build Phases

| Phase | Status | Description |
|---|---|---|
| 0 | ✅ Complete | Architecture and product understanding |
| 1 | ✅ Complete | Project setup and repository structure |
| 2 | 🔲 Next | Database schema and Alembic migrations |
| 3 | 🔲 | Authentication and multi-tenancy |
| 4 | 🔲 | API key management |
| 5 | 🔲 | Telemetry ingestion |
| 6 | 🔲 | SDK / middleware |
| 7 | 🔲 | Metrics engine |
| 8 | 🔲 | Redis integration |
| 9 | 🔲 | Anomaly detection |
| 10 | 🔲 | Incident correlation |
| 11 | 🔲 | Incident management |
| 12 | 🔲 | Evidence collection |
| 13 | 🔲 | AI incident intelligence |
| 14 | 🔲 | React frontend |
| 15 | 🔲 | Demo service + failure simulation |
| 16 | 🔲 | Testing |
| 17 | 🔲 | Dockerization |
| 18 | 🔲 | Final polish |

---

## API Documentation

Once the backend is running, visit:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

---

## Architecture

See [`docs/architecture.md`](docs/architecture.md) for the full data flow diagram.

---

## Key Design Decisions

**Why not Datadog/Grafana?**
This is a focused implementation of the core *incident intelligence* workflow —
telemetry → anomaly detection → correlation → evidence → AI explanation.
Breadth is sacrificed for depth and explainability.

**Why Isolation Forest?**
It is unsupervised (no labelled anomaly data required), handles multi-variate
feature combinations, and its decisions are explainable. LSTM or deep learning
adds complexity without sufficient benefit at this scale.

**Why evidence-grounded AI?**
LLMs hallucinate. Restricting the model to reason only over structured evidence
collected from the database eliminates invented root causes and makes the
output auditable.

**Why Redis for three specific jobs?**
Metrics cache (TTL-based), service health snapshots (latest state), and rate
limiting (atomic counters). Each has a clear architectural reason — Redis is
not included as a buzzword.

---

## License

MIT
