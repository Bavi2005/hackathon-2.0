import React, { useState, useEffect } from 'react';
import { X, Save, AlertTriangle, Loader, Plus, Trash2 } from 'lucide-react';
import { updateExplanation } from '../../lib/api';

interface ExplanationEditorProps {
    applicationId: string;
    currentExplanation: string;
    counterfactuals?: string[];
    isOverride?: boolean;
    onClose: () => void;
    onSave: () => void;
    onSubmit?: (text: string, counterfactuals: string[]) => Promise<void>;
}

export default function ExplanationEditor({ 
    applicationId, 
    currentExplanation, 
    counterfactuals: initialCounterfactuals = [],
    isOverride = false,
    onClose,
    onSave,
    onSubmit
}: ExplanationEditorProps) {
    const [explanation, setExplanation] = useState(currentExplanation);
    const [counterfactuals, setCounterfactuals] = useState<string[]>(
        initialCounterfactuals.length > 0 ? initialCounterfactuals : [
            "Review and address the factors mentioned above",
            "Provide additional supporting documentation",
            "Contact our support team if you have questions"
        ]
    );
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleSave = async () => {
        if (!explanation.trim()) {
            setError('Explanation cannot be empty');
            return;
        }

        setLoading(true);
        setError(null);
        try {
            // Get valid counterfactuals
            const validCounterfactuals = counterfactuals.filter(cf => cf.trim());
            const formattedCounterfactuals = validCounterfactuals
                .map((cf, i) => `Step ${i + 1}: ${cf.replace(/^Step \d+:\s*/i, '')}`)
                .join('\n');
            
            // For override submissions, send explanation and counterfactuals separately
            // The frontend will display them in separate sections
            if (onSubmit) {
                // Only send the explanation text, counterfactuals will be shown separately
                await onSubmit(explanation.trim(), validCounterfactuals);
            } else {
                // For non-override edits, combine them for the full explanation
                const fullExplanation = formattedCounterfactuals 
                    ? `${explanation.trim()}\n\nSteps to Improve:\n${formattedCounterfactuals}`
                    : explanation.trim();
                await updateExplanation(applicationId, fullExplanation);
            }
            onSave();
            onClose();
        } catch (err) {
            console.error('Error saving explanation:', err);
            setError('Failed to save explanation. Please try again.');
        } finally {
            setLoading(false);
        }
    };

    const addCounterfactual = () => {
        setCounterfactuals([...counterfactuals, '']);
    };

    const removeCounterfactual = (index: number) => {
        setCounterfactuals(counterfactuals.filter((_, i) => i !== index));
    };

    const updateCounterfactual = (index: number, value: string) => {
        const updated = [...counterfactuals];
        updated[index] = value;
        setCounterfactuals(updated);
    };

    return (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-8">
            <div className="bg-[#1a100e] border border-amber-900/50 rounded-3xl max-w-4xl w-full max-h-[90vh] overflow-hidden shadow-2xl flex flex-col">
                {/* Header */}
                <div className="bg-gradient-to-r from-amber-900/30 to-amber-800/20 border-b border-amber-900/50 p-6 flex-shrink-0">
                    <div className="flex items-center justify-between">
                        <div>
                            <h2 className="text-3xl font-black text-white">
                                {isOverride ? 'Override Decision' : 'Edit Explanation'}
                            </h2>
                            <p className="text-sm text-amber-500/70 mt-1">
                                Customize the explanation and improvement steps shown to customers
                            </p>
                        </div>
                        <button 
                            onClick={onClose}
                            className="p-3 hover:bg-amber-900/40 rounded-full text-amber-500 transition-all"
                        >
                            <X size={24} />
                        </button>
                    </div>

                    {/* Override Warning */}
                    {isOverride && (
                        <div className="mt-4 bg-orange-500/10 border border-orange-500/30 rounded-xl p-4 flex items-start gap-3">
                            <AlertTriangle size={20} className="text-orange-500 flex-shrink-0 mt-0.5" />
                            <div>
                                <p className="text-orange-500 font-bold text-sm">Override Decision</p>
                                <p className="text-orange-400/80 text-xs mt-1">
                                    This decision overrides the AI recommendation. Ensure the explanation is clear and justified.
                                </p>
                            </div>
                        </div>
                    )}
                </div>

                {/* Content - Scrollable */}
                <div className="p-6 overflow-y-auto flex-1">
                    {/* Main Explanation */}
                    <div className="mb-6">
                        <label className="block text-amber-500 font-bold text-sm mb-3 uppercase tracking-wider">
                            Decision Explanation
                        </label>
                        <textarea
                            value={explanation}
                            onChange={e => setExplanation(e.target.value)}
                            placeholder="Enter a clear, customer-friendly explanation of the decision..."
                            className="w-full bg-[#291d1a]/50 border border-amber-900/30 rounded-xl px-4 py-3 text-amber-100 placeholder-amber-900/50 outline-none focus:border-amber-500 resize-none"
                            rows={6}
                            disabled={loading}
                        />
                    </div>

                    {/* Counterfactuals / Steps to Improve */}
                    <div>
                        <div className="flex items-center justify-between mb-3">
                            <label className="block text-amber-500 font-bold text-sm uppercase tracking-wider">
                                Steps to Improve (Counterfactuals)
                            </label>
                            <button
                                onClick={addCounterfactual}
                                disabled={loading}
                                className="flex items-center gap-1 text-xs text-amber-400 hover:text-amber-300 transition-colors"
                            >
                                <Plus size={14} /> Add Step
                            </button>
                        </div>
                        
                        <div className="space-y-3">
                            {counterfactuals.map((cf, index) => (
                                <div key={index} className="flex items-start gap-2">
                                    <span className="text-amber-500 font-bold text-sm mt-3 w-16 flex-shrink-0">
                                        Step {index + 1}:
                                    </span>
                                    <input
                                        type="text"
                                        value={cf.replace(/^Step \d+:\s*/i, '')}
                                        onChange={e => updateCounterfactual(index, e.target.value)}
                                        placeholder="Enter an actionable improvement step..."
                                        className="flex-1 bg-[#291d1a]/50 border border-amber-900/30 rounded-lg px-3 py-2 text-amber-100 placeholder-amber-900/50 outline-none focus:border-amber-500 text-sm"
                                        disabled={loading}
                                    />
                                    {counterfactuals.length > 1 && (
                                        <button
                                            onClick={() => removeCounterfactual(index)}
                                            className="p-2 text-red-500/50 hover:text-red-400 transition-colors"
                                            disabled={loading}
                                        >
                                            <Trash2 size={16} />
                                        </button>
                                    )}
                                </div>
                            ))}
                        </div>

                        <p className="text-xs text-amber-900 mt-3">
                            These steps help customers understand what they can do to improve their chances in future applications.
                        </p>
                    </div>
                    
                    {error && (
                        <div className="mt-4 text-red-500 text-sm font-medium">
                            {error}
                        </div>
                    )}

                    <div className="mt-6 text-xs text-amber-900 border-t border-amber-900/20 pt-4">
                        <p className="mb-1"><strong>Guidelines:</strong></p>
                        <ul className="list-disc list-inside space-y-1">
                            <li>Be clear, concise, and professional</li>
                            <li>Explain the specific reasoning behind the decision</li>
                            <li>Make improvement steps actionable and achievable</li>
                            <li>Avoid technical jargon that customers might not understand</li>
                        </ul>
                    </div>
                </div>

                {/* Footer */}
                <div className="border-t border-amber-900/30 bg-[#291d1a]/50 p-6 flex gap-3 justify-end flex-shrink-0">
                    <button
                        onClick={onClose}
                        disabled={loading}
                        className="px-6 py-3 bg-transparent border border-amber-900/30 hover:bg-amber-900/20 text-amber-500 font-bold rounded-xl transition-all"
                    >
                        Cancel
                    </button>
                    <button
                        onClick={handleSave}
                        disabled={loading || !explanation.trim()}
                        className="px-6 py-3 bg-amber-500 hover:bg-amber-600 disabled:bg-amber-900/30 disabled:text-amber-900 text-white font-bold rounded-xl transition-all flex items-center gap-2"
                    >
                        {loading ? (
                            <>
                                <Loader size={20} className="animate-spin" />
                                Saving...
                            </>
                        ) : (
                            <>
                                <Save size={20} />
                                {isOverride ? 'Confirm Denial' : 'Save Changes'}
                            </>
                        )}
                    </button>
                </div>
            </div>
        </div>
    );
}
