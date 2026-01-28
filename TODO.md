# Project Tasks

- [ ] **1. Backend & AI Performance (No Formal Testing)**
    - [ ] Keep API stable (fix network errors, ensure it stays reachable).
    - [ ] Simplify and harden AI input handling so it always accepts data cleanly.
    - [ ] Tune for speed: keep responses as fast as possible with qwen2.5:1.5b, without adding test/benchmark overhead.

- [ ] **2. Fast Input Format Handling**
    - [ ] Make backend convert CSV/JSON/TXT into a single fast internal format (compact JSON or text) before sending to AI.
    - [ ] Limit heavy parsing work so most time is spent inside the model, not on Python overhead.

- [ ] **3. Rich Explanations + Storage**
    - [ ] Update prompts so AI returns longer, clearer explanations while staying responsive.
    - [ ] Store every AI explanation in a lightweight backend "explanations" history for later use.

- [ ] **4. Feature: CSV / File Batch Upload**
    - [ ] Backend: Ensure `/applications/batch_upload` and related endpoints handle CSV/JSON/TXT reliably.
    - [ ] Frontend: Add/keep an "Upload" entry point with a simple modal.
    - [ ] Frontend: Show basic loading/progress during processing (no test scripts required).

- [ ] **5. UI/UX Upgrade (Dashboard)**
    - [ ] Design: Switch to a more professional Kanban/Grid layout (cleaner, less "gamey").
    - [ ] Component: Fix Sidebar size (make it smaller/cleaner).
    - [ ] Responsiveness: Ensure all buttons (Filter, Search, Approve, Reject) work in normal usage (manual checks only).
 