import React, { useEffect, useState, useRef, useMemo } from 'react';

// ============================================================================
// HELPER: Parse incoming log data
// ============================================================================
const parseLogData = (data) => {
    if (typeof data === 'object' && data !== null) {
        return data;
    }
    if (typeof data === 'string') {
        try {
            return JSON.parse(data);
        } catch {
            return { status: 'info', message: data };
        }
    }
    return { status: 'info', message: String(data) };
};

// ============================================================================
// BADGE COMPONENT - Colored buttons like terminal
// ============================================================================
const Badge = ({ type, direction }) => {
    const getBadge = () => {
        if (type === 'log' || type === 'exploring') {
            if (direction === 'forward') {
                return { label: 'FWD', bg: 'bg-blue-600', text: 'text-white' };
            }
            return { label: 'BWD', bg: 'bg-purple-600', text: 'text-white' };
        }
        if (type === 'finished') {
            return { label: 'OK', bg: 'bg-green-600', text: 'text-white' };
        }
        if (type === 'error') {
            return { label: 'ERR', bg: 'bg-red-600', text: 'text-white' };
        }
        if (type === 'heartbeat') {
            return { label: '...', bg: 'bg-zinc-700', text: 'text-zinc-400' };
        }
        return { label: 'INFO', bg: 'bg-zinc-600', text: 'text-zinc-200' };
    };

    const config = getBadge();

    return (
        <span className={`${config.bg} ${config.text} px-1.5 py-0.5 rounded text-[10px] font-bold uppercase min-w-[36px] text-center`}>
            {config.label}
        </span>
    );
};

// ============================================================================
// SINGLE LOG LINE - Shows exact backend message
// ============================================================================
const LogLine = ({ log }) => {
    const { status, direction, message } = log.parsed;

    // Skip heartbeats in display
    if (status === 'heartbeat') return null;

    // Get the display text - prioritize 'message' field for 'log' status
    const getDisplayText = () => {
        if (status === 'log' && message) {
            return message; // Exact message from backend: "Carlo Rubbia (forward): 318 → 22 humans"
        }
        if (message) return message;
        if (log.parsed.nodes?.[0]) {
            return `Checking: ${log.parsed.nodes[0]}`;
        }
        return JSON.stringify(log.parsed);
    };

    // Text color based on direction
    const getTextColor = () => {
        if (status === 'log' || status === 'exploring') {
            if (direction === 'forward') return 'text-blue-300';
            if (direction === 'backward') return 'text-purple-300';
        }
        if (status === 'finished') return 'text-green-300';
        if (status === 'error') return 'text-red-300';
        return 'text-zinc-400';
    };

    return (
        <div className="flex items-start gap-2 py-0.5 hover:bg-white/5 px-2 -mx-2 rounded font-mono text-xs">
            {/* Timestamp */}
            <span className="text-zinc-600 flex-shrink-0">[{log.time}]</span>

            {/* Badge */}
            <Badge type={status} direction={direction} />

            {/* Message - exact text from backend */}
            <span className={`${getTextColor()} break-all`}>
                {getDisplayText()}
            </span>
        </div>
    );
};

// ============================================================================
// MAIN COMPONENT
// ============================================================================
const StatusConsole = ({ loading }) => {
    const [logs, setLogs] = useState([]);
    const logsEndRef = useRef(null);
    const wasLoadingRef = useRef(false);

    // Reset logs when loading starts
    useEffect(() => {
        if (loading && !wasLoadingRef.current) {
            setLogs([]);
        }
        wasLoadingRef.current = loading;
    }, [loading]);

    // Listen for log events
    useEffect(() => {
        const handleLog = (event) => {
            const rawData = event.detail;
            const now = new Date();
            const time = now.toLocaleTimeString('en-US', {
                hour12: false,
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit'
            });

            const parsed = parseLogData(rawData);

            setLogs(prev => [...prev, {
                time,
                parsed,
                id: Date.now() + Math.random()
            }]);
        };

        window.addEventListener('bfs-log', handleLog);
        return () => window.removeEventListener('bfs-log', handleLog);
    }, []);

    // Auto-scroll to bottom
    useEffect(() => {
        logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [logs]);

    // Calculate metrics
    const metrics = useMemo(() => {
        const logEntries = logs.filter(l => l.parsed.status === 'log' || l.parsed.status === 'exploring');
        return {
            nodes: logEntries.length,
            events: logs.length,
        };
    }, [logs]);

    return (
        <div className="h-full flex flex-col bg-zinc-950 rounded-xl border border-zinc-800 overflow-hidden">

            {/* Header Bar - Terminal style */}
            <div className="flex items-center justify-between px-3 py-2 bg-zinc-900 border-b border-zinc-800">
                <div className="flex items-center gap-2">
                    {/* Traffic light dots */}
                    <div className="flex gap-1.5">
                        <span className="w-3 h-3 rounded-full bg-red-500" />
                        <span className="w-3 h-3 rounded-full bg-yellow-500" />
                        <span className="w-3 h-3 rounded-full bg-green-500" />
                    </div>
                    <span className="text-zinc-500 ml-2 font-mono text-xs">BFS Engine</span>
                </div>

                {/* Live indicator */}
                {loading && (
                    <div className="flex items-center gap-1.5 text-green-400 font-mono text-xs">
                        <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
                        <span>LIVE</span>
                    </div>
                )}
            </div>

            {/* Stats Bar */}
            <div className="flex items-center gap-4 px-3 py-1.5 bg-zinc-900/50 border-b border-zinc-800/50 font-mono text-[10px] text-zinc-500">
                <span>Nodes: <span className="text-cyan-400">{metrics.nodes}</span></span>
                <span>Events: <span className="text-purple-400">{metrics.events}</span></span>
            </div>

            {/* Log Area */}
            <div className="flex-grow overflow-y-auto p-3 space-y-0.5 custom-scrollbar bg-zinc-950">
                {logs.length === 0 ? (
                    <div className="h-full flex items-center justify-center text-zinc-700 font-mono text-xs">
                        <span>$ awaiting input...</span>
                        <span className="animate-pulse ml-1">_</span>
                    </div>
                ) : (
                    <>
                        {logs.map(log => (
                            <LogLine key={log.id} log={log} />
                        ))}
                        <div ref={logsEndRef} />
                    </>
                )}
            </div>

            {/* Footer */}
            {logs.length > 0 && (
                <div className="px-3 py-1.5 bg-zinc-900/50 border-t border-zinc-800/50 font-mono text-[10px] text-zinc-600">
                    <span className="text-green-500">$</span> {metrics.nodes} nodes processed | {metrics.events} total events
                </div>
            )}
        </div>
    );
};

export default StatusConsole;
