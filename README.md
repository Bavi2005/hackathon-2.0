# Universal XAI Decision Engine

# How to run
cd ai\ /agent; 
ollama pull mistral:7b-instruct-q4_K_M;
uvicorn xai_agent:app --reload;
open new terminal;
cd ui;
npm install;
npm run dev;
open localhost:3000 on any browser

## New Features (v2.0)

### 1. AI Override Handling
- System now generates explanations when agents override AI decisions
- Override badge displayed in employee dashboard
- Detailed override explanations with reasoning and next steps

### 2. Improved AI Model
- Switched from `phi3:mini` to `mistral:7b-instruct-q4_K_M` for better performance
- Faster processing and more reliable JSON generation
- Better decision quality on 16GB RAM systems

### 3. RAG/Memory System
- **PolicyMemory**: Store and manage decision policies by domain
- Upload policies via CSV, JSON, or TXT files
- Policies automatically injected into AI prompts
- **AIMemory**: System learns from past decisions for better context

### 4. Enhanced Metrics Display
- Key metrics: risk_score, approval_probability, critical_factors
- Properly formatted counterfactuals display
- Visual metric cards in dashboard

### 5. Editable Explanations
- Agents can edit AI-generated explanations before showing to customers
- Edit button in case review panel
- Maintains audit trail of edits

### 6. Optimized Bulk Processing
- Parallel batch processing (batch size: 5)
- Faster CSV uploads
- Better resource utilization

### New API Endpoints
- `POST /policies` - Add a policy
- `GET /policies` - Get all policies
- `DELETE /policies/{domain}/{policy_id}` - Remove a policy
- `POST /policies/upload` - Upload policy file
- `PUT /applications/{app_id}/explanation` - Edit explanation
- `POST /bulk/upload` - Optimized bulk CSV upload
- `GET /health` - Check AI model availability

### UI Components
- **PolicyManager**: Modal for managing policies across domains
- **ExplanationEditor**: Modal for editing explanations
- **Enhanced EmployeeDashboard**: Shows metrics, overrides, and counterfactuals

## i. Chosen Problem Statement
In today's digital landscape, high-stakes decisions—such as loan approvals, job hiring, insurance claims, and credit assessments—are increasingly automated by AI. However, most of these systems act as "black boxes," providing results without transparency. This lack of explainability leads to trust issues, potential biases, and frustration for users who receive a rejection without knowing why or how to improve.

**The Problem**: How can we build an automated decision system that is not only accurate but also transparent, fair, and actionable for both customers and human auditors?

---

## ii. Explanation of the Solution
**TriShade** is a comprehensive, full-stack AI governance and decision-support platform designed to solve the critical "black box" problem in automated systems. Built with the philosophy that AI should be a partner in decision-making rather than a silent arbiter, TriShade integrates high-performance engineering with state-of-the-art Explainable AI (XAI) methodologies to bridge the gap between algorithmic efficiency and human trust.

### Technical Architecture & Core Logic
At its heart, TriShade operates on a multi-tiered architecture that separates concerns between data capture, AI reasoning, and human oversight:

1.  **Intelligent Submission Layer**: The Customer Portal is not just a form; it is a specialized data-entry engine. It features dynamic field rendering based on the application domain (Loan, Job, Insurance, or Credit). Crucially, it includes a front-end "Harmonization Layer" that sanitizes and typesets user inputs (e.g., converting strings to precise floats/integers) before they touch the API. This ensures that the AI models receive structured, high-quality data, minimizing 422 errors and "hallucinations" caused by malformed input.

2.  **The XAI Reasoning Engine**: When a request hits our FastAPI backend, TriShade triggers a deterministic reasoning cycle. We utilize **Ollama** to host the **phi3:mini** model locally, ensuring data privacy and low latency. Unlike standard classifiers that return a binary 0 or 1, our engine uses strict JSON-schema prompting to force the AI into an "Audit-Grade" state. The model is required to output:
    *   **Qualitative Reasoning**: A human-readable narrative explaining *why* a specific decision was reached.
    *   **Confidence Scoring**: A statistical measure of how certain the model is about its recommendation.
    *   **Fairness Assessment**: An internal self-audit to identify if sensitive attributes (like marital status or age) disproportionately influenced the outcome.

3.  **Actionable Counterfactuals**: One of TriShade's standout features is the generation of counterfactual explanations. The engine doesn't just say "No"; it provides a roadmap for "Yes." By simulating slight variations in the input data, the AI identifies the minimum changes required for a different outcome (e.g., "Increasing your credit score by 50 points would change this rejection into an approval"). These insights are delivered directly to the customer, transforming a static result into an actionable advisory.

4.  **Human-in-the-Loop Governance**: TriShade acknowledges that AI is not infallible. The **Employee Audit Portal** serves as the final authority. It provides a high-density dashboard where human auditors see the same AI insights as the customer, alongside the raw data. Auditors can approve, reject, or provide additional feedback, with their final decision being persisted in a robust JSON-based database (`db.json`). This ensures full traceability and accountability for every application processed by the system.

### The Value Proposition
TriShade delivers a premium User Experience (UX) characterized by glassmorphism and micro-animations, designed to feel state-of-the-art. By providing real-time polling and status tracking, the system maintains engagement and reduces the "anxiety of the void" typical in automated applications. Ultimately, TriShade isn't just a decision engine; it's a transparency engine built for the next generation of AI-driven governance.

---

## iii. Tech Stack Used
- **Frontend Architecture**:
  - **Framework**: Next.js (TypeScript)
  - **Styling**: Vanilla CSS (Modern aesthetic with Glassmorphism)
  - **Icons**: Lucide React
  - **API Client**: Axios (with custom transformation interceptors)
- **Backend Architecture**:
  - **Language**: Python
  - **API Framework**: FastAPI
  - **Server**: Uvicorn
  - **Persistence**: JSON-based Database (`db.json`)
- **AI Core**:
  - **Engine**: Ollama
  - **Model**: phi3:mini (Optimized for deterministic XAI reasoning)
- **Tools**:
  - **Version Control**: Git

---

## iv. Link to Your Demo Video
https://youtu.be/Ci7YcPcaG7c?si=ShGResNoFpFP2Xsn

---

## v. Link to Your Presentation Deck
https://www.canva.com/design/DAG-Wng8mTw/aU1IInB10b0_6YY2zQbapQ/edit?utm_content=DAG-Wng8mTw&utm_campaign=designshare&utm_medium=link2&utm_source=sharebutton
