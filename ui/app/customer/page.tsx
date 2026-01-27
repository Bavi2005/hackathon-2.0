"use client";

import React, { useState } from 'react';
import { ArrowLeft, CheckCircle2, Loader2, AlertCircle } from 'lucide-react';
import Link from 'next/link';
import { submitApplication } from '../../lib/api';

type Domain = 'loan' | 'credit' | 'insurance' | 'job';

export default function CustomerPortal() {
    const [domain, setDomain] = useState<Domain>('loan');
    const [loading, setLoading] = useState(false);
    const [success, setSuccess] = useState<any>(null);
    const [error, setError] = useState<string | null>(null);

    const [formData, setFormData] = useState<any>({});

    const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
        setFormData({ ...formData, [e.target.name]: e.target.value });
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        setError(null);
        setSuccess(null);

        try {
            // Ensure numeric fields are numbers
            const payload = { ...formData };
            ['age', 'monthly_income', 'existing_debt', 'credit_score', 'loan_amount', 'employment_years', 'annual_income', 'accounts_open', 'policy_years', 'claim_amount', 'annual_premium', 'years_experience', 'expected_salary'].forEach(field => {
                if (payload[field]) payload[field] = Number(payload[field]);
            });

            const result = await submitApplication(domain, payload);
            setSuccess(result);
        } catch (err: any) {
            console.error(err);
            setError(err.message || "Failed to submit application");
        } finally {
            setLoading(false);
        }
    };

    const renderFormFields = () => {
        switch (domain) {
            case 'loan':
                return (
                    <>
                        <div className="grid grid-cols-2 gap-4">
                            <Input name="age" label="Age" type="number" onChange={handleInputChange} required />
                            <Select name="gender" label="Gender" options={["M", "F", "Other"]} onChange={handleInputChange} required />
                        </div>
                        <Select name="marital_status" label="Marital Status" options={["Single", "Married", "Divorced"]} onChange={handleInputChange} required />
                        <div className="grid grid-cols-2 gap-4">
                            <Input name="employment_years" label="Years Employed" type="number" onChange={handleInputChange} required />
                            <Select name="employment_type" label="Employment Type" options={["Permanent", "Contract", "Self-Employed", "Unemployed"]} onChange={handleInputChange} required />
                        </div>
                        <Input name="monthly_income" label="Monthly Income ($)" type="number" onChange={handleInputChange} required />
                        <Input name="existing_debt" label="Existing Debt ($)" type="number" onChange={handleInputChange} required />
                        <Input name="credit_score" label="Credit Score" type="number" onChange={handleInputChange} required />
                        <Input name="loan_amount" label="Loan Amount Requested ($)" type="number" onChange={handleInputChange} required />
                        <Select name="loan_purpose" label="Purpose" options={["Home", "Vehicle", "Personal", "Education"]} onChange={handleInputChange} required />
                    </>
                );
            case 'job':
                return (
                    <>
                        <Input name="job_title" label="Job Title Applied For" onChange={handleInputChange} required />
                        <Input name="years_experience" label="Years of Experience" type="number" onChange={handleInputChange} required />
                        <Select name="education_level" label="Education Level" options={["High School", "Bachelor", "Master", "PhD"]} onChange={handleInputChange} required />
                        <Input name="companies_worked" label="Number of Previous Companies" type="number" onChange={handleInputChange} required />
                        <Input name="career_gaps" label="Career Gaps (Years)" type="number" onChange={handleInputChange} required />
                        <Input name="expected_salary" label="Expected Salary ($)" type="number" onChange={handleInputChange} required />
                    </>
                );
            case 'credit':
                return (
                    <>
                        <Input name="customer_id" label="Customer ID" onChange={handleInputChange} required />
                        <Input name="credit_score" label="Credit Score" type="number" onChange={handleInputChange} required />
                        <Input name="annual_income" label="Annual Income ($)" type="number" onChange={handleInputChange} required />
                        <Input name="accounts_open" label="Open Accounts" type="number" onChange={handleInputChange} required />
                        <Input name="credit_history_years" label="Credit History (Years)" type="number" onChange={handleInputChange} required />
                        <Input name="defaults" label="Number of Defaults" type="number" onChange={handleInputChange} required />
                    </>
                );
            case 'insurance':
                return (
                    <>
                        <Input name="age" label="Age" type="number" onChange={handleInputChange} required />
                        <Select name="policy_type" label="Policy Type" options={["Vehicle", "Home", "Health"]} onChange={handleInputChange} required />
                        <Input name="policy_years" label="Policy Duration (Years)" type="number" onChange={handleInputChange} required />
                        <Input name="previous_claims" label="Previous Claims" type="number" onChange={handleInputChange} required />
                        <Input name="claim_amount" label="Claim Amount ($)" type="number" onChange={handleInputChange} required />
                        <Select name="incident_severity" label="Incident Severity" options={["minor", "moderate", "severe"]} onChange={handleInputChange} required />
                    </>
                );
            default:
                return null;
        }
    };

    return (
        <div className="min-h-screen bg-neutral-950 text-white p-6 md:p-12">
            <div className="max-w-2xl mx-auto space-y-8">
                <Link href="/" className="flex items-center text-neutral-400 hover:text-white transition-colors w-fit">
                    <ArrowLeft className="w-4 h-4 mr-2" /> Back to Home
                </Link>

                {!success ? (
                    <>
                        <div className="space-y-4">
                            <h1 className="text-4xl font-bold bg-gradient-to-r from-blue-400 to-cyan-400 bg-clip-text text-transparent">
                                New Application
                            </h1>
                            <p className="text-neutral-400">Select the type of service you need and provide your details for instant AI assessment.</p>
                        </div>

                        <div className="flex p-1 bg-neutral-900 rounded-xl overflow-x-auto">
                            {(['loan', 'credit', 'insurance', 'job'] as Domain[]).map((d) => (
                                <button
                                    key={d}
                                    onClick={() => { setDomain(d); setFormData({}); setError(null); }}
                                    className={`flex-1 py-3 px-6 rounded-lg font-medium transition-all whitespace-nowrap ${domain === d
                                            ? 'bg-blue-600 text-white shadow-lg shadow-blue-500/20'
                                            : 'text-neutral-400 hover:text-white hover:bg-neutral-800'
                                        }`}
                                >
                                    {d.charAt(0).toUpperCase() + d.slice(1)}
                                </button>
                            ))}
                        </div>

                        <form onSubmit={handleSubmit} className="space-y-6 bg-neutral-900/50 p-8 rounded-2xl border border-neutral-800">
                             <div className="mb-4">
                                <label className="block text-slate-400 mb-2">Full Name</label>
                                <input
                                    type="text"
                                    name="full_name"
                                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-purple-500"
                                    onChange={handleInputChange}
                                    required
                                />
                            </div>
                            
                            {renderFormFields()}

                            {error && (
                                <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-xl flex items-center text-red-400">
                                    <AlertCircle className="w-5 h-5 mr-2" />
                                    {error}
                                </div>
                            )}

                            <button
                                type="submit"
                                disabled={loading}
                                className="w-full py-4 bg-blue-600 hover:bg-blue-500 rounded-xl font-bold shadow-lg shadow-blue-500/20 transition-all disabled:opacity-50 flex items-center justify-center"
                            >
                                {loading ? <Loader2 className="animate-spin w-5 h-5" /> : 'Submit Application'}
                            </button>
                        </form>
                    </>
                ) : (
                    <div className="bg-neutral-900 border border-neutral-800 rounded-3xl p-8 md:p-12 text-center space-y-6 animate-in fade-in slide-in-from-bottom-8">
                        <div className="w-20 h-20 bg-green-500/10 rounded-full flex items-center justify-center mx-auto text-green-500">
                            <CheckCircle2 size={40} />
                        </div>
                        <h2 className="text-3xl font-bold text-white">Application Received, {success.data?.full_name || 'Applicant'}</h2>
                        <div className="text-neutral-400 space-y-2">
                            <p>Your application ID is <span className="font-mono text-white bg-neutral-800 px-2 py-1 rounded">{success.id}</span></p>
                            <p>Our AI has processed your request and it is currently: <span className="text-blue-400 font-semibold">{success.status.replace('_', ' ').toUpperCase()}</span></p>
                        </div>

                        <div className="mt-8 p-6 bg-neutral-950 rounded-xl border border-neutral-800 text-left">
                            <h3 className="font-semibold text-white mb-2">AI Preliminary Feedback:</h3>
                            <p className="text-neutral-400 italic">"{success.ai_result?.decision?.reasoning || "Processing..."}"</p>
                        </div>

                        <button
                            onClick={() => { setSuccess(null); setFormData({}); }}
                            className="mt-8 px-8 py-3 bg-neutral-800 hover:bg-neutral-700 rounded-xl font-medium transition-colors"
                        >
                            Submit Another Application
                        </button>
                    </div>
                )}
            </div>
        </div>
    );
}

const Input = ({ label, ...props }: any) => (
    <div className="space-y-2">
        <label className="text-sm font-medium text-neutral-400">{label}</label>
        <input
            className="w-full bg-neutral-950 border border-neutral-800 rounded-lg px-4 py-3 focus:ring-2 focus:ring-blue-500 outline-none transition-all"
            {...props}
        />
    </div>
);

const Select = ({ label, options, ...props }: any) => (
    <div className="space-y-2">
        <label className="text-sm font-medium text-neutral-400">{label}</label>
        <select
            className="w-full bg-neutral-950 border border-neutral-800 rounded-lg px-4 py-3 focus:ring-2 focus:ring-blue-500 outline-none transition-all"
            {...props}
        >
            <option value="">Select...</option>
            {options.map((opt: string) => (
                <option key={opt} value={opt}>{opt}</option>
            ))}
        </select>
    </div>
);
