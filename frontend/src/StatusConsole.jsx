import React, { useEffect, useState, useRef, useMemo } from 'react';

// ============================================================================
// HELPER: Parse incoming log data
// ============================================================================

const parseLogData = (data) => {
    if (typeof data === 'object' && data !== null) {
        return data;
    }
    if (typeof data === 'string') {
        const jsonMatch = data.match(/\{.*\}/s);
        if (jsonMatch) {
            try {
                return JSON.parse(jsonMatch[0]);
            } catch {
                return { status: 'info', message: data };
            }
        }
        return { status: 'info', message: data };
    }
    return { status: 'unknown', message: String(data) };
};

// ============================================================================
// SUB-COMPONENTS
// ============================================================================

// HUD Metric Card
const MetricCard = ({ label, value, color = 'cyan' }) => {
    const colorClasses = {
        cyan: 'text-cyan-400 border-cyan-500/30 bg-cyan-500/10',
        purple: 'text-purple-400 border-purple-500/30 bg-purple-500/10',
        amber: 'text-amber-400 border-amber-500/30 bg-amber-500/10',
    };

    return (
        <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border ${colorClasses[color]} backdrop-blur-sm`}>
            <div className="flex flex-col">
                <span className="text-[10px] uppercase tracking-wider text-zinc-500">{label}</span>
                <span className={`text-sm font-mono font-bold ${colorClasses[color].split(' ')[0]}`}>{value}</span>
            </div>
        </div>
    );
};

// Colored badge button (replaces emoji)
const StatusBadge = ({ type, direction }) => {
    const getBadgeConfig = () => {
        switch (type) {
            case 'exploring':
                if (direction === 'forward') {
                    return { color: 'bg-blue-500', label: 'FWD', textColor: 'text-white' };
                }
                return { color: 'bg-purple-500', label: 'BWD', textColor: 'text-white' };
            case 'finished':
                return { color: 'bg-green-500', label: 'OK', textColor: 'text-white' };
            case 'error':
                return { color: 'bg-red-500', label: 'ERR', textColor: 'text-white' };
            case 'info':
                return { color: 'bg-zinc-500', label: 'INFO', textColor: 'text-white' };
            case 'heartbeat':
                return { color: 'bg-zinc-600', label: '...', textColor: 'text-zinc-300' };
            default:
                return { color: 'bg-zinc-600', label: 'LOG', textColor: 'text-white' };
        }
    };

    const config = getBadgeConfig();

    return (
        <span className={`
            inline-flex items-center justify-center
            px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider
            ${config.color} ${config.textColor}
            min-w-[40px]
        `}>
            {config.label}
        </span>
    );
};

// Single log entry - terminal style
const LogEntry = ({ log }) => {
    const { status, direction, nodes, stats, message } = log.parsed;

    // Format the log message like the backend terminal
    const getLogContent = () => {
        if (status === 'exploring' && nodes && nodes.length > 0) {
            const nodeName = nodes[0];
            const dir = direction === 'forward' ? 'forward' : 'backward';
            const visited = stats?.visited || '?';
            const humans = stats?.humans || '?';
            return `${nodeName} (${dir}): ${visited} → ${humans} humans`;
        }
        if (status === 'finished') {
            return message || 'Path found!';
        }
        if (status === 'error') {
            return message || 'Error occurred';
        }
        if (status === 'info') {
            return message || 'Info';
        }
        if (status === 'heartbeat') {
            return 'System active...';
        }
        return message || JSON.stringify(log.parsed);
    };

    // Skip heartbeat in detailed view
    if (status === 'heartbeat') {
        return null;
    }

    const getBorderColor = () => {
        switch (status) {
            case 'exploring':
                return direction === 'forward' ? 'border-l-blue-500' : 'border-l-purple-500';
            case 'finished':
                return 'border-l-green-500';
            case 'error':
                return 'border-l-red-500';
            default:
                return 'border-l-zinc-600';
        }
    };

    return (
        <div className={`
            flex items-center gap-3 px-3 py-2 
            border-l-2 ${getBorderColor()} 
            bg-zinc-800/30 rounded-r
            font-mono text-xs
            animate-slideIn
        `}>
            {/* Timestamp */}
            <span className="text-zinc-600 flex-shrink-0">[{log.time}]</span>

            {/* Status badge */}
            <StatusBadge type={status} direction={direction} />

            {/* Message */}
            <span className={`
                flex-grow truncate
                ${status === 'finished' ? 'text-green-400 font-bold' :
                    status === 'error' ? 'text-red-400' :
                        status === 'exploring' && direction === 'forward' ? 'text-blue-300' :
                            status === 'exploring' && direction === 'backward' ? 'text-purple-300' :
                                'text-zinc-300'}
            `}>
                {getLogContent()}
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
    const containerRef = useRef(null);
    const wasLoadingRef = useRef(false);

    // Reset logs when loading starts
    useEffect(() => {
        if (loading && !wasLoadingRef.current) {
            setLogs([]);
            console.log('[StatusConsole] Loading started, logs reset');
        }
        wasLoadingRef.current = loading;
    }, [loading]);

    // Always listen for events
    useEffect(() => {
        const handleLog = (event) => {
            const rawData = event.detail;
            const now = new Date();
            const timeString = now.toLocaleTimeString('en-US', {
                hour12: false,
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit'
            });

            const parsed = parseLogData(rawData);
            console.log('[StatusConsole] Received:', parsed.status, parsed.nodes?.[0] || parsed.message);

            setLogs(prev => [...prev, {
                time: timeString,
                parsed,
                id: Date.now() + Math.random()
            }]);
        };

        window.addEventListener('bfs-log', handleLog);
        return () => window.removeEventListener('bfs-log', handleLog);
    }, []);

    // Auto-scroll to bottom
    useEffect(() => {
        logsEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [logs]);

    // Calculate metrics from latest exploring log
    const metrics = useMemo(() => {
        const latestExploring = [...logs].reverse().find(l => l.parsed.status === 'exploring');
        const stats = latestExploring?.parsed?.stats || {};
        const visited = stats.visited || 0;
        const time = stats.time || 0;
        const speed = time > 0 ? (visited / time).toFixed(1) : '0';
        return { visited, time, speed };
    }, [logs]);

    // Filter out consecutive heartbeats
    const displayLogs = useMemo(() => {
        return logs.filter(log => log.parsed.status !== 'heartbeat');
    }, [logs]);

    return (
        <div className="h-full flex flex-col bg-zinc-900/80 backdrop-blur-xl rounded-2xl border border-zinc-700/50 overflow-hidden shadow-2xl">

            {/* Header */}
            <div className="px-4 py-3 bg-zinc-800/50 border-b border-zinc-700/50">
                {/* Title */}
                <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                        <div className={`w-2 h-2 rounded-full ${loading ? 'bg-green-400 animate-pulse shadow-lg shadow-green-400/50' : 'bg-zinc-600'}`} />
                        <span className="text-xs font-mono text-zinc-400 uppercase tracking-widest">
                            BFS Engine
                        </span>
                    </div>
                    {loading && (
                        <span className="flex items-center gap-1.5 text-xs font-mono text-green-400 animate-pulse">
                            <span className="w-1.5 h-1.5 rounded-full bg-green-400" />
                            LIVE
                        </span>
                    )}
                </div>

                {/* Metrics */}
                <div className="flex flex-wrap gap-2">
                    <MetricCard label="Time" value={`${metrics.time}s`} color="cyan" />
                    <MetricCard label="Visited" value={`${metrics.visited}`} color="purple" />
                    <MetricCard label="Speed" value={`${metrics.speed}/s`} color="amber" />
                </div>
            </div>

            {/* Log List */}
            <div
                ref={containerRef}
                className="flex-grow overflow-y-auto p-2 space-y-1 custom-scrollbar bg-zinc-900"
            >
                {displayLogs.length === 0 ? (
                    <div className="h-full flex flex-col items-center justify-center text-zinc-600">
                        <svg className="w-10 h-10 mb-2 opacity-30" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1" d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" />
                        </svg>
                        <span className="text-sm font-mono">Awaiting search...</span>
                    </div>
                ) : (
                    <>
                        {displayLogs.map((log) => (
                            <LogEntry key={log.id} log={log} />
                        ))}
                        <div ref={logsEndRef} />
                    </>
                )}
            </div>

            {/* Footer */}
            {logs.length > 0 && (
                <div className="px-4 py-2 bg-zinc-800/30 border-t border-zinc-700/30 flex justify-between items-center text-[10px] text-zinc-600 font-mono">
                    <span>{displayLogs.length} events</span>
                    <span>{displayLogs.filter(l => l.parsed.status === 'exploring').length} nodes explored</span>
                </div>
            )}
        </div>
    );
};

export default StatusConsole;
