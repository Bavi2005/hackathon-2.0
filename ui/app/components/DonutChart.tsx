import React, { useMemo } from 'react';

type ChartSegment = {
	value: number;
	color: string;
	label?: string;
};

interface DonutChartProps {
	data: ChartSegment[];
	size?: number;
	thickness?: number;
	centerLabel?: string;
	centerSubLabel?: string;
}

export default function DonutChart({ data, size = 160, thickness = 20, centerLabel, centerSubLabel }: DonutChartProps) {
	const total = useMemo(() => data.reduce((acc, curr) => acc + curr.value, 0), [data]);

	const segments = useMemo(() => {
		let startAngle = 0;
		return data.map((segment, index) => {
			const percentage = total === 0 ? 0 : segment.value / total;
			const angle = percentage * 360;
			// SVG arc logic: Large arc flag is 1 if angle > 180
			const largeArc = angle > 180 ? 1 : 0;

			// Calculate coordinates (polar to cartesian)
			// We start from -90deg (top)
			const r = (size - thickness) / 2;
			const cx = size / 2;
			const cy = size / 2;

			const startRad = (startAngle - 90) * Math.PI / 180;
			const endRad = (startAngle + angle - 90) * Math.PI / 180;

			const x1 = cx + r * Math.cos(startRad);
			const y1 = cy + r * Math.sin(startRad);
			const x2 = cx + r * Math.cos(endRad);
			const y2 = cy + r * Math.sin(endRad);

			const pathData = [
				`M ${x1} ${y1}`, // Move to start
				`A ${r} ${r} 0 ${largeArc} 1 ${x2} ${y2}`, // Arc to end
			].join(' ');

			const currentStartAngle = startAngle;
			startAngle += angle;

			return { pathData, color: segment.color, key: index, percentage };
		});
	}, [data, total, size, thickness]);

	return (
		<div className="relative flex items-center justify-center" style={{ width: size, height: size }}>
			<svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
				{/* Background Circle */}
				<circle cx={size / 2} cy={size / 2} r={(size - thickness) / 2} stroke="#1a1d3a" strokeWidth={thickness} fill="none" />

				{/* Segments */}
				{segments.map(seg => (
					<path
						key={seg.key}
						d={seg.pathData}
						fill="none"
						stroke={seg.color}
						strokeWidth={thickness}
						strokeLinecap="round" // Optional: makes ends rounded
					/>
				))}
			</svg>
			{/* Center Text */}
			<div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
				{centerLabel && <span className="text-2xl font-black text-white">{centerLabel}</span>}
				{centerSubLabel && <span className="text-xs font-bold text-gray-500 uppercase tracking-wider">{centerSubLabel}</span>}
			</div>
		</div>
	);
}
