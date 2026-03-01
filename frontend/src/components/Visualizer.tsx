import React, { useEffect, useState } from 'react';

interface VisualizerProps {
    isSpeaking: boolean;
}

export const Visualizer: React.FC<VisualizerProps> = ({ isSpeaking }) => {
    const [bars, setBars] = useState<number[]>(new Array(10).fill(4));

    useEffect(() => {
        if (!isSpeaking) {
            setBars(new Array(10).fill(4));
            return;
        }
        const interval = setInterval(() => {
            setBars(prev => prev.map(() => Math.max(6, Math.random() * 28)));
        }, 100);
        return () => clearInterval(interval);
    }, [isSpeaking]);

    return (
        <div className="visualizer-container">
            {bars.map((height, i) => (
                <div
                    key={i}
                    className="visualizer-bar"
                    style={{ height: `${height}px` }}
                />
            ))}
        </div>
    );
};
