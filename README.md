# EcoSphere — Corporate ESG & Sustainability Management Platform

EcoSphere is a modern, enterprise-grade **Environmental, Social, and Governance (ESG) Management & Analytics Platform** designed to help organizations track, convert, and visualize sustainability metrics, ESG compliance, employee engagement, and environmental liabilities.

---

## 🚀 Key Modules & Features

### 🟢 Environmental: Carbon Cost Accounting
* **Operational Resource Mapping:** Tracks and converts raw ERP events (fuel invoices, energy bills) into Scope 1, 2, and 3 emissions using configurable, dynamic **Emission Factors**.
* **Financial Liability Conversion:** Converts greenhouse gas emissions ($CO_2e$) into monetary liabilities based on active, version-controlled carbon pricing rules.
* **Department Budgets:** Monitors actual emissions against configured annual or quarterly carbon budgets, highlighting overrun risks with visual thresholds.
* **Scenario Simulator:** Interactive sliders allowing ESG teams to simulate diesel reductions, fleet electrification (EVs), and solar offsets to preview direct cost savings and ESG score shifts.

### 🟡 Social: CSR & Gamified Employee Engagement
* **CSR Activities volunteering:** Coordinates employee participation and approvals for local community CSR events.
* **Gamification Lab:** Tracks friendly corporate sustainability challenges, leaderboards, and unlocks badges using a dynamic XP transaction system.
* **Mandatory Trainings:** Monitors employee completion rates for regulatory safety and environmental training programs.

### 🔴 Governance: Risk Management & Heatmap
* **ESG Risk Heatmap:** Dynamic matrix evaluating department risks across Env (growth, overrun), Social (participation, training completion, engagement), and Gov (policy acknowledgements, audits) pillars.
* **Policy Acknowledgements:** Coordinates publishing and tracking of mandatory ESG codes of conduct and policy versions.
* **Compliance Issues Ticketing:** Track, assign, and alert owners on unresolved or overdue compliance violations.
* **Department Audits:** Logs audit dates, findings, and scores, factoring results directly into governance risk matrices.

---

## 🛠️ Technology Stack

### Backend (Python)
* **Framework:** FastAPI (async routing, Pydantic v2 validation)
* **ORM:** SQLAlchemy (declarative models, relationship mapping)
* **Database:** PostgreSQL (production-ready) / SQLite (in-memory for testing)
* **Task Runner / Server:** Uvicorn

### Frontend (TypeScript / React)
* **Build System:** Vite
* **UI Components:** React with custom premium vanilla CSS styling & Radix UI
* **Query Caching:** TanStack React Query (v5)
* **Data Visualization:** Recharts (responsive trends, area, and bar charts)
* **Icons:** Lucide React

---

## 📁 Repository Structure

```
├── backend/
│   ├── app/
│   │   ├── api/            # API endpoints (carbon, compliance, erp, scores)
│   │   ├── core/           # Security, config, dependency injection
│   │   ├── models/         # SQLAlchemy schemas (carbon, risk, governance)
│   │   ├── schemas/        # Pydantic v2 request/response validation schemas
│   │   ├── services/       # Core business logic (risk engine, cost calculations)
│   │   └── seed/           # Pre-configured demo data seed script
│   └── tests/              # Comprehensive Pytest/Unittest suite
├── frontend/
│   ├── src/
│   │   ├── app/            # App shell, router, and navigation items
│   │   ├── components/     # Reusable UI components (StatCard, PageHeader)
│   │   ├── features/       # Modular features (carbon-accounting, risk-heatmap)
│   │   └── lib/            # Axios API wrappers and Auth context providers
│   └── package.json
```

---

## ⚙️ Getting Started & Installation

### Backend Setup
1. Navigate to the backend directory:
   ```bash
   cd backend
   ```
2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   # On Windows (PowerShell):
   .\.venv\Scripts\Activate.ps1
   # On macOS/Linux:
   source .venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Seed the database (runs on PostgreSQL by default; config is loaded from environment variables or defaults to `localhost`):
   ```bash
   python -m app.seed
   ```
5. Start the development server:
   ```bash
   uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
   ```
   *Note: Ensure the backend is run on port **8001** to align with the frontend proxy configurations.*

### Frontend Setup
1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Install npm packages:
   ```bash
   npm install
   ```
3. Start the Vite development server:
   ```bash
   npm run dev
   ```
4. Open your browser and navigate to [http://localhost:5173/](http://localhost:5173/).

---

## 🔑 Demo Seed Credentials
All pre-seeded user accounts use the password `Demo@123`:

* **ESG Manager:** `esg@ecosphere.in` (Full access to configurations, risk dashboard, and metrics)
* **Admin:** `admin@ecosphere.in` (Full system administration)
* **Dept Head:** `head@ecosphere.in` (View department-specific data and budgets)
* **Employee:** `employee@ecosphere.in` (View personal dashboard, challenges, and log completions)

---

## 🧪 Running Unit Tests
A comprehensive test suite validates the endpoints, lifecycle states, and engine formulas. Run the suite from the `backend/` directory:

```bash
.\.venv\Scripts\python.exe -m unittest discover tests
```