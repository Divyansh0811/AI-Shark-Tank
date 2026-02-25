import React, { useState, useCallback } from 'react';
import {
    LiveKitRoom,
    RoomAudioRenderer,
    ControlBar,
    useParticipants,
    ConnectionState,
} from '@livekit/components-react';
import { SharkCard } from './components/SharkCard';
import { Trophy, Send, Users } from 'lucide-react';
const ENV = "PRODUCTION"
const BACKEND_URL = ENV === "PRODUCTION"
    ? 'https://ai-shark-tank.onrender.com'
    : 'http://localhost:8000';

export default function App() {
    const [token, setToken] = useState<string | null>(null);
    const [serverUrl, setServerUrl] = useState<string | null>(null);
    const [roomName, setRoomName] = useState('shark-arena');
    const [identity, setIdentity] = useState('');
    const [isJoining, setIsJoining] = useState(false);

    const handleJoin = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!roomName || !identity) return;
        setIsJoining(true);

        try {
            const resp = await fetch(`${BACKEND_URL}/token`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    participant_identity: identity,
                    participant_name: identity,
                    room_config: {
                        name: roomName
                    }
                }),
            });
            const data = await resp.json();
            // Align with backend change: using participant_token
            setToken(data.participant_token);
            setServerUrl(data.server_url);
        } catch (err) {
            console.error('Failed to get token:', err);
            alert('Failed to connect to backend server');
        } finally {
            setIsJoining(false);
        }
    };

    if (!token || !serverUrl) {
        return (
            <div className="fixed inset-0 flex items-center justify-center p-4 md:p-8 bg-slate-950 overflow-y-auto">
                <div className="max-w-xl w-full glass-panel p-12 md:p-20 shadow-[0_0_150px_rgba(59,130,246,0.1)] relative flex flex-col items-center border-white/10 my-auto">
                    <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-transparent via-blue-500/30 to-transparent" />

                    <div className="flex justify-center mb-16">
                        <div className="w-32 h-32 bg-gradient-to-br from-blue-600 to-blue-900 rounded-[40px] flex items-center justify-center transform rotate-12 shadow-2xl shadow-blue-500/30 border border-white/20">
                            <Trophy className="w-16 h-16 text-white -rotate-12 drop-shadow-2xl" />
                        </div>
                    </div>

                    <div className="text-center mb-16 w-full">
                        <h1 className="text-6xl font-black text-white tracking-tighter mb-6 leading-[1.1]">
                            SHARK TANK <span className="text-blue-500 drop-shadow-[0_0_20px_rgba(59,130,246,0.4)]">AI</span>
                        </h1>
                        <p className="text-slate-500 font-black uppercase tracking-[0.3em] text-[11px] opacity-80">
                            The Elite AI Pitch Arena
                        </p>
                    </div>

                    <form onSubmit={handleJoin} className="space-y-10 w-full max-w-sm">
                        <div className="space-y-4">
                            <label className="text-[11px] font-black text-slate-500 uppercase tracking-widest ml-1">Identity</label>
                            <input
                                type="text"
                                value={identity}
                                onChange={(e) => setIdentity(e.target.value)}
                                placeholder="e.g. Steve Jobs"
                                className="glass-input"
                                required
                            />
                        </div>
                        <div className="space-y-4">
                            <label className="text-[11px] font-black text-slate-500 uppercase tracking-widest ml-1">Room Name</label>
                            <input
                                type="text"
                                value={roomName}
                                onChange={(e) => setRoomName(e.target.value)}
                                className="glass-input"
                                required
                            />
                        </div>
                        <button
                            type="submit"
                            disabled={isJoining}
                            className="w-full premium-button flex items-center justify-center gap-6 mt-12 py-6"
                        >
                            <span className="text-xl tracking-widest">{isJoining ? 'PREPARING...' : 'ENTER ARENA'}</span>
                            <Send className={`w-6 h-6 transition-transform ${isJoining ? 'translate-x-12 opacity-0' : ''}`} />
                        </button>
                    </form>
                </div>
            </div>
        );
    }

    return (
        <LiveKitRoom
            token={token!}
            serverUrl={serverUrl!}
            connect={true}
            audio={true}
            video={false}
            onDisconnected={() => setToken(null)}
            style={{ height: '100vh', display: 'flex', flexDirection: 'column' }}
        >
            <RoomContent roomName={roomName} />
            <RoomAudioRenderer />
        </LiveKitRoom>
    );
}

function RoomContent({ roomName }: { roomName: string }) {
    const participants = useParticipants();
    // Generalized detection: Show all remote participants as "Sharks"
    const sharks = participants.filter(p => !p.isLocal);

    return (
        <div className="grid grid-rows-[auto_1fr_auto] h-screen w-full overflow-hidden max-w-screen-2xl mx-auto xl:p-8 p-4 gap-6">
            <header className="arena-header glass-panel px-10 py-8 flex justify-between items-center bg-black/40 backdrop-blur-xl border-white/10 rounded-[32px]">
                <div className="text-left">
                    <div className="flex items-center gap-3 mb-2">
                        <div className="w-2.5 h-2.5 bg-red-500 rounded-full animate-pulse shadow-[0_0_10px_#ef4444]" />
                        <span className="text-[10px] font-black text-red-500 uppercase tracking-[0.2em]">Live Session</span>
                    </div>
                    <h2 className="text-4xl font-black text-white tracking-tighter leading-none">
                        {roomName.toUpperCase()}
                    </h2>
                </div>

                <div className="flex gap-8 items-center">
                    <div className="flex flex-col items-end">
                        <span className="text-[10px] font-bold text-gray-500 uppercase tracking-widest mb-1">Board of Investors</span>
                        <div className="flex items-center gap-2">
                            <Users className="w-5 h-5 text-blue-400" />
                            <span className="text-2xl font-black text-white">{sharks.length}</span>
                        </div>
                    </div>
                    <button
                        onClick={() => window.location.reload()}
                        className="bg-white/5 hover:bg-red-500/10 text-white/60 hover:text-red-500 px-8 py-4 rounded-2xl border border-white/10 transition-all font-black text-xs uppercase tracking-[0.1em]"
                    >
                        Abandon Pitch
                    </button>
                </div>
            </header>

            <div className={`flex-1 grid gap-10 items-center transition-all duration-700 ${sharks.length === 1 ? 'grid-cols-1 max-w-2xl mx-auto' :
                sharks.length === 2 ? 'grid-cols-1 md:grid-cols-2 max-w-5xl mx-auto' :
                    'grid-cols-1 md:grid-cols-3'
                }`}>
                {sharks.map((shark) => (
                    <SharkCard key={shark.sid} participant={shark} />
                ))}

                {sharks.length === 0 && (
                    <div className="col-span-full flex items-center justify-center p-32 glass-panel border-dashed bg-white/[0.01] relative overflow-hidden">
                        <div className="absolute inset-0 bg-blue-500/5 animate-pulse" />
                        <div className="text-center relative z-10">
                            <div className="relative w-24 h-24 mx-auto mb-8">
                                <div className="absolute inset-0 border-4 border-blue-500/20 rounded-full" />
                                <div className="absolute inset-0 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
                            </div>
                            <h3 className="text-2xl font-black text-white mb-3 tracking-tight">WAITING FOR SHARKS</h3>
                            <p className="text-gray-500 font-bold uppercase tracking-widest text-xs">Analyzing pitch deck and market potential...</p>
                        </div>
                    </div>
                )}
            </div>

            <div className="flex items-center justify-center py-6 px-10 glass-panel bg-black/60 backdrop-blur-3xl border-white/10 rounded-[32px] shadow-2xl relative z-50">
                <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-4 py-1.5 bg-blue-600 rounded-full shadow-xl shadow-blue-500/30 border border-white/20">
                    <span className="text-[10px] font-black text-white uppercase tracking-[0.2em]">Pitch Console</span>
                </div>

                <div className="flex items-center justify-center w-full">
                    <ControlBar
                        variation="minimal"
                        controls={{ microphone: true, screenShare: false, camera: false, chat: false }}
                        className="bg-transparent border-none p-0 flex gap-8 scale-110"
                    />
                </div>
            </div>
        </div>
    );
}
