# Employee Attendance & Analytics API (FastAPI + MongoDB)

---

## Quick Start

### 1. Requirements

- Python 3.11+
- MongoDB 6.0+

### 2. Installation

```bash
# Activate virtual environment
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Run the Application

```bash
uvicorn app.main:app --port 8000 --reload
```

The API is available at `http://localhost:8000`. Interactive OpenAPI at `http://localhost:8000/docs`.

---

## Architectural Highlights

- **Modular Design:** Clear separation of concerns inside `app/`:
  - `core/`: Timezone conversions, epoch milliseconds handling and business rules.
  - `db/`: Database connection lifecycle and index creation.
  - `schemas/`: Models fot validating inputs, ranges, regex.
  - `services/`: Business logic.
  - `routers/`: Route handlers implementing `openapi.yaml`.
- **MongoDB Aggregations:** All analytics endpoints execute inside MongoDB

---
