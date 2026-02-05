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
# HELPER FUNCTIONS FOR DYNAMIC EXPLANATION GENERATION
# =====================================================

def generate_rejection_reasons(decision_type, applicant: Dict[str, Any]) -> Dict[str, Any]:
    """Generate dynamic rejection reasons and counterfactuals based on applicant data"""
    data = {k.lower().replace(" ", "_"): v for k, v in applicant.items()}
    reasons = []
    counterfactuals = []
    detailed_analysis = []
    # Handle both enum and string types
    domain = decision_type.value.lower() if hasattr(decision_type, 'value') else decision_type.lower()
    
    if domain == "loan":
        # Check income
        monthly_income = float(data.get("monthly_income", data.get("monthlyincome", 0)) or 0)
        annual_income = monthly_income * 12 if monthly_income > 0 else float(data.get("income", data.get("annual_income", 0)) or 0)
        loan_amount = float(data.get("loan_amount", data.get("loanamount", 10000)) or 10000)
        credit_score = int(data.get("credit_score", data.get("cibil_score", data.get("cibil_score", 650))) or 650)
        existing_debt = float(data.get("existing_debt", data.get("existingdebt", 0)) or 0)
        
        # Debt-to-income ratio check
        if annual_income > 0:
            dti = (existing_debt + loan_amount * 0.05) / (annual_income / 12) * 100
            if dti > 50:
                reasons.append(f"Debt-to-income ratio of {dti:.0f}% exceeds the recommended 50% threshold per BNM guidelines")
                detailed_analysis.append(f"Your current debt obligations combined with the requested loan would result in a DTI of {dti:.0f}%, which exceeds the Bank Negara Malaysia recommended maximum of 50%. This indicates potential strain on your monthly finances.")
                counterfactuals.append("Reduce your existing debt by at least 20% before reapplying to improve your DTI ratio")
                counterfactuals.append("Consider applying for a smaller loan amount that results in a DTI below 50%")
        
        # Loan-to-income check
        if annual_income > 0 and loan_amount > annual_income * 5:
            ratio = loan_amount/annual_income
            reasons.append(f"Requested loan amount (RM{loan_amount:,.0f}) is {ratio:.1f}x annual income, exceeding prudent lending limits")
            detailed_analysis.append(f"The requested loan of RM{loan_amount:,.0f} is approximately {ratio:.1f} times your annual income of RM{annual_income:,.0f}. Prudent lending guidelines typically cap loans at 4-5x annual income.")
            counterfactuals.append(f"Increase your annual income to at least RM{loan_amount/5:,.0f} or reduce the loan request to RM{annual_income*4:,.0f}")
        
        # Credit score concerns
        if credit_score < 700:
            reasons.append(f"Credit score of {credit_score} indicates elevated risk requiring additional scrutiny")
            detailed_analysis.append(f"Your credit score of {credit_score} is below our preferred threshold of 700. This may indicate past credit difficulties or limited credit history.")
            counterfactuals.append("Improve your credit score by paying all bills on time for at least 6 months")
            counterfactuals.append("Reduce credit card utilization to below 30% of available limits")
            counterfactuals.append("Dispute any errors on your credit report with credit bureaus")
        
        # Income threshold
        if annual_income < 48000:  # RM4,000/month
            reasons.append(f"Annual income of RM{annual_income:,.0f} may not support repayment obligations")
            detailed_analysis.append(f"Your annual income of RM{annual_income:,.0f} (RM{annual_income/12:,.0f}/month) is below our minimum threshold for this loan type. This raises concerns about sustainable repayment capacity.")
            counterfactuals.append("Increase your monthly income through additional employment, side business, or career advancement")
            counterfactuals.append("Consider adding a co-applicant with stable income to strengthen the application")
            
        # Check employment
        employment = str(data.get("employment_status", data.get("employment", data.get("self_employed", "")))).lower()
        if employment in ["unemployed", "no", "0", "none"]:
            reasons.append("Employment status requires verification for income stability assessment")
            detailed_analysis.append("Your current employment status indicates potential income instability, which is a key factor in our lending assessment.")
            counterfactuals.append("Secure stable employment for at least 6 months before reapplying")
            counterfactuals.append("Provide documentation of alternative income sources such as rental income or investments")
            
    elif domain == "credit":
        credit_score = int(data.get("credit_score", data.get("score", 600)) or 600)
        utilization = float(data.get("credit_utilization", data.get("utilization", 0)) or 0)
        
        if credit_score < 650:
            reasons.append(f"Credit score of {credit_score} is below the minimum threshold for credit approval")
            detailed_analysis.append(f"Your credit score of {credit_score} does not meet our minimum requirement of 650 for this credit product.")
            counterfactuals.append("Focus on improving your credit score by making all payments on time")
            counterfactuals.append("Keep credit accounts open but maintain low balances to build positive history")
            
        if utilization > 70:
            reasons.append(f"Credit utilization of {utilization:.0f}% indicates high existing credit dependency")
            detailed_analysis.append(f"Your current credit utilization of {utilization:.0f}% suggests heavy reliance on existing credit. Lenders prefer utilization below 30%.")
            counterfactuals.append(f"Pay down existing credit balances to reduce utilization to below 30%")
        
        missed_payments = int(data.get("missed_payments", data.get("delinquencies", 0)) or 0)
        if missed_payments > 0:
            reasons.append(f"{missed_payments} missed payment(s) on record indicate payment reliability concerns")
            detailed_analysis.append(f"Your credit history shows {missed_payments} late or missed payment(s), which negatively impacts your creditworthiness assessment.")
            counterfactuals.append("Establish a 12-month history of on-time payments before reapplying")
            counterfactuals.append("Set up automatic payments to avoid future missed payments")
            
    elif domain == "insurance":
        age = int(data.get("age", 30) or 30)
        claims_history = int(data.get("claims", data.get("claims_history", data.get("previous_claims", 0))) or 0)
        risk_score = float(data.get("risk_score", data.get("risk", 50)) or 50)
        
        if age > 65:
            reasons.append(f"Age of {age} places applicant in higher risk category requiring enhanced underwriting")
            detailed_analysis.append(f"At {age} years of age, you fall into an elevated risk category that requires specialized underwriting assessment.")
            counterfactuals.append("Consider policies specifically designed for seniors with appropriate coverage levels")
        if claims_history > 2:
            reasons.append(f"Claims history of {claims_history} previous claims indicates elevated risk profile")
            detailed_analysis.append(f"Your history of {claims_history} claims in the reference period indicates higher-than-average risk.")
            counterfactuals.append("Maintain a claims-free record for 2-3 years to demonstrate improved risk profile")
            counterfactuals.append("Consider accepting a higher deductible to reduce premium and demonstrate confidence")
        if risk_score > 70:
            reasons.append(f"Risk assessment score of {risk_score:.0f} exceeds acceptable threshold")
            detailed_analysis.append(f"Your risk assessment score of {risk_score:.0f} exceeds our threshold for standard coverage.")
            counterfactuals.append("Address lifestyle factors that may be contributing to elevated risk scores")
            
    elif domain == "job":
        experience = int(data.get("years_experience", data.get("experience", data.get("experience_years", 0))) or 0)
        education = str(data.get("education", data.get("education_level", ""))).lower()
        skills_match = float(data.get("skills_match", data.get("skill_score", 50)) or 50)
        
        if experience < 2:
            reasons.append(f"{experience} years of experience is below the minimum requirement for this position")
            detailed_analysis.append(f"The position requires candidates with at least 2 years of relevant experience. Your {experience} years of experience, while valuable, does not meet this threshold.")
            counterfactuals.append("Gain additional experience through internships, freelance work, or junior-level positions")
            counterfactuals.append("Pursue relevant certifications to supplement practical experience")
        if skills_match < 60:
            reasons.append(f"Skills assessment score of {skills_match:.0f}% indicates gaps in required competencies")
            detailed_analysis.append(f"Your skills assessment score of {skills_match:.0f}% indicates that some required competencies may need development.")
            counterfactuals.append("Focus on developing key technical skills highlighted in the job requirements")
            counterfactuals.append("Consider taking online courses or workshops in areas where gaps were identified")
            counterfactuals.append("Build a portfolio demonstrating practical application of required skills")
    
    if not reasons:
        reasons.append("Additional verification requirements were not satisfactorily met during manual review")
        detailed_analysis.append("During the manual review process, certain aspects of your application required additional verification that could not be completed.")
        counterfactuals.append("Ensure all required documents are complete and accurate when reapplying")
        counterfactuals.append("Contact our support team for guidance on specific requirements")
    
    # Number the counterfactuals
    numbered_counterfactuals = [f"Step {i+1}: {cf}" for i, cf in enumerate(counterfactuals)]
    
    return {
        "reasons": " ".join(reasons),
        "detailed_analysis": " ".join(detailed_analysis) if detailed_analysis else "Standard evaluation criteria were applied during the review.",
        "counterfactuals": numbered_counterfactuals
    }


def generate_human_override_reasons(decision_type, applicant: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate reasons why a HUMAN reviewer might reject an AI-APPROVED application.
    This analyzes the data to find edge cases, borderline metrics, and concerns
    that require human judgment beyond automated thresholds.
    """
    data = {k.lower().replace(" ", "_"): v for k, v in applicant.items()}
    concerns = []
    detailed_analysis = []
    counterfactuals = []
    
    domain = decision_type.value.lower() if hasattr(decision_type, 'value') else decision_type.lower()
    
    if domain == "loan":
        monthly_income = float(data.get("monthly_income", data.get("monthlyincome", 0)) or 0)
        annual_income = monthly_income * 12 if monthly_income > 0 else float(data.get("income", data.get("annual_income", 0)) or 0)
        loan_amount = float(data.get("loan_amount", data.get("loanamount", 10000)) or 10000)
        credit_score = int(data.get("credit_score", data.get("cibil_score", 650)) or 650)
        employment_length = float(data.get("employment_length", data.get("years_employed", data.get("experience", 0))) or 0)
        loan_term = int(data.get("loan_term", data.get("term", 12)) or 12)
        
        lti_ratio = loan_amount / annual_income if annual_income > 0 else 0
        monthly_payment = loan_amount / loan_term if loan_term > 0 else loan_amount
        dti_ratio = (monthly_payment / monthly_income * 100) if monthly_income > 0 else 100
        
        # Borderline income concerns
        if 3000 <= monthly_income <= 4000:
            concerns.append("Borderline Income Level")
            detailed_analysis.append(f"While your monthly income of RM{monthly_income:,.0f} meets the minimum threshold, it is in the borderline range. Our assessment officer identified that after accounting for typical living expenses in your area, the remaining disposable income may not provide adequate buffer for loan repayment during financial emergencies.")
            counterfactuals.append(f"Increase your monthly income to at least RM5,000 by seeking additional income sources, a higher-paying position, or adding a co-applicant")
        
        # DTI ratio concerns (even if passing, near threshold)
        if 35 <= dti_ratio <= 50:
            concerns.append("High Debt Service Ratio")
            detailed_analysis.append(f"Your debt-to-income ratio of {dti_ratio:.1f}% is within acceptable limits but on the higher end. Manual review determined that this leaves limited financial flexibility, which increases the risk of payment difficulties if unexpected expenses arise.")
            counterfactuals.append(f"Reduce your debt-to-income ratio to below 30% by paying down existing debts or requesting a smaller loan amount (recommend RM{loan_amount * 0.7:,.0f} or less)")
        
        # Loan-to-income ratio concerns
        if 3.5 <= lti_ratio <= 5:
            concerns.append("Elevated Loan-to-Income Ratio")
            detailed_analysis.append(f"The loan amount of RM{loan_amount:,.0f} represents {lti_ratio:.1f}x your annual income. While this is within policy limits, our officer noted that loans above 3x annual income historically show higher default rates in similar applicant profiles.")
            counterfactuals.append(f"Consider a smaller loan amount of RM{annual_income * 3:,.0f} (3x annual income) for higher approval probability")
        
        # Employment stability
        if 1 <= employment_length <= 2:
            concerns.append("Limited Employment History")
            detailed_analysis.append(f"Your current employment tenure of {employment_length:.1f} years meets minimum requirements, but our assessment officer noted that longer employment history provides stronger evidence of income stability. This is particularly relevant given current economic conditions.")
            counterfactuals.append(f"Continue at your current employer for at least 2-3 years to demonstrate employment stability, then reapply")
        
        # Credit score edge cases
        if 650 <= credit_score <= 700:
            concerns.append("Fair Credit Score")
            detailed_analysis.append(f"Your credit score of {credit_score} is in the 'fair' range. While acceptable for automated approval, manual review identified recent credit activities that may indicate emerging financial stress not yet reflected in your score.")
            counterfactuals.append(f"Improve your credit score to above 750 by maintaining timely payments and reducing credit utilization below 30%")
        
        # If no specific concerns found, provide general human-judgment reasons
        if not concerns:
            concerns.append("Additional Verification Required")
            detailed_analysis.append(f"Although your application met automated screening criteria (income: RM{monthly_income:,.0f}/month, credit score: {credit_score}, loan amount: RM{loan_amount:,.0f}), our assessment officer identified discrepancies during document verification that require clarification. This includes potential inconsistencies between declared income and supporting documentation.")
            counterfactuals.append("Ensure all income documentation (payslips, bank statements, EA forms) accurately reflect your declared monthly income")
            counterfactuals.append("Provide additional verification documents such as employment letter, latest 6 months bank statements, and proof of other income sources if applicable")
            counterfactuals.append("Contact our customer service team to understand specific documentation requirements before reapplying")
    
    elif domain == "credit":
        credit_score = int(data.get("credit_score", data.get("cibil_score", 650)) or 650)
        annual_income = float(data.get("annual_income", data.get("income", 50000)) or 50000)
        num_accounts = int(data.get("num_credit_accounts", data.get("open_accounts", 0)) or 0)
        credit_utilization = float(data.get("credit_utilization", data.get("utilization", 30)) or 30)
        
        if 25 <= credit_utilization <= 40:
            concerns.append("Elevated Credit Utilization")
            detailed_analysis.append(f"Your credit utilization of {credit_utilization:.0f}% is within acceptable limits but indicates you're using a significant portion of available credit. Manual review suggests this pattern may indicate reliance on credit for regular expenses.")
            counterfactuals.append(f"Reduce your credit utilization to below 20% by paying down existing balances")
        
        if num_accounts > 5:
            concerns.append("Multiple Credit Accounts")
            detailed_analysis.append(f"You have {num_accounts} open credit accounts. While this isn't automatically disqualifying, our assessment officer noted that managing multiple accounts increases the risk of oversight and potential payment issues.")
            counterfactuals.append(f"Consider consolidating or closing {num_accounts - 3} accounts you use least frequently")
        
        if not concerns:
            concerns.append("Credit History Pattern Concerns")
            detailed_analysis.append(f"Manual review of your credit history (score: {credit_score}) identified patterns suggesting potential financial stress. While your score meets automated thresholds, recent inquiry patterns and account activity raised concerns about near-term creditworthiness.")
            counterfactuals.append("Maintain current credit accounts without opening new ones for 6 months")
            counterfactuals.append("Ensure all payments are made on or before due dates")
            counterfactuals.append("Reapply after demonstrating 6 months of stable credit behavior")
    
    elif domain == "insurance":
        age = int(data.get("age", 35) or 35)
        claims_history = int(data.get("claims_count", data.get("past_claims", 0)) or 0)
        risk_score = float(data.get("risk_score", 50) or 50)
        policy_type = data.get("policy_type", data.get("insurance_type", "general"))
        
        if 35 <= age <= 45:
            concerns.append("Age-Related Risk Assessment")
            detailed_analysis.append(f"At age {age}, you are entering a demographic bracket with statistically higher claim rates. While this doesn't disqualify you, our underwriter determined that the current premium structure doesn't adequately account for this elevated risk.")
            counterfactuals.append("Consider alternative policy structures with adjusted coverage that better match your risk profile")
        
        if claims_history >= 1:
            concerns.append("Claims History Review")
            detailed_analysis.append(f"Your record shows {claims_history} previous claim(s). Our underwriting team reviewed the nature of these claims and determined they indicate a pattern that increases future claim probability beyond acceptable thresholds.")
            counterfactuals.append(f"Maintain a claims-free record for at least 2 years before reapplying")
        
        if not concerns:
            concerns.append("Underwriting Risk Assessment")
            detailed_analysis.append(f"While your application passed automated screening, our underwriting team identified lifestyle or occupation factors that increase risk exposure beyond standard policy parameters. This assessment is based on comprehensive risk evaluation that considers factors not fully captured in the application form.")
            counterfactuals.append("Request a detailed risk assessment report from our underwriting team")
            counterfactuals.append("Consider applying for an alternative policy type with different coverage parameters")
            counterfactuals.append("Address any modifiable risk factors before reapplying in 6-12 months")
    
    else:  # job
        experience = float(data.get("experience", data.get("years_experience", 0)) or 0)
        skills_match = float(data.get("skills_match", data.get("skill_score", 70)) or 70)
        education = data.get("education", data.get("qualification", ""))
        
        if 60 <= skills_match <= 75:
            concerns.append("Partial Skills Alignment")
            detailed_analysis.append(f"Your skills assessment score of {skills_match:.0f}% indicates partial alignment with position requirements. While meeting minimum thresholds, our hiring manager identified specific technical competencies where additional development would be needed.")
            counterfactuals.append("Acquire certifications or training in the specific skills gaps identified for this role")
        
        if not concerns:
            concerns.append("Cultural Fit Assessment")
            detailed_analysis.append(f"While your qualifications met technical requirements (experience: {experience:.0f} years, skills match: {skills_match:.0f}%), our assessment indicated potential misalignment with team dynamics or organizational culture. This determination was made through comprehensive evaluation of your interview responses and assessment results.")
            counterfactuals.append("Research our company culture and values before reapplying")
            counterfactuals.append("Consider roles in different teams or departments that may be a better fit")
            counterfactuals.append("Request feedback from HR on specific areas for development")
    
    # Format counterfactuals with step numbers
    numbered_counterfactuals = [f"Step {i+1}: {cf}" for i, cf in enumerate(counterfactuals)]
    
    return {
        "concerns": concerns,
        "detailed_analysis": "\n\n".join(detailed_analysis) if detailed_analysis else "Manual review identified concerns requiring the application to be declined.",
        "counterfactuals": numbered_counterfactuals
    }


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
        # If AI approved, generate human-reviewer concerns for potential denial
        # Uses generate_human_override_reasons which finds edge cases and borderline metrics
        override_data = generate_human_override_reasons(decision_type, applicant)
        override_analysis = override_data["detailed_analysis"]
        override_counterfactuals = override_data["counterfactuals"]
        override_concerns = override_data["concerns"]
        
        concerns_summary = ", ".join(override_concerns) if override_concerns else "Additional verification concerns"
        alternative_reasoning = f"After manual review by our assessment officer, this application has been declined. While automated screening passed, additional scrutiny revealed the following concerns ({concerns_summary}):\n\n{override_analysis}"
        alternative_counterfactuals = override_counterfactuals if override_counterfactuals else [
            "Step 1: Address the specific concerns highlighted in the decision explanation",
            "Step 2: Provide additional supporting documentation",
            "Step 3: Reapply after improving your application profile"
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


def fast_override_explanation(
    decision_type: DecisionType,
    applicant: Dict[str, Any],
    ai_recommendation: str,
    agent_decision: str,
    agent_comment: Optional[str] = None
) -> Dict[str, Any]:
    """Instant rule-based override explanation - no AI calls"""
    
    domain = decision_type.value.lower()
    ai_rec = ai_recommendation.upper()
    agent_dec = agent_decision.upper()
    
    # Base explanation templates
    if ai_rec == "REJECTED" and agent_dec == "APPROVED":
        summary = f"Your {domain} application has been approved after manual review by our assessment officer."
        override_context = "After careful human review, additional factors were identified that support approval despite automated concerns."
        
        if domain == "loan":
            detailed_reasoning = agent_comment or "Manual verification confirmed adequate repayment capacity. Additional factors such as employment stability, savings history, or collateral support this approval per BNM guidelines."
            next_steps = [
                "Step 1: You will receive your loan agreement via email within 2-3 business days",
                "Step 2: Review and sign the agreement to finalize your loan",
                "Step 3: Funds will be disbursed within 5-7 business days after signing"
            ]
            conditions = [
                "Subject to final document verification",
                "Interest rate and terms as specified in the agreement"
            ]
        elif domain == "credit":
            detailed_reasoning = agent_comment or "Manual review found positive credit indicators not captured in automated screening, supporting approval."
            next_steps = [
                "Step 1: Your credit application is approved",
                "Step 2: Await final documentation via email",
                "Step 3: Contact us if you have any questions"
            ]
            conditions = ["Subject to final verification"]
        elif domain == "insurance":
            detailed_reasoning = agent_comment or "Manual underwriting review identified mitigating factors that support policy issuance."
            next_steps = [
                "Step 1: Your insurance application is approved",
                "Step 2: Policy documents will be sent within 3-5 business days",
                "Step 3: Premium payment details will be included"
            ]
            conditions = ["Subject to policy terms and conditions", "Premium rates as quoted"]
        else:  # job
            detailed_reasoning = agent_comment or "Manual review confirmed candidate qualifications meet position requirements."
            next_steps = [
                "Step 1: Proceed to the next interview stage",
                "Step 2: HR will contact you with further details"
            ]
            conditions = ["Subject to background verification"]
        
        return {
            "summary": summary,
            "detailed_reasoning": detailed_reasoning,
            "next_steps": next_steps,
            "conditions": conditions,
            "override_context": override_context,
            "counterfactuals": next_steps
        }
    
    else:  # AI approved but agent rejected - GENERATE DYNAMIC REASONS
        summary = f"Your {domain} application has been declined after manual review by our assessment officer."
        override_context = "While automated screening passed, additional scrutiny during manual review identified concerns that require the application to be declined at this time."
        
        # Generate HUMAN OVERRIDE reasons - concerns a human reviewer might have even when AI approved
        override_data = generate_human_override_reasons(decision_type, applicant)
        detailed_analysis = override_data["detailed_analysis"]
        counterfactuals = override_data["counterfactuals"]
        concerns = override_data["concerns"]
        
        concerns_text = ", ".join(concerns) if concerns else "Additional verification concerns"
        
        if domain == "loan":
            detailed_reasoning = agent_comment or f"Upon closer review of your application by our assessment officer, the following concerns were identified ({concerns_text}):\n\n{detailed_analysis}\n\nThese factors require us to decline your loan application at this time per Bank Negara Malaysia (BNM) prudent lending guidelines. We understand this may be disappointing, and we've provided specific steps below to help you improve your chances in future applications."
            next_steps = counterfactuals if counterfactuals else [
                "Step 1: Review and address the concerns mentioned above",
                "Step 2: Improve your debt-to-income ratio by reducing existing debts",
                "Step 3: Reapply after 90 days with updated financial information"
            ]
            conditions = []
        elif domain == "credit":
            detailed_reasoning = agent_comment or f"Manual review identified the following factors ({concerns_text}) that prevent credit approval at this time:\n\n{detailed_analysis}\n\nPlease review the improvement steps below to enhance your credit profile."
            next_steps = counterfactuals if counterfactuals else [
                "Step 1: Improve your credit score through timely payments",
                "Step 2: Reduce credit utilization below 30%",
                "Step 3: Reapply after 6 months with improved credit standing"
            ]
            conditions = []
        elif domain == "insurance":
            detailed_reasoning = agent_comment or f"Underwriting review identified the following risk factors ({concerns_text}):\n\n{detailed_analysis}\n\nThis risk profile requires us to decline coverage at this time."
            next_steps = counterfactuals if counterfactuals else [
                "Step 1: Maintain a claims-free record for at least 2 years",
                "Step 2: Address any lifestyle factors contributing to risk",
                "Step 3: Consider reapplying with updated information"
            ]
            conditions = []
        else:  # job
            detailed_reasoning = agent_comment or f"After careful evaluation by our hiring team, the following factors were considered ({concerns_text}):\n\n{detailed_analysis}\n\nWhile we appreciate your interest, we have decided to pursue other candidates whose qualifications more closely match our current requirements."
            next_steps = counterfactuals if counterfactuals else [
                "Step 1: Gain additional relevant experience in your field",
                "Step 2: Consider obtaining certifications in key skill areas",
                "Step 3: Apply for future openings that match your profile"
            ]
            conditions = []
    
    return {
        "summary": summary,
        "detailed_reasoning": detailed_reasoning,
        "next_steps": next_steps,
        "conditions": conditions,
        "override_context": override_context,
        "counterfactuals": next_steps  # Include counterfactuals for frontend access
    }


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


@app.post("/applications/batch_csv")
async def batch_csv_upload(
    decision_type: DecisionType = Query(...),
    file: UploadFile = File(...)
):
    """Batch process applications from CSV file"""
    content = await file.read()
    
    try:
        df = pd.read_csv(BytesIO(content))
    except Exception as e:
        raise HTTPException(400, f"Invalid CSV file: {str(e)}")
    
    if len(df) > MAX_CSV_ROWS:
        raise HTTPException(400, f"CSV too large. Maximum {MAX_CSV_ROWS} rows allowed.")
    
    if len(df) == 0:
        raise HTTPException(400, "CSV file is empty")
    
    applicants = df.to_dict(orient="records")
    saved_apps = []
    
    for applicant_data in applicants:
        # Save each application
        app_entry = {
            "domain": decision_type.value,
            "data": applicant_data,
            "status": ApplicationStatus.PENDING_AI.value
        }
        saved_app = db.save_application(app_entry)
        
        # Run AI analysis (fast mode is instant)
        ai_result = await ai_decision(decision_type, applicant_data)
        
        # Update with AI result
        updates = {
            "status": ApplicationStatus.PENDING_HUMAN.value,
            "ai_result": ai_result
        }
        updated_app = db.update_application(saved_app["id"], updates)
        saved_apps.append(updated_app)
    
    return {"count": len(saved_apps), "applications": saved_apps}


# Alias for frontend compatibility
@app.post("/applications/batch_upload")
async def batch_upload_alias(
    decision_type: DecisionType = Query(...),
    file: UploadFile = File(...)
):
    """Alias for batch_csv_upload for frontend compatibility"""
    return await batch_csv_upload(decision_type, file)


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
            
            # FAST MODE: Use instant rule-based explanation
            if FAST_MODE:
                print("DEBUG: FAST MODE - instant override explanation")
                override_explanation = fast_override_explanation(
                    decision_type,
                    app["data"],
                    ai_decision,
                    agent_decision,
                    comment
                )
            else:
                # Slow mode: Call AI for explanation
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
            # Fallback if anything fails
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

@app.delete("/clear-all-data")
async def clear_all_data():
    """
    Clear all application data from the database.
    This is a destructive operation - use with caution.
    """
    try:
        # Clear the database by writing an empty array
        db._write_db([])
        return {"success": True, "message": "All data has been cleared"}
    except Exception as e:
        raise HTTPException(500, f"Failed to clear data: {str(e)}")

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
