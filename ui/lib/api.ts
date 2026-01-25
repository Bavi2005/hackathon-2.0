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
    };
    final_decision?: string;
    reviewer_comment?: string;
    reviewed_at?: string;
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

export default api;
