export type CaseData = {
	decision_id: string;
	domain: string;
	timestamp: string;
	input_features: any;
	model_output: { label: string; confidence: number | null; };
	explanation: { summary: string; };
	counterfactual: string;
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
	decision: string;
	summary: string;
};
