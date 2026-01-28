import axios from 'axios';
import { CaseData, ApplicationType, Application } from './types';

const API_BASE_URL = 'http://localhost:8000';

const client = axios.create({
	baseURL: API_BASE_URL,
	headers: { 'Content-Type': 'application/json' }
});

// Helper to transform backend app to frontend CaseData
const transform = (app: any): CaseData => {
	const aiReasoning = app.ai_result?.decision?.reasoning || "Pending AI analysis...";
	const reviewerComment = app.reviewer_comment ? `Auditor Note: ${app.reviewer_comment}` : "";

	return {
		decision_id: app.id,
		domain: app.domain,
		timestamp: app.timestamp || new Date().toISOString(),
		input_features: {
			...app.data,
			applicant_id: app.data.applicant_id || `ID: ${app.id.slice(0, 8)}`
		},
		model_output: {
			label: app.status === 'completed' ? (app.final_decision?.toUpperCase() || 'COMPLETED') : 'Pending',
			confidence: app.ai_result?.decision?.confidence || null
		},
		explanation: {
			summary: app.status === 'completed'
				? `${aiReasoning}${reviewerComment ? ` | ${reviewerComment}` : ""}`
				: `AI Suggestion: ${app.ai_result?.decision?.status || 'Processing'}. ${aiReasoning}`
		},
		counterfactual: app.ai_result?.counterfactuals ? JSON.stringify(app.ai_result.counterfactuals[0]) : "N/A",
		applicant_name: app.data?.full_name || app.data?.applicant_name,
		ai_result: app.ai_result
	};
};

export const submitApplication = async (type: ApplicationType, formData: any): Promise<any> => {
	const response = await client.post('/applications', formData, {
		params: { decision_type: type }
	});
	return response.data;
};

export const getApplications = async (status?: string): Promise<Application[]> => {
	try {
		const response = await client.get('/applications', {
			params: status ? { status } : {}
		});
		return response.data;
	} catch (e) {
		console.error("API Error", e);
		return [];
	}
};

export const getApplication = async (id: string): Promise<Application | null> => {
	try {
		const response = await client.get(`/applications/${id}`);
		return response.data;
	} catch (e) {
		return null;
	}
};

export const reviewApplication = async (
	id: string,
	decision: 'approved' | 'rejected',
	comment?: string
): Promise<Application> => {
	const response = await client.post(`/applications/${id}/review`, null, {
		params: {
			decision,
			comment
		}
	});
	return response.data;
};

export const updateExplanation = async (id: string, explanation: string): Promise<Application> => {
	const response = await client.put(`/applications/${id}/explanation`, {
		explanation
	});
	return response.data;
};

export const api = {
	// 1. Submit Application (Customer)
	submitApplication,

	// 2. Poll Status (Customer)
	getApplicationStatus: async (id: string, category: string): Promise<CaseData | null> => {
		try {
			const response = await client.get(`/applications/${id}`);
			return transform(response.data);
		} catch (e) {
			return null;
		}
	},

	// 3. Get All Applications (Employee)
	getApplications: async (): Promise<Record<string, CaseData[]>> => {
		try {
			const response = await client.get('/applications');
			const allApps = response.data;

			const results: Record<string, CaseData[]> = { loan: [], job: [], insurance: [], credit: [] };

			// Load static data from local files (if any exist in public)
			const domains = ['loan', 'job', 'insurance', 'credit'];
			const staticData = await Promise.all(
				domains.map(d =>
					fetch(`/${d}_decisions.json`)
						.then(res => res.json())
						.catch(() => [])
				)
			);

			// Merge static data first
			staticData.forEach((data, i) => {
				results[domains[i]] = [...data];
			});

			// Append and transform live backend data
			allApps.forEach((app: any) => {
				if (results[app.domain]) {
					results[app.domain].push(transform(app));
				}
			});
			return results;
		} catch (e) {
			console.error("API Error", e);
			return { loan: [], job: [], insurance: [], credit: [] };
		}
	},

	// 4. Update Status (Employee)
	updateApplicationStatus: async (id: string, category: string, status: 'Approved' | 'Denied', explanation: string): Promise<void> => {
		await client.post(`/applications/${id}/review`, null, {
			params: {
				decision: status.toLowerCase() === 'approved' ? 'approved' : 'rejected',
				comment: explanation
			}
		});
	}
};
