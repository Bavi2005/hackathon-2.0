import React, { useState, useEffect } from 'react';
import { X, Plus, Trash2, Upload, FileText, Loader } from 'lucide-react';
import { getPolicies, addPolicy, deletePolicy, uploadPolicyFile } from '../../lib/api';

interface PolicyManagerProps {
    onClose: () => void;
}

type Domain = 'loan' | 'credit' | 'insurance' | 'job' | 'global';

const DOMAINS: { id: Domain; label: string }[] = [
    { id: 'loan', label: 'Loan' },
    { id: 'credit', label: 'Credit' },
    { id: 'insurance', label: 'Insurance' },
    { id: 'job', label: 'Job' },
    { id: 'global', label: 'Global' },
];

export default function PolicyManager({ onClose }: PolicyManagerProps) {
    const [activeDomain, setActiveDomain] = useState<Domain>('loan');
    const [policies, setPolicies] = useState<any>({});
    const [newPolicyText, setNewPolicyText] = useState('');
    const [loading, setLoading] = useState(false);
    const [dragActive, setDragActive] = useState(false);

    useEffect(() => {
        loadPolicies();
    }, []);

    const loadPolicies = async () => {
        try {
            const data = await getPolicies();
            setPolicies(data);
        } catch (error) {
            console.error('Error loading policies:', error);
        }
    };

    const handleAddPolicy = async () => {
        if (!newPolicyText.trim()) return;
        
        setLoading(true);
        try {
            await addPolicy(activeDomain, newPolicyText.trim());
            setNewPolicyText('');
            await loadPolicies();
        } catch (error) {
            console.error('Error adding policy:', error);
        } finally {
            setLoading(false);
        }
    };

    const handleDeletePolicy = async (policyId: string) => {
        setLoading(true);
        try {
            await deletePolicy(activeDomain, policyId);
            await loadPolicies();
        } catch (error) {
            console.error('Error deleting policy:', error);
        } finally {
            setLoading(false);
        }
    };

    const handleFileUpload = async (file: File) => {
        setLoading(true);
        try {
            await uploadPolicyFile(activeDomain, file);
            await loadPolicies();
        } catch (error) {
            console.error('Error uploading file:', error);
            alert('Error uploading file. Please check the format.');
        } finally {
            setLoading(false);
        }
    };

    const handleDrag = (e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        if (e.type === 'dragenter' || e.type === 'dragover') {
            setDragActive(true);
        } else if (e.type === 'dragleave') {
            setDragActive(false);
        }
    };

    const handleDrop = (e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        setDragActive(false);

        if (e.dataTransfer.files && e.dataTransfer.files[0]) {
            handleFileUpload(e.dataTransfer.files[0]);
        }
    };

    const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files[0]) {
            handleFileUpload(e.target.files[0]);
        }
    };

    const currentPolicies = policies[activeDomain] || [];

    return (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-8">
            <div className="bg-[#1a100e] border border-amber-900/50 rounded-3xl max-w-5xl w-full max-h-[90vh] overflow-hidden shadow-2xl">
                {/* Header */}
                <div className="bg-gradient-to-r from-amber-900/30 to-amber-800/20 border-b border-amber-900/50 p-6 flex items-center justify-between">
                    <div>
                        <h2 className="text-3xl font-black text-white">Policy Manager</h2>
                        <p className="text-sm text-amber-500/70 mt-1">Manage AI decision-making policies</p>
                    </div>
                    <button 
                        onClick={onClose}
                        className="p-3 hover:bg-amber-900/40 rounded-full text-amber-500 transition-all"
                    >
                        <X size={24} />
                    </button>
                </div>

                {/* Domain Tabs */}
                <div className="border-b border-amber-900/30 bg-[#291d1a]/50 px-6 flex gap-2 overflow-x-auto">
                    {DOMAINS.map(domain => (
                        <button
                            key={domain.id}
                            onClick={() => setActiveDomain(domain.id)}
                            className={`px-6 py-4 font-bold text-sm uppercase tracking-wider transition-all border-b-2 ${
                                activeDomain === domain.id
                                    ? 'border-amber-500 text-amber-500 bg-amber-500/10'
                                    : 'border-transparent text-amber-500/50 hover:text-amber-400 hover:bg-amber-900/20'
                            }`}
                        >
                            {domain.label}
                        </button>
                    ))}
                </div>

                {/* Content */}
                <div className="p-6 overflow-y-auto max-h-[calc(90vh-250px)]">
                    {/* Add Policy Section */}
                    <div className="mb-6">
                        <label className="block text-amber-500 font-bold text-sm mb-2 uppercase tracking-wider">
                            Add New Policy
                        </label>
                        <div className="flex gap-3">
                            <textarea
                                value={newPolicyText}
                                onChange={e => setNewPolicyText(e.target.value)}
                                placeholder="Enter policy text (e.g., 'Applicants with credit score below 600 should be rejected')"
                                className="flex-1 bg-[#291d1a]/50 border border-amber-900/30 rounded-xl px-4 py-3 text-amber-100 placeholder-amber-900/50 outline-none focus:border-amber-500 resize-none"
                                rows={3}
                                disabled={loading}
                            />
                            <button
                                onClick={handleAddPolicy}
                                disabled={loading || !newPolicyText.trim()}
                                className="px-6 py-3 bg-amber-500 hover:bg-amber-600 disabled:bg-amber-900/30 disabled:text-amber-900 text-white font-bold rounded-xl transition-all flex items-center gap-2 h-fit"
                            >
                                {loading ? <Loader size={20} className="animate-spin" /> : <Plus size={20} />}
                                Add
                            </button>
                        </div>
                    </div>

                    {/* File Upload Section */}
                    <div className="mb-6">
                        <label className="block text-amber-500 font-bold text-sm mb-2 uppercase tracking-wider">
                            Upload Policy File
                        </label>
                        <div
                            onDragEnter={handleDrag}
                            onDragLeave={handleDrag}
                            onDragOver={handleDrag}
                            onDrop={handleDrop}
                            className={`border-2 border-dashed rounded-xl p-8 text-center transition-all ${
                                dragActive
                                    ? 'border-amber-500 bg-amber-500/10'
                                    : 'border-amber-900/30 bg-[#291d1a]/30 hover:border-amber-500/50'
                            }`}
                        >
                            <input
                                type="file"
                                id="policy-file-input"
                                accept=".csv,.json,.txt"
                                onChange={handleFileInput}
                                className="hidden"
                                disabled={loading}
                            />
                            <label
                                htmlFor="policy-file-input"
                                className="cursor-pointer flex flex-col items-center gap-3"
                            >
                                <Upload size={40} className="text-amber-500/50" />
                                <div className="text-amber-500/70">
                                    <span className="font-bold">Click to upload</span> or drag and drop
                                </div>
                                <div className="text-xs text-amber-900">
                                    Supported: CSV, JSON, TXT
                                </div>
                            </label>
                        </div>
                    </div>

                    {/* Policies List */}
                    <div>
                        <label className="block text-amber-500 font-bold text-sm mb-3 uppercase tracking-wider">
                            Existing Policies ({currentPolicies.length})
                        </label>
                        {currentPolicies.length === 0 ? (
                            <div className="text-center py-12 text-amber-500/50">
                                <FileText size={48} className="mx-auto mb-3 opacity-30" />
                                <p className="font-bold">No policies defined for this domain</p>
                                <p className="text-xs mt-1">Add your first policy above</p>
                            </div>
                        ) : (
                            <div className="space-y-3">
                                {currentPolicies.map((policy: any, index: number) => (
                                    <div
                                        key={policy.id}
                                        className="bg-[#291d1a]/50 border border-amber-900/30 rounded-xl p-4 flex items-start gap-4 hover:border-amber-500/50 transition-all group"
                                    >
                                        <div className="flex-shrink-0 w-8 h-8 bg-amber-500/10 rounded-full flex items-center justify-center text-amber-500 font-bold text-sm">
                                            {index + 1}
                                        </div>
                                        <div className="flex-1">
                                            <p className="text-amber-100 leading-relaxed">{policy.text}</p>
                                            <p className="text-xs text-amber-900 mt-2">
                                                Added: {new Date(policy.created_at).toLocaleString()}
                                            </p>
                                        </div>
                                        <button
                                            onClick={() => handleDeletePolicy(policy.id)}
                                            disabled={loading}
                                            className="p-2 hover:bg-red-500/20 rounded-lg text-red-500/50 hover:text-red-500 transition-all opacity-0 group-hover:opacity-100"
                                        >
                                            <Trash2 size={18} />
                                        </button>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}
