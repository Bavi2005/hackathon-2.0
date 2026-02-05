from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from enum import Enum
from functools import lru_cache
import hashlib
import pandas as pd
import json
import asyncio
import httpx
import re
import uuid
import os
from io import BytesIO
from pypdf import PdfReader

# =====================================================
# APP
# =====================================================
app = FastAPI(title="Universal XAI Decision Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# =====================================================
# CONFIG (RAM-SAFE)
# =====================================================
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "qwen2.5:3b"

# FAST MODE: Set to True for instant rule-based decisions (no AI)
# Set to False to use slower but smarter AI decisions
FAST_MODE = True  # Toggle this for instant vs AI responses

# Performance tuning for CPU inference
OLLAMA_OPTIONS = {
    "num_ctx": 2048,       # Reduced context window (default 4096) - faster
    "num_thread": 8,       # Use 8 of 12 CPU threads
    "temperature": 0.3,    # Lower = faster, more deterministic
    "top_p": 0.9,          # Slightly restrict sampling
    "repeat_penalty": 1.1, # Prevent repetition loops
    "num_predict": 512,    # Limit output tokens (was unlimited)
}

MAX_CSV_ROWS = 50
MAX_CONCURRENCY = 3  # Reduced to avoid CPU contention
REQUEST_TIMEOUT = 120.0
MAX_FILE_SIZE_MB = 10  # Maximum file size in MB for uploads

semaphore = asyncio.Semaphore(MAX_CONCURRENCY)

# Simple in-memory cache for repeated requests
_response_cache: Dict[str, Dict[str, Any]] = {}
CACHE_MAX_SIZE = 100

def get_cache_key(decision_type: str, applicant: Dict[str, Any]) -> str:
    """Generate a hash key for caching based on input data"""
    data_str = f"{decision_type}:{json.dumps(applicant, sort_keys=True)}"
    return hashlib.md5(data_str.encode()).hexdigest()

def get_cached_response(key: str) -> Optional[Dict[str, Any]]:
    return _response_cache.get(key)

def set_cached_response(key: str, response: Dict[str, Any]):
    global _response_cache
    if len(_response_cache) >= CACHE_MAX_SIZE:
        # Remove oldest entry (simple FIFO)
        oldest = next(iter(_response_cache))
        del _response_cache[oldest]
    _response_cache[key] = response

# =====================================================
# FAST RULE-BASED ENGINE (Instant decisions)
# =====================================================
def fast_decision(decision_type: str, applicant: Dict[str, Any]) -> Dict[str, Any]:
    """Instant rule-based decision engine - no AI calls"""
    
    # Extract common fields (case-insensitive)
    data = {k.lower(): v for k, v in applicant.items()}
    
    score = 50  # Start neutral
    factors = []
    counterfactuals = []  # Will be numbered dynamically at the end
    detailed_analysis = []  # For longer explanation
    
    if decision_type == "loan":
        # Loan scoring rules
        # Try to get income - check for monthly_income first and convert to annual
        monthly_income = float(data.get("monthly_income", data.get("monthlyincome", 0)) or 0)
        if monthly_income > 0:
            annual_income = monthly_income * 12
            income_is_monthly = True
        else:
            annual_income = float(data.get("income", data.get("annual_income", data.get("applicantincome", 0))) or 0)
            income_is_monthly = False
        
        loan_amount = float(data.get("loan_amount", data.get("loanamount", data.get("amount", 10000))) or 10000)
        credit_score = float(data.get("credit_score", data.get("cibil_score", data.get("cibil score", 650))) or 650)
        
        # Display income appropriately
        display_income = monthly_income if income_is_monthly else annual_income
        income_period = "monthly" if income_is_monthly else "annual"
        
        # BNM Guidelines: Minimum income threshold RM3,000/month (RM36,000/year)
        # Good income: RM5,000/month (RM60,000/year), Excellent: RM10,000/month (RM120,000/year)
        MIN_ANNUAL_INCOME = 36000  # RM3,000/month as per BNM prudent lending guidelines
        GOOD_ANNUAL_INCOME = 60000  # RM5,000/month
        EXCELLENT_ANNUAL_INCOME = 120000  # RM10,000/month
        
        # Income analysis using annual income for consistent comparison
        if annual_income >= EXCELLENT_ANNUAL_INCOME:
            score += 20
            factors.append("High income")
            detailed_analysis.append(f"Your {income_period} income of RM{display_income:,.0f} (RM{annual_income:,.0f}/year) demonstrates strong financial capacity, placing you in our preferred income bracket for loan applicants.")
        elif annual_income >= GOOD_ANNUAL_INCOME:
            score += 15
            factors.append("Good income")
            detailed_analysis.append(f"Your {income_period} income of RM{display_income:,.0f} (RM{annual_income:,.0f}/year) shows solid financial standing and meets our standard requirements.")
        elif annual_income >= MIN_ANNUAL_INCOME:
            score += 5
            factors.append("Moderate income")
            detailed_analysis.append(f"Your {income_period} income of RM{display_income:,.0f} (RM{annual_income:,.0f}/year) meets the minimum requirement per Bank Negara Malaysia (BNM) guidelines, though higher income would improve your approval chances.")
        else:
            score -= 15
            factors.append("Low income")
            min_monthly = MIN_ANNUAL_INCOME / 12
            detailed_analysis.append(f"Your {income_period} income of RM{display_income:,.0f} (RM{annual_income:,.0f}/year) is below the minimum threshold of RM{min_monthly:,.0f}/month as per BNM prudent lending guidelines. This significantly impacts your debt service ratio (DSR) and loan repayment capacity.")
            counterfactuals.append(f"Increase your monthly income to at least RM{min_monthly:,.0f} through additional employment, side income, or by adding a co-applicant with higher income")
        
        # Credit score analysis
        if credit_score >= 700:
            score += 25
            factors.append("Excellent credit")
            detailed_analysis.append(f"Your credit score of {credit_score:.0f} is excellent, indicating a strong history of responsible credit management and timely payments.")
        elif credit_score >= 600:
            score += 10
            factors.append("Fair credit")
            detailed_analysis.append(f"Your credit score of {credit_score:.0f} is within acceptable range but not optimal. A score above 700 would qualify you for better interest rates.")
        else:
            score -= 20
            factors.append("Poor credit")
            detailed_analysis.append(f"Your credit score of {credit_score:.0f} is below our minimum threshold of 600. This indicates potential issues with credit history such as missed payments, high utilization, or recent derogatory marks.")
            counterfactuals.append("Improve your credit score above 650 by paying down existing debts, making all payments on time, and disputing any errors on your credit report")
        
        # Loan-to-income ratio analysis (BNM DSR Guidelines: typically max 60-70% DSR)
        # Using simplified loan-to-annual-income ratio as proxy
        MAX_LTI_RATIO = 5  # Max 5x annual income for personal loans
        lti_ratio = loan_amount / annual_income if annual_income > 0 else float('inf')
        if annual_income > 0 and loan_amount > annual_income * MAX_LTI_RATIO:
            score -= 15
            factors.append("High loan-to-income")
            detailed_analysis.append(f"The requested loan amount of RM{loan_amount:,.0f} represents a loan-to-income ratio of {lti_ratio:.1f}x your annual income (RM{annual_income:,.0f}), which exceeds BNM's prudent lending threshold of {MAX_LTI_RATIO}x annual income.")
            max_recommended_loan = annual_income * MAX_LTI_RATIO
            counterfactuals.append(f"Request a smaller loan amount (max RM{max_recommended_loan:,.0f} based on your income) or increase your income before reapplying")
        elif annual_income == 0:
            score -= 20
            factors.append("No verifiable income")
            detailed_analysis.append("No verifiable income was provided, making it impossible to assess your debt service capacity.")
            counterfactuals.append("Provide proof of income such as payslips, EPF statements, or income tax returns")
        
    elif decision_type == "credit":
        # Credit scoring rules
        age = float(data.get("age", data.get("days_birth", 0)) or 30)
        if age < 0: age = abs(age) / 365  # Convert negative days to years
        employed = data.get("employed", data.get("name_income_type", "")) != "Unemployed"
        
        # Handle monthly_income for credit too
        monthly_income = float(data.get("monthly_income", data.get("monthlyincome", 0)) or 0)
        if monthly_income > 0:
            annual_income = monthly_income * 12
        else:
            annual_income = float(data.get("income", data.get("annual_income", data.get("amt_income_total", 0))) or 0)
        
        # Credit score if provided
        credit_score = float(data.get("credit_score", data.get("cibil_score", data.get("cibil score", 0))) or 0)
        
        # BNM Guidelines for credit - similar thresholds
        if annual_income > 120000:
            score += 25
            factors.append("High income")
            detailed_analysis.append(f"Your annual income of RM{annual_income:,.0f} significantly exceeds our requirements, demonstrating excellent financial stability and repayment capacity.")
        elif annual_income > 60000:
            score += 15
            factors.append("Good income")
            detailed_analysis.append(f"Your income of RM{annual_income:,.0f}/year meets our credit requirements and indicates stable financial standing.")
        else:
            score -= 10
            detailed_analysis.append(f"Your reported income of RM{annual_income:,.0f}/year is below our preferred threshold for credit approval. Higher income improves credit limits and approval odds.")
            counterfactuals.append("Increase your annual income above RM60,000 to qualify for better credit terms and higher approval probability")
        
        if employed:
            score += 15
            factors.append("Employed")
            detailed_analysis.append("Your current employment status provides assurance of stable income flow for meeting credit obligations.")
        else:
            score -= 20
            factors.append("Unemployed")
            detailed_analysis.append("Being currently unemployed creates uncertainty about your ability to make regular credit payments. Employment stability is a key factor in credit decisions.")
            counterfactuals.append("Secure stable employment with verifiable income before reapplying for credit")
        
        # Credit score analysis
        if credit_score > 0:
            if credit_score >= 700:
                score += 20
                factors.append("Excellent credit score")
                detailed_analysis.append(f"Your credit score of {credit_score:.0f} demonstrates an excellent credit history and responsible financial behavior.")
            elif credit_score >= 600:
                score += 10
                factors.append("Good credit score")
                detailed_analysis.append(f"Your credit score of {credit_score:.0f} is within acceptable range for credit approval.")
            else:
                score -= 15
                factors.append("Low credit score")
                detailed_analysis.append(f"Your credit score of {credit_score:.0f} is below our preferred threshold of 600, indicating potential credit history issues.")
                counterfactuals.append("Improve your credit score above 650 by paying down existing debts, making all payments on time, and disputing any errors on your credit report")
        
        if 25 <= age <= 60:
            score += 10
            factors.append("Prime age")
            detailed_analysis.append(f"Your age of {age:.0f} years falls within our preferred demographic, typically associated with stable income and responsible credit behavior.")
        elif age < 25:
            detailed_analysis.append(f"At {age:.0f} years old, you have limited credit history which may affect approval. Building credit over time will improve future applications.")
            counterfactuals.append("Build a longer credit history by responsibly using a secured credit card or becoming an authorized user on an established account")
        
        
    elif decision_type == "insurance":
        # Insurance scoring rules
        age = float(data.get("age", data.get("customer_age", 35)) or 35)
        claims = int(data.get("claims", data.get("num_claims", data.get("past_claims", 0))) or 0)
        premium = float(data.get("premium", data.get("monthly_premium", 100)) or 100)
        
        if age < 30:
            score += 15
            factors.append("Young age")
            detailed_analysis.append(f"At {age:.0f} years old, you fall into a lower-risk age bracket with statistically fewer claims and health issues.")
        elif age > 60:
            score -= 10
            factors.append("Higher age risk")
            detailed_analysis.append(f"Your age of {age:.0f} years places you in a higher actuarial risk category, which affects premium calculations and coverage eligibility.")
            counterfactuals.append("Consider applying for senior-specific insurance plans designed for your age bracket with appropriate coverage options")
        else:
            detailed_analysis.append(f"Your age of {age:.0f} is within standard risk parameters for insurance coverage.")
        
        if claims == 0:
            score += 25
            factors.append("No prior claims")
            detailed_analysis.append("Your clean claims history demonstrates responsible usage of insurance and low risk profile, qualifying you for preferred rates.")
        elif claims <= 2:
            score += 5
            factors.append("Few claims")
            detailed_analysis.append(f"Your claims history shows {claims} previous claim(s), which is within acceptable limits but may affect your premium rates.")
            counterfactuals.append("Maintain a claim-free record going forward to gradually improve your risk profile and premium rates")
        else:
            score -= 20
            factors.append("Multiple claims")
            detailed_analysis.append(f"Your history of {claims} claims indicates higher-than-average risk. Multiple claims suggest patterns that insurers consider when assessing coverage and pricing.")
            counterfactuals.append("Maintain a claim-free record for at least 2 years to demonstrate lower risk and qualify for better rates")
        
        # Additional insurance-specific counterfactuals
        if premium > 500:
            detailed_analysis.append(f"Your current premium of RM{premium:.0f}/month reflects your risk profile and coverage level.")
            counterfactuals.append("Consider adjusting your coverage level or increasing deductibles to reduce monthly premiums")
        
    elif decision_type == "job":
        # Job application scoring
        experience = float(data.get("experience", data.get("years_experience", data.get("totalyearsexperience", 0))) or 0)
        education = str(data.get("education", data.get("degree", ""))).lower()
        skills_match = float(data.get("skills_match", data.get("skill_score", 70)) or 70)
        
        if experience >= 5:
            score += 25
            factors.append("Experienced")
            detailed_analysis.append(f"Your {experience:.0f} years of experience demonstrates proven expertise and industry knowledge that strongly supports your candidacy.")
        elif experience >= 2:
            score += 10
            factors.append("Some experience")
            detailed_analysis.append(f"With {experience:.0f} years of experience, you meet our minimum requirements, though candidates with 5+ years are typically preferred.")
        else:
            score -= 5
            detailed_analysis.append(f"Your experience of {experience:.0f} years is below our preferred threshold. We typically look for candidates with at least 2 years of relevant experience.")
            counterfactuals.append("Gain more industry experience through internships, projects, or entry-level positions before reapplying")
        
        if "master" in education or "phd" in education:
            score += 15
            factors.append("Advanced degree")
            detailed_analysis.append("Your advanced degree demonstrates significant academic achievement and specialized knowledge in your field.")
        elif "bachelor" in education:
            score += 10
            factors.append("Bachelor's degree")
            detailed_analysis.append("Your bachelor's degree meets our educational requirements for this position.")
        else:
            detailed_analysis.append("Consider obtaining relevant certifications or completing a degree program to strengthen your candidacy.")
        
        if skills_match >= 80:
            score += 20
            factors.append("Strong skills match")
            detailed_analysis.append(f"Your skills alignment score of {skills_match:.0f}% indicates an excellent match with the job requirements.")
        else:
            detailed_analysis.append(f"Your skills alignment score of {skills_match:.0f}% suggests some gaps with job requirements. Consider developing skills more closely aligned with the role.")
    
    # Clamp score
    score = max(0, min(100, score))
    
    # Decision threshold
    approved = score >= 55
    confidence = min(0.95, score / 100 + 0.1)
    
    # Number the counterfactuals dynamically (no gaps!)
    numbered_counterfactuals = [f"Step {i+1}: {cf}" for i, cf in enumerate(counterfactuals)]
    
    if not numbered_counterfactuals and not approved:
        numbered_counterfactuals = [
            "Step 1: Review and update your application details to ensure all information is accurate and complete",
            "Step 2: Provide additional supporting documentation such as pay stubs, tax returns, or employment verification",
            "Step 3: Contact our support team at support@example.com for a manual review of your application"
        ]
    
    # Build detailed reasoning
    if detailed_analysis:
        detailed_reasoning = " ".join(detailed_analysis)
    else:
        detailed_reasoning = "Standard evaluation criteria were applied to assess your application."
    
    summary_reasoning = f"Based on automated analysis: {', '.join(factors[:3]) if factors else 'Standard evaluation criteria applied'}. Risk score: {score}/100."
    full_reasoning = f"{summary_reasoning}\n\nDetailed Analysis:\n{detailed_reasoning}"
    
    # Generate alternative reasoning for when employee overrides the AI decision
    # This ensures logical, Bank Negara-compliant explanations are ready for both outcomes
    if approved:
        # If AI approved, generate a ready-made denial explanation for employee override
        denial_reasons = []
        denial_reasons.append("After manual review by our assessment officer, this application has been declined.")
        
        if decision_type == "loan":
            denial_reasons.append("While automated screening passed, additional scrutiny revealed concerns regarding debt serviceability under Bank Negara Malaysia (BNM) guidelines.")
            denial_reasons.append("Per BNM's Responsible Lending Guidelines, all loans must demonstrate sustainable repayment capacity considering total debt obligations.")
        elif decision_type == "credit":
            denial_reasons.append("Manual verification identified discrepancies or risks not captured by automated screening.")
            denial_reasons.append("Per credit policy, applications flagged for manual review require additional documentation or guarantees.")
        elif decision_type == "insurance":
            denial_reasons.append("Underwriting review identified risk factors requiring policy exclusions or higher premiums than standard coverage allows.")
            denial_reasons.append("Per insurance regulations, certain risk profiles require specialized underwriting assessment.")
        elif decision_type == "job":
            denial_reasons.append("After interview and reference check, the candidate profile did not align with current team requirements.")
            denial_reasons.append("While qualifications were met, cultural fit or specific skill gaps were identified during the review process.")
        
        alternative_reasoning = " ".join(denial_reasons)
        alternative_counterfactuals = [
            "Step 1: Request a detailed explanation from our customer service team regarding the specific concerns identified",
            "Step 2: Provide additional documentation such as proof of income, employment verification, or collateral",
            "Step 3: Wait 6 months and reapply with improved financial standing or additional supporting evidence"
        ]
    else:
        # If AI rejected, generate a ready-made approval explanation for employee override
        approval_reasons = []
        approval_reasons.append("After manual review by our assessment officer, this application has been approved with conditions.")
        
        if decision_type == "loan":
            approval_reasons.append(f"Despite automated screening concerns, manual verification confirmed adequate repayment capacity per BNM guidelines.")
            approval_reasons.append("Additional factors such as employment stability, savings history, or collateral support this approval.")
        elif decision_type == "credit":
            approval_reasons.append("Manual review of credit history and repayment patterns supports approval with monitored credit limit.")
            approval_reasons.append("Employment verification and income documentation sufficiently mitigate identified risks.")
        elif decision_type == "insurance":
            approval_reasons.append("Underwriting review approved coverage with standard terms after verifying health declarations.")
            approval_reasons.append("Risk factors identified are within acceptable limits for the selected coverage tier.")
        elif decision_type == "job":
            approval_reasons.append("Interview performance and references demonstrated potential that outweighs experience gaps.")
            approval_reasons.append("Candidate shows strong learning ability and cultural fit that supports hiring decision.")
        
        alternative_reasoning = " ".join(approval_reasons)
        alternative_counterfactuals = []  # No counterfactuals needed for approval
    
    return {
        "decision": {
            "status": "APPROVED" if approved else "REJECTED",
            "confidence": round(confidence, 2),
            "reasoning": full_reasoning
        },
        "counterfactuals": numbered_counterfactuals[:5],
        "fairness": {
            "assessment": "Fair",
            "concerns": "Automated rule-based evaluation"
        },
        "key_metrics": {
            "risk_score": 100 - score,
            "approval_probability": round(score / 100, 2),
            "critical_factors": factors[:3]
        },
        "alternative_reasoning": alternative_reasoning,
        "alternative_counterfactuals": alternative_counterfactuals
    }

# File paths
POLICIES_FILE = "../data/policies.json"
AI_MEMORY_FILE = "../data/ai_memory.json"
EXPLANATIONS_FILE = "../data/explanations.json"

# =====================================================
# ENUM (Swagger-stable)
# =====================================================
class DecisionType(str, Enum):
    loan = "loan"
    credit = "credit"
    insurance = "insurance"
    job = "job"

# =====================================================
# POLICY MEMORY (RAG-like)
# =====================================================
class PolicyMemory:
    def __init__(self, file_path: str = POLICIES_FILE):
        self.file_path = file_path
        self._ensure_file()
    
    def _ensure_file(self):
        if not os.path.exists(self.file_path):
            os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
            with open(self.file_path, "w") as f:
                json.dump({
                    "loan": [],
                    "credit": [],
                    "insurance": [],
                    "job": [],
                    "global": []
                }, f, indent=2)
    
    def _read_policies(self) -> Dict[str, List[Dict[str, Any]]]:
        try:
            with open(self.file_path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {"loan": [], "credit": [], "insurance": [], "job": [], "global": []}
    
    def _write_policies(self, policies: Dict[str, List[Dict[str, Any]]]):
        with open(self.file_path, "w") as f:
            json.dump(policies, f, indent=2)
    
    def add_policy(self, domain: str, policy_text: str) -> Dict[str, Any]:
        policies = self._read_policies()
        if domain not in policies:
            raise ValueError(f"Invalid domain: {domain}")
        
        policy_entry = {
            "id": str(uuid.uuid4())[:8],
            "text": policy_text,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        policies[domain].append(policy_entry)
        self._write_policies(policies)
        return policy_entry
    
    def get_policies(self, domain: Optional[str] = None) -> Dict[str, List[Dict[str, Any]]]:
        policies = self._read_policies()
        if domain:
            return {domain: policies.get(domain, [])}
        return policies
    
    def remove_policy(self, domain: str, policy_id: str) -> bool:
        policies = self._read_policies()
        if domain not in policies:
            return False
        
        original_length = len(policies[domain])
        policies[domain] = [p for p in policies[domain] if p["id"] != policy_id]
        
        if len(policies[domain]) < original_length:
            self._write_policies(policies)
            return True
        return False
    
    def get_relevant_policies(self, domain: str) -> str:
        """Get formatted policies for AI prompt injection"""
        policies = self._read_policies()
        domain_policies = policies.get(domain, [])
        global_policies = policies.get("global", [])
        
        all_policies = global_policies + domain_policies
        
        if not all_policies:
            return ""
        
        policy_text = "\n\nAPPLICABLE POLICIES AND RULES:\n"
        for i, policy in enumerate(all_policies, 1):
            policy_text += f"{i}. {policy['text']}\n"
        
        return policy_text

# =====================================================
# AI MEMORY (Decision History)
# =====================================================
class AIMemory:
    def __init__(self, file_path: str = AI_MEMORY_FILE, max_decisions: int = 50):
        self.file_path = file_path
        self.max_decisions = max_decisions
        self._ensure_file()
    
    def _ensure_file(self):
        if not os.path.exists(self.file_path):
            os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
            with open(self.file_path, "w") as f:
                json.dump({"decisions": []}, f, indent=2)
    
    def _read_memory(self) -> Dict[str, List[Dict[str, Any]]]:
        try:
            with open(self.file_path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {"decisions": []}
    
    def _write_memory(self, memory: Dict[str, List[Dict[str, Any]]]):
        with open(self.file_path, "w") as f:
            json.dump(memory, f, indent=2)
    
    def add_decision(self, decision_type: str, decision: str, reasoning: str):
        memory = self._read_memory()
        
        decision_entry = {
            "type": decision_type,
            "decision": decision,
            # Store full reasoning; we'll truncate only when building context
            "reasoning": reasoning,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        memory["decisions"].insert(0, decision_entry)
        
        # Keep only recent decisions
        if len(memory["decisions"]) > self.max_decisions:
            memory["decisions"] = memory["decisions"][:self.max_decisions]
        
        self._write_memory(memory)
    
    def get_context(self, decision_type: str, limit: int = 5) -> str:
        """Get recent decision context for AI prompt"""
        memory = self._read_memory()
        decisions = [d for d in memory["decisions"] if d["type"] == decision_type][:limit]
        
        if not decisions:
            return ""
        
        context = "\n\nRECENT SIMILAR DECISIONS:\n"
        for i, dec in enumerate(decisions, 1):
            snippet = dec["reasoning"][:400] if dec.get("reasoning") else ""
            context += f"{i}. {dec['decision']}: {snippet}\n"
        
        return context

# Initialize memory systems
policy_memory = PolicyMemory()
ai_memory = AIMemory()

# =====================================================
# EXPLANATION STORE (Full AI Outputs)
# =====================================================
class ExplanationStore:
    def __init__(self, file_path: str = EXPLANATIONS_FILE, max_entries: int = 200):
        self.file_path = file_path
        self.max_entries = max_entries
        self._ensure_file()

    def _ensure_file(self):
        if not os.path.exists(self.file_path):
            os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
            with open(self.file_path, "w") as f:
                json.dump({"explanations": []}, f, indent=2)

    def _read_store(self) -> Dict[str, List[Dict[str, Any]]]:
        try:
            with open(self.file_path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {"explanations": []}

    def _write_store(self, data: Dict[str, List[Dict[str, Any]]]):
        with open(self.file_path, "w") as f:
            json.dump(data, f, indent=2)

    def add_explanation(self, decision_type: str, applicant: Dict[str, Any], ai_output: Dict[str, Any]) -> Dict[str, Any]:
        data = self._read_store()

        entry = {
            "id": str(uuid.uuid4())[:8],
            "type": decision_type,
            "applicant": applicant,
            "decision": ai_output.get("decision", {}),
            "counterfactuals": ai_output.get("counterfactuals", []),
            "fairness": ai_output.get("fairness", {}),
            "key_metrics": ai_output.get("key_metrics", {}),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        data["explanations"].insert(0, entry)

        if len(data["explanations"]) > self.max_entries:
            data["explanations"] = data["explanations"][: self.max_entries]

        self._write_store(data)
        return entry


explanation_store = ExplanationStore()

# =====================================================
# PROMPT
# =====================================================
def format_as_text(data: Dict[str, Any]) -> str:
    """
    Convert dict data to a concise text format (key: value) for the AI prompt.
    This reduces token usage and improves AI processing speed compared to JSON.
    Handles nested dictionaries, lists, and None values properly.
    """
    lines = []
    for key, value in data.items():
        # Format the key to be more readable
        readable_key = key.replace('_', ' ').title()
        
        # Handle different value types
        if value is None:
            formatted_value = "N/A"
        elif isinstance(value, dict):
            # For nested dicts, use JSON representation
            formatted_value = json.dumps(value)
        elif isinstance(value, list):
            # For lists, join items with commas
            formatted_value = ", ".join(str(item) for item in value)
        else:
            formatted_value = str(value)
            
        lines.append(f"{readable_key}: {formatted_value}")
    return "\n".join(lines)


def build_prompt(decision_type: DecisionType, applicant: Dict[str, Any]) -> str:
    # Get relevant policies (skip history for speed)
    policies = policy_memory.get_relevant_policies(decision_type.value)
    applicant_text = format_as_text(applicant)
    
    # Compact prompt - reduces tokens significantly
    return f"""You are a {decision_type.value} decision engine. Output JSON only.
Evaluate this application and decide APPROVED or REJECTED.

DATA:
{applicant_text}{policies}

OUTPUT FORMAT:
{{"decision":{{"status":"APPROVED/REJECTED","confidence":0.0-1.0,"reasoning":"2-3 sentence explanation"}},"counterfactuals":["Step 1:...","Step 2:...","Step 3:..."],"fairness":{{"assessment":"Fair/Unfair","concerns":"brief"}},"key_metrics":{{"risk_score":0-100,"approval_probability":0.0-1.0,"critical_factors":["f1","f2"]}}}}

RULES: If REJECTED, list 3 actionable steps. If APPROVED, counterfactuals can be empty."""

# =====================================================
# OVERRIDE PROMPT
# =====================================================
def build_override_prompt(
    decision_type: DecisionType,
    applicant: Dict[str, Any],
    ai_recommendation: str,
    agent_decision: str,
    agent_comment: Optional[str] = None
) -> str:
    return f"""
SYSTEM:
You are an explainable AI system helping to explain why a human agent overrode your recommendation.
You MUST output JSON only.

CONTEXT:
- Application Type: {decision_type.value}
- Your AI Recommendation: {ai_recommendation}
- Agent's Final Decision: {agent_decision}
- Agent's Comment: {agent_comment or "None provided"}

APPLICANT DATA:
{json.dumps(applicant, indent=2)}

TASK:
Generate a customer-friendly explanation for why the agent overrode your recommendation.
Include:
1. Summary of the override
2. Reasoning for the agent's decision
3. Next steps for the customer
4. Conditions or requirements if applicable

OUTPUT (STRICT JSON ONLY):
{{
  "summary": "Brief explanation of the override decision",
  "detailed_reasoning": "Comprehensive explanation",
  "next_steps": ["step1", "step2"],
  "conditions": ["condition1", "condition2"],
  "override_context": "Why the human decision differed from AI"
}}
"""

# =====================================================
# JSON EXTRACTION (CRASH-PROOF)
# =====================================================
def extract_json(text: str) -> Dict[str, Any]:
    # Try multiple regex patterns for robustness
    patterns = [
        r"\{.*\}",  # Standard pattern
        r"```json\s*(\{.*?\})\s*```",  # Markdown code block
        r"```\s*(\{.*?\})\s*```",  # Generic code block
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            try:
                json_str = match.group(1) if len(match.groups()) > 0 else match.group()
                return json.loads(json_str)
            except json.JSONDecodeError:
                continue
    
    # Fallback response
    print(f"DEBUG: Parsing failed for text: {text[:200]}")
    return {
        "decision": {
            "status": "REJECTED",
            "confidence": 0.5,
            "reasoning": "Model output invalid or incomplete - System Error"
        },
        "counterfactuals": [
            "Ensure all application fields are filled correctly.",
            "Verify income and employment details.",
            "Contact support for manual review."
        ],
        "fairness": {
            "assessment": "Unknown",
            "concerns": "Processing Error"
        },
        "key_metrics": {
            "risk_score": 50,
            "approval_probability": 0.0,
            "critical_factors": ["Invalid AI response"]
        }
    }


def normalize_counterfactuals(raw_cf: Any) -> List[str]:
    """Clean and standardize counterfactual list coming back from the model."""
    cleaned: List[str] = []

    if isinstance(raw_cf, str):
        # Split on newlines or semicolons if model packed into one string
        candidates = [part.strip() for part in re.split(r"[\n;]+", raw_cf) if part.strip()]
    elif isinstance(raw_cf, list):
        candidates = []
        for item in raw_cf:
            if isinstance(item, str):
                candidates.append(item.strip())
            else:
                try:
                    candidates.append(str(item).strip())
                except Exception:
                    continue
    else:
        candidates = []

    for idx, text in enumerate(candidates, start=1):
        if not text:
            continue
        # Enforce "Step N:" prefix
        if not text.lower().startswith("step "):
            text = f"Step {idx}: {text}"
        cleaned.append(text)
        if len(cleaned) >= 5:
            break

    return cleaned

# =====================================================
# OLLAMA CALL (NEVER CRASHES)
# =====================================================
async def call_ai(prompt: str) -> Dict[str, Any]:
    async with semaphore:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            try:
                print(f"DEBUG: Call AI with model {MODEL_NAME}...")
                response = await client.post(
                    OLLAMA_URL,
                    json={
                        "model": MODEL_NAME, 
                        "prompt": prompt, 
                        "stream": False,
                        "format": "json",  # FORCE JSON MODE
                        "options": OLLAMA_OPTIONS  # Performance tuning
                    }
                )
                response.raise_for_status()
            except Exception as e:
                print(f"ERROR: AI Call Failed: {e}")
                return extract_json("")

    raw = response.json().get("response", "")
    print(f"DEBUG: AI Output: {raw[:100]}...") # Print first 100 chars
    return extract_json(raw)

# =====================================================
# DECISION ENGINE
# =====================================================
async def ai_decision(decision_type: DecisionType, applicant: Dict[str, Any]):
    # Check cache first for repeated requests
    cache_key = get_cache_key(decision_type.value, applicant)
    cached = get_cached_response(cache_key)
    if cached:
        print(f"DEBUG: Cache HIT for {decision_type.value}")
        # Update timestamp for cached response
        cached["audit"]["timestamp"] = datetime.now(timezone.utc).isoformat()
        cached["audit"]["cached"] = True
        return cached
    
    # FAST MODE: Use instant rule-based decisions
    if FAST_MODE:
        print(f"DEBUG: FAST MODE - rule-based decision for {decision_type.value}")
        ai_output = fast_decision(decision_type.value, applicant)
    else:
        ai_output = await call_ai(build_prompt(decision_type, applicant))
        # Normalize counterfactuals for consistent frontend experience
        try:
            raw_cf = ai_output.get("counterfactuals", [])
            ai_output["counterfactuals"] = normalize_counterfactuals(raw_cf)
        except Exception as e:
            print(f"WARNING: Failed to normalize counterfactuals: {e}")

    # Store decision in memory for future context
    decision_status = ai_output["decision"]["status"]
    decision_reasoning = ai_output["decision"]["reasoning"]
    ai_memory.add_decision(decision_type.value, decision_status, decision_reasoning)

    # Persist full explanation payload for auditing and analytics
    try:
        explanation_store.add_explanation(decision_type.value, applicant, ai_output)
    except Exception as e:
        # Do not let storage failures break decision flow
        print(f"WARNING: Failed to store explanation: {e}")

    result = {
        "decision_type": decision_type.value,
        "applicant": applicant,
        "decision": ai_output["decision"],
        "counterfactuals": ai_output.get("counterfactuals", []),
        "fairness": ai_output["fairness"],
        "key_metrics": ai_output.get("key_metrics", {
            "risk_score": 50,
            "approval_probability": 0.5,
            "critical_factors": []
        }),
        # Include pre-generated reasoning for employee override scenarios
        "alternative_reasoning": ai_output.get("alternative_reasoning", ""),
        "alternative_counterfactuals": ai_output.get("alternative_counterfactuals", []),
        "audit": {
            "engine": "universal-xai-http",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    }
    
    # Cache the result
    set_cached_response(cache_key, result)
    return result

# =====================================================
# BATCH (PARALLEL, OPTIMIZED)
# =====================================================
async def process_batch(decision_type: DecisionType, applicants: List[Dict[str, Any]]):
    # Process in parallel batches of 5
    batch_size = 5
    results = []
    
    for i in range(0, len(applicants), batch_size):
        batch = applicants[i:i + batch_size]
        batch_results = await asyncio.gather(
            *[ai_decision(decision_type, applicant) for applicant in batch]
        )
        results.extend(batch_results)
    
    return results

# =====================================================
# ENDPOINTS (Swagger-perfect)
# =====================================================
# =====================================================
# DATABASE
# =====================================================
from database import SimpleDB
db = SimpleDB()

# =====================================================
# ENDPOINTS (Swagger-perfect)
# =====================================================
@app.post("/decision/json")
async def decision_json(
    decision_type: DecisionType = Query(...),
    payload: Dict[str, Any] = ...
):
    return await ai_decision(decision_type, payload)


@app.post("/decision/batch/json")
async def decision_batch_json(
    decision_type: DecisionType = Query(...),
    payload: List[Dict[str, Any]] = ...
):
    if len(payload) > MAX_CSV_ROWS:
        raise HTTPException(400, f"Max {MAX_CSV_ROWS} records allowed")

    results = await process_batch(decision_type, payload)
    return {"count": len(results), "results": results}


@app.post("/decision/csv")
async def decision_csv(
    decision_type: DecisionType = Query(...),
    file: UploadFile = File(...)
):
    content = await file.read()
    df = pd.read_csv(BytesIO(content))

    if len(df) > MAX_CSV_ROWS:
        raise HTTPException(400, "CSV too large")

    applicants = df.to_dict(orient="records")
    results = await process_batch(decision_type, applicants)
    return {"count": len(results), "results": results}


@app.post("/decision/form/loan")
async def decision_loan_form(
    applicant_id: int = Form(...),
    age: int = Form(...),
    monthly_income: float = Form(...),
    existing_debt: float = Form(...),
    credit_score: int = Form(...),
    loan_amount: float = Form(...)
):
    return await ai_decision(
        DecisionType.loan,
        {
            "applicant_id": applicant_id,
            "age": age,
            "monthly_income": monthly_income,
            "existing_debt": existing_debt,
            "credit_score": credit_score,
            "loan_amount": loan_amount
        }
    )

# =====================================================
# NEW WORKFLOW ENDPOINTS
# =====================================================

class ApplicationStatus(str, Enum):
    PENDING_AI = "pending_ai"
    PENDING_HUMAN = "pending_human"
    APPROVED = "approved"
    REJECTED = "rejected"
    COMPLETED = "completed"

@app.post("/applications")
async def submit_application(
    decision_type: DecisionType = Query(...),
    payload: Dict[str, Any] = ...
):
    # 1. Save Initial Application
    app_entry = {
        "domain": decision_type.value,
        "data": payload,
        "status": ApplicationStatus.PENDING_AI.value
    }
    saved_app = db.save_application(app_entry)
    
    # 2. Run AI Analysis
    ai_result = await ai_decision(decision_type, payload)
    
    # 3. Update Application with AI Result
    updates = {
        "status": ApplicationStatus.PENDING_HUMAN.value,
        "ai_result": ai_result
    }
    updated_app = db.update_application(saved_app["id"], updates)
    
    return updated_app


@app.get("/applications")
async def get_applications(status: Optional[str] = None):
    return db.get_all_applications(status)

@app.get("/applications/{app_id}")
async def get_application(app_id: str):
    app = db.get_application(app_id)
    if not app:
        raise HTTPException(404, "Application not found")
    return app

@app.post("/applications/{app_id}/review")
async def review_application(
    app_id: str,
    decision: str = Query(..., pattern="^(approved|rejected)$"),
    comment: Optional[str] = None
):
    app = db.get_application(app_id)
    if not app:
        raise HTTPException(404, "Application not found")
    
    # Detect override scenario
    ai_decision = app.get("ai_result", {}).get("decision", {}).get("status", "").upper()
    agent_decision = decision.upper()
    
    is_override = False
    override_explanation = None
    
    # Case 3: AI says REJECTED but agent approves
    # Case 4: AI says APPROVED but agent rejects
    if (ai_decision == "REJECTED" and agent_decision == "APPROVED") or \
       (ai_decision == "APPROVED" and agent_decision == "REJECTED"):
        is_override = True
        
        # Generate override explanation
        try:
            decision_type = DecisionType(app["domain"])
            override_prompt = build_override_prompt(
                decision_type,
                app["data"],
                ai_decision,
                agent_decision,
                comment
            )
            override_result = await call_ai(override_prompt)
            override_explanation = override_result
        except Exception as e:
            # Fallback if AI fails
            override_explanation = {
                "summary": f"Agent overrode AI recommendation from {ai_decision} to {agent_decision}",
                "detailed_reasoning": comment or "Agent determined a different decision was appropriate",
                "next_steps": ["Contact support for more details"],
                "conditions": [],
                "override_context": "Human review superseded AI analysis"
            }
    
    updates = {
        "status": ApplicationStatus.COMPLETED.value,
        "final_decision": decision,
        "reviewer_comment": comment,
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "is_override": is_override,
        "override_explanation": override_explanation
    }
    
    updated_app = db.update_application(app_id, updates)
    return updated_app

# =====================================================
# POLICY MANAGEMENT ENDPOINTS
# =====================================================
@app.post("/policies")
async def add_policy(domain: str = Query(...), policy_text: str = Query(...)):
    """Add a new policy to the specified domain"""
    try:
        policy = policy_memory.add_policy(domain, policy_text)
        return {"success": True, "policy": policy}
    except ValueError as e:
        raise HTTPException(400, str(e))

@app.get("/policies")
async def get_policies(domain: Optional[str] = None):
    """Get all policies or policies for a specific domain"""
    return policy_memory.get_policies(domain)

@app.delete("/policies/{domain}/{policy_id}")
async def delete_policy(domain: str, policy_id: str):
    """Remove a policy from the specified domain"""
    success = policy_memory.remove_policy(domain, policy_id)
    if not success:
        raise HTTPException(404, "Policy not found")
    return {"success": True, "message": "Policy deleted"}

@app.post("/policies/upload")
async def upload_policy_file(
    domain: str = Query(...),
    file: UploadFile = File(...)
):
    """Upload policy file (CSV, JSON, TXT)"""
    try:
        content = await file.read()
        text_content = content.decode('utf-8')
        
        # Parse based on file type
        if file.filename.endswith('.json'):
            data = json.loads(text_content)
            # If it's a list of policies
            if isinstance(data, list):
                policies = []
                for policy_text in data:
                    if isinstance(policy_text, str):
                        policies.append(policy_memory.add_policy(domain, policy_text))
                    elif isinstance(policy_text, dict) and 'text' in policy_text:
                        policies.append(policy_memory.add_policy(domain, policy_text['text']))
                return {"success": True, "count": len(policies), "policies": policies}
            else:
                raise HTTPException(400, "JSON must be a list of policy strings or objects")
        
        elif file.filename.endswith('.csv'):
            # Assume CSV has a 'policy' column
            df = pd.read_csv(BytesIO(content))
            if 'policy' not in df.columns:
                raise HTTPException(400, "CSV must have a 'policy' column")
            policies = []
            for policy_text in df['policy']:
                policies.append(policy_memory.add_policy(domain, str(policy_text)))
            return {"success": True, "count": len(policies), "policies": policies}
        
        elif file.filename.endswith('.txt'):
            # Each line is a policy
            policies = []
            for line in text_content.split('\n'):
                line = line.strip()
                if line:
                    policies.append(policy_memory.add_policy(domain, line))
            return {"success": True, "count": len(policies), "policies": policies}
        
        else:
            raise HTTPException(400, "Unsupported file type. Use .json, .csv, or .txt")
    
    except Exception as e:
        raise HTTPException(400, f"Error processing file: {str(e)}")

# =====================================================
# EXPLANATION EDITOR ENDPOINT
# =====================================================
@app.put("/applications/{app_id}/explanation")
async def update_explanation(
    app_id: str,
    payload: Dict[str, Any]
):
    """Allow agents to edit AI-generated explanations"""
    app = db.get_application(app_id)
    if not app:
        raise HTTPException(404, "Application not found")
    
    updates = {
        "agent_explanation": payload.get("explanation"),
        "explanation_edited": True,
        "explanation_edited_at": datetime.now(timezone.utc).isoformat()
    }
    
    updated_app = db.update_application(app_id, updates)
    return updated_app

# =====================================================
# FILE PARSING HELPERS
# =====================================================
def safe_numeric_conversion(value: str) -> Any:
    """
    Safely convert a string to a number (int or float) if possible.
    Returns the original string if conversion fails.
    """
    value = value.strip()
    try:
        # Try integer first
        if '.' not in value:
            return int(value)
        # Try float - but validate it's a proper decimal number
        parts = value.split('.')
        if len(parts) == 2 and parts[0].lstrip('-').isdigit() and parts[1].isdigit():
            return float(value)
    except (ValueError, AttributeError):
        pass
    return value


def parse_key_value_text(text: str) -> Dict[str, Any]:
    """
    Parse text containing 'key: value' lines into a dictionary.
    Converts numeric values where appropriate.
    """
    parsed_data = {}
    lines = text.strip().split('\n')
    for line in lines:
        line = line.strip()
        if ':' in line:
            parts = line.split(':', 1)
            if len(parts) == 2:
                key = parts[0].strip().lower().replace(' ', '_')
                value = parts[1].strip()
                # Convert to number if possible
                parsed_data[key] = safe_numeric_conversion(value)
    return parsed_data


# =====================================================
# BULK UPLOAD ENDPOINT (OPTIMIZED, MULTI-FORMAT)
# =====================================================
@app.post("/bulk/upload")
async def bulk_upload(
    decision_type: DecisionType = Query(...),
    file: UploadFile = File(...)
):
    """
    Optimized bulk upload with parallel processing.
    Supports: .csv, .json, .pdf, .txt files
    """
    try:
        content = await file.read()
        filename = file.filename.lower() if file.filename else ""
        
        # Security: Check file size
        file_size_mb = len(content) / (1024 * 1024)
        if file_size_mb > MAX_FILE_SIZE_MB:
            raise HTTPException(400, f"File size ({file_size_mb:.1f}MB) exceeds maximum allowed ({MAX_FILE_SIZE_MB}MB)")
        
        applicants = []
        
        # Handle CSV files
        if filename.endswith('.csv'):
            df = pd.read_csv(BytesIO(content))
            if len(df) > MAX_CSV_ROWS:
                raise HTTPException(400, f"Max {MAX_CSV_ROWS} records allowed")
            applicants = df.to_dict(orient="records")
        
        # Handle JSON files
        elif filename.endswith('.json'):
            text_content = content.decode('utf-8')
            data = json.loads(text_content)
            
            # If it's a list, treat each item as an applicant
            if isinstance(data, list):
                applicants = data
            # If it's a single dict, treat it as one applicant
            elif isinstance(data, dict):
                applicants = [data]
            else:
                raise HTTPException(400, "JSON must be a list or object")
            
            if len(applicants) > MAX_CSV_ROWS:
                raise HTTPException(400, f"Max {MAX_CSV_ROWS} records allowed")
        
        # Handle PDF files
        elif filename.endswith('.pdf'):
            try:
                # Extract text from PDF
                pdf_reader = PdfReader(BytesIO(content))
                
                # Security: Limit number of pages to prevent memory exhaustion
                max_pages = 50
                if len(pdf_reader.pages) > max_pages:
                    raise HTTPException(400, f"PDF has too many pages (max {max_pages})")
                
                text_content = ""
                for page in pdf_reader.pages:
                    text_content += page.extract_text() + "\n"
                
                # Use helper function to parse key-value data
                parsed_data = parse_key_value_text(text_content)
                
                # If we found structured data, use it; otherwise pass as raw content
                if parsed_data:
                    applicants = [parsed_data]
                else:
                    # Truncate raw content to prevent excessive data
                    max_content_length = 5000
                    truncated_content = text_content[:max_content_length].strip()
                    applicants = [{"raw_content": truncated_content}]
                    
            except Exception as e:
                raise HTTPException(400, f"Error processing PDF: {str(e)}")
        
        # Handle TXT files
        elif filename.endswith('.txt'):
            text_content = content.decode('utf-8')
            
            # Use helper function to parse key-value data
            parsed_data = parse_key_value_text(text_content)
            
            # If we found structured data, use it; otherwise pass as raw content
            if parsed_data:
                applicants = [parsed_data]
            else:
                # Truncate raw content to prevent excessive data
                max_content_length = 5000
                truncated_content = text_content[:max_content_length].strip()
                applicants = [{"raw_content": truncated_content}]
        
        else:
            raise HTTPException(400, "Unsupported file type. Use .json, .csv, .pdf, or .txt")
        
        if not applicants:
            raise HTTPException(400, "No valid applicant data found in file")
        
        # Process in parallel batches
        results = await process_batch(decision_type, applicants)
        
        # Save to database
        saved_apps = []
        for i, result in enumerate(results):
            app_entry = {
                "domain": decision_type.value,
                "data": applicants[i],
                "status": ApplicationStatus.PENDING_HUMAN.value,
                "ai_result": result
            }
            saved_apps.append(db.save_application(app_entry))
        
        return {
            "success": True,
            "count": len(saved_apps),
            "file_type": filename.split('.')[-1] if '.' in filename else "unknown",
            "applications": saved_apps
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, f"Error processing bulk upload: {str(e)}")

# =====================================================
# AUDIT LOG ENDPOINT
# =====================================================
from fastapi.responses import JSONResponse

@app.get("/audit-log")
async def download_audit_log():
    """
    Download all applications as an audit log.
    Returns a JSON array of all applications with their review history.
    """
    all_apps = db._read_db()
    
    # Build audit log entries
    audit_log = []
    for app in all_apps:
        entry = {
            "application_id": app.get("id"),
            "domain": app.get("domain"),
            "submitted_at": app.get("timestamp"),
            "applicant_data": app.get("data", {}),
            "ai_decision": app.get("ai_result", {}).get("decision", {}).get("status"),
            "ai_confidence": app.get("ai_result", {}).get("decision", {}).get("confidence"),
            "ai_reasoning": app.get("ai_result", {}).get("decision", {}).get("reasoning"),
            "final_status": app.get("status"),
            "final_decision": app.get("final_decision"),
            "reviewed_at": app.get("reviewed_at"),
            "reviewer_comment": app.get("reviewer_comment"),
            "is_override": app.get("is_override", False),
            "override_explanation": app.get("override_explanation")
        }
        audit_log.append(entry)
    
    # Sort by timestamp descending (newest first)
    audit_log.sort(key=lambda x: x.get("submitted_at", ""), reverse=True)
    
    return JSONResponse(
        content=audit_log,
        headers={
            "Content-Disposition": "attachment; filename=audit_log.json"
        }
    )

# =====================================================
# HEALTH CHECK ENDPOINT
# =====================================================
@app.get("/health")
async def health_check():
    """Check AI model availability"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                OLLAMA_URL,
                json={"model": MODEL_NAME, "prompt": "test", "stream": False}
            )
            if response.status_code == 200:
                return {
                    "status": "healthy",
                    "model": MODEL_NAME,
                    "available": True
                }
            else:
                return {
                    "status": "degraded",
                    "model": MODEL_NAME,
                    "available": False,
                    "error": "Model not responding correctly"
                }
    except Exception as e:
        return {
            "status": "unhealthy",
            "model": MODEL_NAME,
            "available": False,
            "error": str(e)
        }

# =====================================================
# LEGACY/INQUIRY SUPPORT (Bridging api.py)
# =====================================================
@app.post("/inquiry")
async def submit_inquiry(payload: Dict[str, Any]):
    # Extract domain and data from legacy payload
    domain = payload.get("domain")
    data = payload.get("data")
    
    if not domain or not data:
        raise HTTPException(400, "Missing domain or data")
        
    try:
        decision_type = DecisionType(domain)
    except ValueError:
        raise HTTPException(400, f"Invalid domain: {domain}")

    # Reuse the submit_application logic
    # We call it directly (function call, not HTTP)
    app_id = str(uuid.uuid4())[:8]
    
    # 1. Save
    app_entry = {
        "id": app_id,
        "domain": domain,
        "data": data,
        "status": ApplicationStatus.PENDING_AI.value,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    saved_app = db.save_application(app_entry) # Ensure db.save_application handles ID generation if not provided, or accepts ID
    
    # 2. Run AI
    ai_result = await ai_decision(decision_type, data)
    
    # 3. Update
    updates = {
        "status": ApplicationStatus.PENDING_HUMAN.value,
        "ai_result": ai_result
    }
    updated_app = db.update_application(app_id, updates)
    
    return {
        "message": "Inquiry received",
        "inquiry_id": app_id,
        "result": updated_app
    }
