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
// HELPER: Parse backend log message
// Pattern: "Name (direction): Total → Filtered → Humans humans"
// Returns: { name, direction, visited } or null
// ============================================================================
const parseBackendLog = (rawMessage) => {
    if (!rawMessage || typeof rawMessage !== 'string') return null;

    // Robust regex: handles both → and -> arrows
    // "Carlo Rubbia (forward): 318 → 312 → 22 humans"
    // "Carlo Rubbia (backward): 500 -> 490 -> 28 humans"
    const regex = /^(.+?)\s+\((forward|backward)\):\s*(\d+)/i;
    const match = rawMessage.match(regex);

    if (match) {
        return {
            name: match[1].trim(),
            direction: match[2].toLowerCase(),
            visited: parseInt(match[3], 10)
        };
    }

    return null;
};

// ============================================================================
// BADGE COMPONENT - Colored buttons
// ============================================================================
const Badge = ({ type, direction }) => {
    let label = 'INFO';
    let bg = 'bg-zinc-600';

    if (type === 'log' || type === 'exploring') {
        if (direction === 'forward') {
            label = 'FWD';
            bg = 'bg-blue-600';
        } else {
            label = 'BWD';
            bg = 'bg-purple-600';
        }
    } else if (type === 'finished') {
        label = 'OK';
        bg = 'bg-green-600';
    } else if (type === 'error') {
        label = 'ERR';
        bg = 'bg-red-600';
    }

    return (
        <span className={`${bg} text-white px-1.5 py-0.5 rounded text-[10px] font-bold uppercase min-w-[36px] text-center inline-block flex-shrink-0`}>
            {label}
        </span>
    );
};

// ============================================================================
// SINGLE LOG LINE
// ============================================================================
const LogLine = ({ log }) => {
    const { status, direction, message } = log.parsed;

    // Skip heartbeats
    if (status === 'heartbeat') return null;

    // Parse the backend log message
    const parsed = status === 'log' ? parseBackendLog(message) : null;

    // Render based on status
    if (status === 'log' && parsed) {
        // Parsed log: Show name and visited count clearly
        const dirColor = parsed.direction === 'forward' ? 'text-blue-300' : 'text-purple-300';

        return (
            <div className="flex items-center gap-2 py-1 hover:bg-white/5 px-2 -mx-2 rounded font-mono text-xs">
                <span className="text-zinc-600 flex-shrink-0">[{log.time}]</span>
                <Badge type={status} direction={parsed.direction} />
                <span className={dirColor}>
                    Checking: <span className="font-semibold">{parsed.name}</span>
                </span>
                <span className="text-zinc-500 flex-shrink-0">
                    (Visited: <span className="text-amber-400 font-semibold">{parsed.visited}</span>)
                </span>
            </div>
        );
    }

    if (status === 'finished') {
        return (
            <div className="flex items-center gap-2 py-1 px-2 -mx-2 rounded font-mono text-xs bg-green-900/20">
                <span className="text-zinc-600 flex-shrink-0">[{log.time}]</span>
                <Badge type={status} direction={direction} />
                <span className="text-green-400 font-semibold">
                    🎯 {message || 'Path found!'}
                </span>
            </div>
        );
    }

    if (status === 'error') {
        return (
            <div className="flex items-center gap-2 py-1 px-2 -mx-2 rounded font-mono text-xs bg-red-900/20">
                <span className="text-zinc-600 flex-shrink-0">[{log.time}]</span>
                <Badge type={status} direction={direction} />
                <span className="text-red-400">⚠️ {message || 'Error'}</span>
            </div>
        );
    }

    // Default: info or fallback
    return (
        <div className="flex items-center gap-2 py-1 hover:bg-white/5 px-2 -mx-2 rounded font-mono text-xs">
            <span className="text-zinc-600 flex-shrink-0">[{log.time}]</span>
            <Badge type={status} direction={direction} />
            <span className="text-zinc-400">{message || 'System active'}</span>
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

    // Listen for log events - NO THROTTLING for real-time updates
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

            // Immediate state update - no batching
            setLogs(prev => [...prev, {
                time,
                parsed,
                id: Date.now() + Math.random()
            }]);
        };

        window.addEventListener('bfs-log', handleLog);
        return () => window.removeEventListener('bfs-log', handleLog);
    }, []);

    // Auto-scroll to bottom immediately
    useEffect(() => {
        logsEndRef.current?.scrollIntoView({ behavior: 'auto' }); // 'auto' is faster than 'smooth'
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

            {/* Header Bar */}
            <div className="flex items-center justify-between px-3 py-2 bg-zinc-900 border-b border-zinc-800">
                <div className="flex items-center gap-2">
                    <div className="flex gap-1.5">
                        <span className="w-3 h-3 rounded-full bg-red-500" />
                        <span className="w-3 h-3 rounded-full bg-yellow-500" />
                        <span className="w-3 h-3 rounded-full bg-green-500" />
                    </div>
                    <span className="text-zinc-500 ml-2 font-mono text-xs">BFS Engine</span>
                </div>

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
            <div className="flex-grow overflow-y-auto p-2 space-y-0 custom-scrollbar bg-zinc-950">
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
                    <span className="text-green-500">$</span> {metrics.nodes} nodes | {metrics.events} events
                </div>
            )}
        </div>
    );
};

export default StatusConsole;
