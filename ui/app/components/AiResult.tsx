import React from 'react';
import { CheckCircle2, XCircle } from 'lucide-react';
import { AiResultType } from '../lib/types';

interface AiResultProps {
	result: AiResultType;
	onReset: () => void;
}

export default function AiResult({ result, onReset }: AiResultProps) {
	// Note: in CustomerPortal, decision is passed as a string (status.model_output.label)
	// which differs from the AiResultType definition. We handle both for robustness.
	const decisionText = typeof result.decision === 'string' ? result.decision : result.decision?.status || '';
	// Check for all possible rejection/denial statuses from backend
	const isDenied = ['denied', 'rejected', 'high risk', 'high_risk'].includes(decisionText.toLowerCase());
	const isApproved = !isDenied;

	return (
		<div className="min-h-screen bg-[#1a100e] flex items-center justify-center p-8 relative overflow-hidden">
			{/* BACKGROUND */}
			<div className="absolute inset-0 bg-cover bg-center opacity-40 pointer-events-none" style={{ backgroundImage: 'url(/app_bg.png)' }} />
			<div className="absolute inset-0 bg-gradient-to-b from-[#1a100e]/80 via-[#1a100e]/50 to-[#1a100e] pointer-events-none" />

			<div className="relative z-10 bg-[#291d1a]/80 backdrop-blur-2xl border border-amber-500/20 p-12 rounded-[3.5rem] max-w-xl text-center shadow-[0_0_60px_-15px_rgba(245,158,11,0.2)]">
				{isApproved ? (
					<CheckCircle2 size={72} className="text-emerald-500 mx-auto mb-6 drop-shadow-lg" />
				) : (
					<div className="relative inline-block mb-6">
						<div className="absolute inset-0 bg-red-500/30 blur-2xl rounded-full" />
						<XCircle size={96} className="text-red-500 relative z-10 drop-shadow-lg" />
					</div>
				)}

				<h1 className={`text-4xl font-black mb-4 tracking-tight ${isApproved ? 'text-white' : 'text-red-100'}`}>
					{isApproved ? "Congratulations! Your application has been approved." : "Application Denied"}
				</h1>

				{/* REASON FOR DECISION - Always show summary */}
				{result.summary && (
					<div className={`mb-8 text-left p-6 rounded-2xl border ${isApproved ? 'bg-emerald-500/10 border-emerald-500/20' : 'bg-red-500/10 border-red-500/20'}`}>
						<h3 className={`font-bold uppercase tracking-wider text-sm mb-3 ${isApproved ? 'text-emerald-400' : 'text-red-400'}`}>
							{isApproved ? 'Decision Summary' : 'Reason for Decline'}
						</h3>
						<p className={`text-base leading-relaxed whitespace-pre-line ${isApproved ? 'text-emerald-100/80' : 'text-red-100/80'}`}>
							{result.summary}
						</p>
					</div>
				)}

				{/* Steps to Approval (Counterfactuals) - ONLY SHOW IF DENIED */}
				{!isApproved && result.counterfactuals && result.counterfactuals.length > 0 && (
					<div className="mb-10 text-left bg-[#1a100e]/50 p-6 rounded-2xl border border-amber-500/10">
						<h3 className="text-amber-400 font-bold uppercase tracking-wider text-sm mb-4">Steps to Improve Your Application</h3>
						<ul className="space-y-3">
							{result.counterfactuals.map((step: string, i: number) => (
								<li key={i} className="flex items-start text-amber-100/80">
									<span className="mr-3 mt-1.5 w-1.5 h-1.5 rounded-full bg-amber-500 shrink-0" />
									<span>{step}</span>
								</li>
							))}
						</ul>
					</div>
				)}

				<button onClick={onReset} className="w-full py-4 bg-gradient-to-r from-amber-600 to-yellow-600 hover:from-amber-500 hover:to-yellow-500 text-white rounded-2xl font-black text-lg uppercase tracking-wider transition-all shadow-lg hover:shadow-xl transform hover:-translate-y-1">
					Return to Portal
				</button>
			</div>
		</div>
	);
}
