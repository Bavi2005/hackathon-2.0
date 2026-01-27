export type CaseData = {
	decision_id: string;
	domain: string;
	timestamp: string;
	input_features: any;
	model_output: { label: string; confidence: number | null; };
	explanation: { summary: string; };
	counterfactual: string;
	applicant_name?: string;
};

export type PortalMode = 'customer' | 'employee' | null;
export type ApplicationType = 'loan' | 'job' | 'insurance' | 'credit' | null;

export type FormField = {
	name: string;
	label: string;
	type: string;
	options?: string[];
};

export type AiResultType = {
	decision: {
		status: string;
		confidence: number;
		reasoning: string;
	};
	alternative_reasoning?: string;
	counterfactuals?: string[];
	fairness?: {
		assessment: string;
		concerns: string;
	};
	key_metrics?: {
		risk_score: number;
		approval_probability: number;
		critical_factors: string[];
	};
};

export type Application = {
	id: string;
	domain: string;
	data: any;
	status: string;
	ai_result?: AiResultType;
	timestamp: string;
	final_decision?: string;
	reviewer_comment?: string;
	reviewed_at?: string;
	is_override?: boolean;
	override_explanation?: any;
};
