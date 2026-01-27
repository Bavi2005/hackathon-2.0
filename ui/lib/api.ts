import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000';

export interface Application {
    id: string;
    domain: string;
    data: any;
    status: 'pending_ai' | 'pending_human' | 'approved' | 'rejected' | 'completed';
    timestamp: string;
    ai_result?: {
        decision: {
            status: string;
            confidence: number;
            reasoning: string;
        };
        fairness: {
            assessment: string;
            concerns: string;
        };
        counterfactuals: any[];
        key_metrics?: {
            risk_score: number;
            approval_probability: number;
            critical_factors: string[];
        };
    };
    final_decision?: string;
    reviewer_comment?: string;
    reviewed_at?: string;
    is_override?: boolean;
    override_explanation?: {
        summary: string;
        detailed_reasoning: string;
        next_steps: string[];
        conditions: string[];
        override_context: string;
    };
    agent_explanation?: string;
    explanation_edited?: boolean;
}

const api = axios.create({
    baseURL: API_BASE_URL,
    headers: {
        'Content-Type': 'application/json',
    },
});

export const submitApplication = async (domain: string, data: any): Promise<Application> => {
    const response = await api.post('/applications', data, {
        params: { decision_type: domain },
    });
    return response.data;
};

export const getApplications = async (status?: string): Promise<Application[]> => {
    const response = await api.get('/applications', {
        params: { status },
    });
    return response.data;
};

export const getApplication = async (id: string): Promise<Application> => {
    const response = await api.get(`/applications/${id}`);
    return response.data;
};

export const reviewApplication = async (id: string, decision: 'approved' | 'rejected', comment?: string): Promise<Application> => {
    const response = await api.post(`/applications/${id}/review`, null, {
        params: { decision, comment },
    });
    return response.data;
};

export const getPolicies = async (domain?: string): Promise<any> => {
    const response = await api.get('/policies', {
        params: { domain },
    });
    return response.data;
};

export const addPolicy = async (domain: string, policyText: string): Promise<any> => {
    const response = await api.post('/policies', null, {
        params: { domain, policy_text: policyText },
    });
    return response.data;
};

export const deletePolicy = async (domain: string, policyId: string): Promise<any> => {
    const response = await api.delete(`/policies/${domain}/${policyId}`);
    return response.data;
};

export const uploadPolicyFile = async (domain: string, file: File): Promise<any> => {
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await api.post('/policies/upload', formData, {
        params: { domain },
        headers: {
            'Content-Type': 'multipart/form-data',
        },
    });
    return response.data;
};

export const updateExplanation = async (id: string, explanation: string): Promise<Application> => {
    const response = await api.put(`/applications/${id}/explanation`, {
        explanation,
    });
    return response.data;
};

export const bulkUploadApplications = async (domain: string, file: File): Promise<any> => {
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await api.post('/bulk/upload', formData, {
        params: { decision_type: domain },
        headers: {
            'Content-Type': 'multipart/form-data',
        },
    });
    return response.data;
};

export const checkHealth = async (): Promise<any> => {
    const response = await api.get('/health');
    return response.data;
};

export default api;
