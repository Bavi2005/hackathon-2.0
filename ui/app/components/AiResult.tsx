import React from 'react';
import { CheckCircle2 } from 'lucide-react';
import { AiResultType } from '../lib/types';

interface AiResultProps {
	result: AiResultType;
	onReset: () => void;
}

export default function AiResult({ result, onReset }: AiResultProps) {
	const isDenied = result.decision.toLowerCase() === 'denied' || result.decision.toLowerCase() === 'high risk';
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
						<div className="absolute inset-0 bg-red-500/20 blur-xl rounded-full" />
						<CheckCircle2 size={72} className="text-red-500 relative z-10 hidden" /> {/* Placeholder to keep import if needed, but we switch to X */}
						<svg xmlns="http://www.w3.org/2000/svg" width="72" height="72" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-red-500 relative z-10"><circle cx="12" cy="12" r="10" /><path d="m15 9-6 6" /><path d="m9 9 6 6" /></svg>
					</div>
				)}

				<h1 className={`text-5xl font-black mb-4 tracking-tight ${isApproved ? 'text-white' : 'text-red-100'}`}>{result.decision}</h1>
				<p className="text-amber-100/70 mb-10 text-lg font-medium leading-relaxed">"{result.summary}"</p>

				{/* Steps to Approval (Counterfactuals) */}
				{result.counterfactuals && result.counterfactuals.length > 0 && (
					<div className="mb-10 text-left bg-[#1a100e]/50 p-6 rounded-2xl border border-amber-500/10">
						<h3 className="text-amber-400 font-bold uppercase tracking-wider text-sm mb-4">Steps to Approval</h3>
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
