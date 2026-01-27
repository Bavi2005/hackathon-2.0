import React, { useState, useEffect } from 'react';
import { X, Save, AlertTriangle, Loader } from 'lucide-react';
import { updateExplanation } from '../../lib/api';

interface ExplanationEditorProps {
    applicationId: string;
    currentExplanation: string;
    isOverride?: boolean;
    onClose: () => void;
    onSave: () => void;
}

export default function ExplanationEditor({ 
    applicationId, 
    currentExplanation, 
    isOverride = false,
    onClose,
    onSave 
}: ExplanationEditorProps) {
    const [explanation, setExplanation] = useState(currentExplanation);
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
            await updateExplanation(applicationId, explanation.trim());
            onSave();
            onClose();
        } catch (err) {
            console.error('Error saving explanation:', err);
            setError('Failed to save explanation. Please try again.');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-8">
            <div className="bg-[#1a100e] border border-amber-900/50 rounded-3xl max-w-3xl w-full overflow-hidden shadow-2xl">
                {/* Header */}
                <div className="bg-gradient-to-r from-amber-900/30 to-amber-800/20 border-b border-amber-900/50 p-6">
                    <div className="flex items-center justify-between">
                        <div>
                            <h2 className="text-3xl font-black text-white">Edit Explanation</h2>
                            <p className="text-sm text-amber-500/70 mt-1">
                                Customize the explanation shown to customers
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

                {/* Content */}
                <div className="p-6">
                    <label className="block text-amber-500 font-bold text-sm mb-3 uppercase tracking-wider">
                        Explanation Text
                    </label>
                    <textarea
                        value={explanation}
                        onChange={e => setExplanation(e.target.value)}
                        placeholder="Enter a clear, customer-friendly explanation..."
                        className="w-full bg-[#291d1a]/50 border border-amber-900/30 rounded-xl px-4 py-3 text-amber-100 placeholder-amber-900/50 outline-none focus:border-amber-500 resize-none"
                        rows={12}
                        disabled={loading}
                    />
                    
                    {error && (
                        <div className="mt-3 text-red-500 text-sm font-medium">
                            {error}
                        </div>
                    )}

                    <div className="mt-4 text-xs text-amber-900">
                        <p className="mb-1"><strong>Guidelines:</strong></p>
                        <ul className="list-disc list-inside space-y-1">
                            <li>Be clear, concise, and professional</li>
                            <li>Explain the reasoning behind the decision</li>
                            <li>Provide actionable next steps when applicable</li>
                            <li>Avoid technical jargon that customers might not understand</li>
                        </ul>
                    </div>
                </div>

                {/* Footer */}
                <div className="border-t border-amber-900/30 bg-[#291d1a]/50 p-6 flex gap-3 justify-end">
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
                                Save Changes
                            </>
                        )}
                    </button>
                </div>
            </div>
        </div>
    );
}
