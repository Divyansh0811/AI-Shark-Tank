import React, { useEffect, useState } from 'react';
import { useTrackTranscription, useParticipantTracks } from '@livekit/components-react';
import { Track } from 'livekit-client';

interface VisualizerProps {
    participantIdentity: string;
}

export const Visualizer: React.FC<VisualizerProps> = ({ participantIdentity }) => {
    const [bars, setBars] = useState<number[]>(new Array(10).fill(4));

    useEffect(() => {
        const interval = setInterval(() => {
            // Simulate visualizer for now if not speaking, otherwise we'd hook into audio frequency data
            setBars(prev => prev.map(() => Math.max(4, Math.random() * 40)));
        }, 100);
        return () => clearInterval(interval);
    }, []);

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
