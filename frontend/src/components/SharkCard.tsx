import React from 'react';
import { Participant } from 'livekit-client';
import { Visualizer } from './Visualizer';
import { User } from 'lucide-react';

interface SharkCardProps {
    participant: Participant;
}

export const SharkCard: React.FC<SharkCardProps> = ({ participant }) => {
    const { identity, metadata, isSpeaking } = participant;

    // Assign specific classes for special sharks
    const sharkClass = identity.toLowerCase() === "mark" ? "shark-mark" :
        identity.toLowerCase() === "lori" ? "shark-lori" :
            identity.toLowerCase() === "kevin" ? "shark-kevin" : "";

    return (
        <div className={`shark-card ${sharkClass} ${isSpeaking ? 'speaking' : ''}`}>
            <div className="speaking-halo" />
            <div className="flex flex-col items-center text-center mb-5">
                <div className="relative w-28 h-28 mb-5 p-1 rounded-full bg-gradient-to-tr from-white/20 to-transparent">
                    <div className={`absolute inset-0 bg-blue-500/20 blur-2xl rounded-full z-0 ${isSpeaking ? 'animate-pulse' : ''}`} />
                    <div className="relative z-10 w-full h-full bg-black/40 rounded-full backdrop-blur-xl flex items-center justify-center border border-white/10 overflow-hidden shadow-2xl">
                        <div className="absolute inset-0 bg-gradient-to-b from-white/5 to-transparent pointer-events-none" />
                        <User className="w-14 h-14 text-white/50 drop-shadow-glow" />
                    </div>
                    {/* Status dot */}
                    <div className={`absolute bottom-1 right-1 w-5 h-5 border-2 border-[#010409] rounded-full z-20 shadow-lg ${isSpeaking ? 'bg-green-500' : 'bg-blue-500'}`} />
                </div>

                <div className="relative z-10">
                    <h3 className="text-xl md:text-2xl font-black text-white tracking-tighter leading-none mb-2 drop-shadow-md">
                        {(identity || "AI INVESTOR").toUpperCase()} <span className="text-blue-500">AI</span>
                    </h3>
                    <div className="flex items-center justify-center gap-3">
                        <div className="flex gap-1">
                            {[1, 2, 3, 4, 5].map(i => <div key={i} className="w-1 h-1 rounded-full bg-blue-500/50" />)}
                        </div>
                        <span className="text-[9px] font-black uppercase tracking-[0.3em] text-blue-400/80">Master Investor</span>
                        <div className="flex gap-1">
                            {[1, 2, 3, 4, 5].map(i => <div key={i} className="w-1 h-1 rounded-full bg-blue-500/50" />)}
                        </div>
                    </div>
                </div>
            </div>

            <div className="glass-panel p-3 mb-5 bg-black/20 border-white/5 text-center">
                <p className="text-xs font-semibold text-white/50 leading-relaxed italic">
                    "{metadata || "Ready to evaluate your pitch. Impress me with your margins and scalability."}"
                </p>
            </div>

            <div className="flex justify-between items-center px-2">
                <div className="flex flex-col">
                    <span className="text-[10px] font-bold text-white/30 uppercase tracking-widest">Net Worth</span>
                    <span className="text-sm font-bold text-white/80">$Billions</span>
                </div>
                <div className="h-8 w-px bg-white/10" />
                <div className="flex flex-col items-end">
                    <span className="text-[10px] font-bold text-white/30 uppercase tracking-widest">Status</span>
                    <span className={`text-sm font-bold ${isSpeaking ? 'text-green-400' : 'text-blue-400'}`}>
                        {isSpeaking ? 'SPEAKING' : 'LISTENING'}
                    </span>
                </div>
            </div>

            <div className="mt-5">
                <Visualizer isSpeaking={isSpeaking} />
            </div>
        </div>
    );
};
