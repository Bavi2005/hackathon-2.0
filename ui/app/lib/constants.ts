import { Users, Shield, CreditCard, TrendingUp } from 'lucide-react';
import { ApplicationType } from './types';

export const FORM_FIELDS: { [key: string]: Array<{ name: string, label: string, type: string, options?: string[] }> } = {
	loan: [
		{ name: 'full_name', label: 'Full Name', type: 'text' },
		{ name: 'age', label: 'What is your age?', type: 'number' },
		{ name: 'gender', label: 'What is your gender?', type: 'select', options: ['M', 'F', 'Other'] },
		{ name: 'marital_status', label: 'What is your marital status?', type: 'select', options: ['Single', 'Married', 'Divorced', 'Widowed'] },
		{ name: 'employment_years', label: 'How many years have you been employed?', type: 'number' },
		{ name: 'employment_type', label: 'What is your employment type?', type: 'select', options: ['Permanent', 'Contract', 'Self-Employed', 'Part-Time'] },
		{ name: 'monthly_income', label: 'What is your monthly income (RM)?', type: 'number' },
		{ name: 'existing_debt', label: 'What is your existing debt (RM)?', type: 'number' },
		{ name: 'credit_score', label: 'What is your credit score?', type: 'number' },
		{ name: 'loan_amount', label: 'What loan amount are you requesting (RM)?', type: 'number' },
		{ name: 'loan_purpose', label: 'What is the purpose of this loan?', type: 'select', options: ['Personal', 'Business', 'Education', 'Home', 'Vehicle'] },
	],
	job: [
		{ name: 'full_name', label: 'Full Name', type: 'text' },
		{ name: 'job_title', label: 'What job title are you applying for?', type: 'text' },
		{ name: 'years_experience', label: 'How many years of experience do you have?', type: 'number' },
		{ name: 'education_level', label: 'What is your highest education level?', type: 'select', options: ['High School', 'Diploma', 'Bachelor', 'Master', 'PhD'] },
		{ name: 'companies_worked', label: 'How many companies have you worked for?', type: 'number' },
		{ name: 'career_gaps', label: 'How many career gaps do you have?', type: 'number' },
		{ name: 'expected_salary', label: 'What is your expected salary (RM)?', type: 'number' },
	],
	insurance: [
		{ name: 'full_name', label: 'Full Name', type: 'text' },
		{ name: 'age', label: 'What is your age?', type: 'number' },
		{ name: 'policy_type', label: 'What type of policy do you have?', type: 'select', options: ['Health', 'Life', 'Vehicle', 'Property'] },
		{ name: 'policy_years', label: 'How many years have you held this policy?', type: 'number' },
		{ name: 'previous_claims', label: 'How many previous claims have you made?', type: 'number' },
		{ name: 'claim_amount', label: 'What is your claim amount (RM)?', type: 'number' },
		{ name: 'incident_severity', label: 'What is the incident severity?', type: 'select', options: ['minor', 'moderate', 'major', 'critical'] },
		{ name: 'location_type', label: 'What is your location type?', type: 'select', options: ['urban', 'suburban', 'rural'] },
		{ name: 'annual_premium', label: 'What is your annual premium (RM)?', type: 'number' },
	],
	credit: [
		{ name: 'full_name', label: 'Full Name', type: 'text' },
		{ name: 'customer_id', label: 'What is your customer ID?', type: 'text' },
		{ name: 'credit_score', label: 'What is your credit score?', type: 'number' },
		{ name: 'accounts_open', label: 'How many accounts do you have open?', type: 'number' },
		{ name: 'late_payments', label: 'How many late payments have you made?', type: 'number' },
		{ name: 'credit_utilization', label: 'What is your credit utilization ratio? (0.00 - 1.00)', type: 'number' },
		{ name: 'annual_income', label: 'What is your annual income (RM)?', type: 'number' },
		{ name: 'credit_history_years', label: 'How many years of credit history do you have?', type: 'number' },
		{ name: 'defaults', label: 'How many defaults do you have?', type: 'number' },
	]
};

export const CATEGORIES = [
	{ id: 'loan', title: 'Loan Applications', icon: CreditCard },
	{ id: 'job', title: 'Job Profiles', icon: Users },
	{ id: 'insurance', title: 'Insurance Claims', icon: Shield },
	{ id: 'credit', title: 'Credit History', icon: TrendingUp },
] as const;

export const CATEGORY_CONFIG: Record<string, { positive: string, negative: string, posLabel: string, negLabel: string }> = {
	credit: { positive: '#10b981', negative: '#ef4444', posLabel: 'Low Risk', negLabel: 'High Risk' },
	insurance: { positive: '#10b981', negative: '#f97316', posLabel: 'Approved', negLabel: 'Denied' },
	job: { positive: '#06b6d4', negative: '#ec4899', posLabel: 'Hired', negLabel: 'Rejected' },
	default: { positive: '#10b981', negative: '#ef4444', posLabel: 'Approved', negLabel: 'Declined' }
};
