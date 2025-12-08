import React, { useEffect, useState, useRef, useMemo } from 'react';

// ============================================================================
// SVG ICONS (Inline to avoid dependencies)
// ============================================================================

const IconArrowRight = () => (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
    </svg>
);

const IconArrowLeft = () => (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 17l-5-5m0 0l5-5m-5 5h12" />
    </svg>
);

const IconTarget = () => (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
);

const IconAlert = () => (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
    </svg>
);

const IconActivity = () => (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
    </svg>
);

// ============================================================================
// HELPER: Parse incoming log data
// ============================================================================

const parseLogData = (data) => {
    // If already an object, use directly
    if (typeof data === 'object' && data !== null) {
        return data;
    }

    // If string, try to parse JSON
    if (typeof data === 'string') {
        // Extract JSON from format: [HH:MM:SS.ms] {...}
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
const MetricCard = ({ icon, label, value, accent = 'cyan' }) => {
    const accentColors = {
        cyan: 'text-cyan-400 border-cyan-500/30 bg-cyan-500/10',
        purple: 'text-purple-400 border-purple-500/30 bg-purple-500/10',
        green: 'text-green-400 border-green-500/30 bg-green-500/10',
        amber: 'text-amber-400 border-amber-500/30 bg-amber-500/10',
    };

    return (
        <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border ${accentColors[accent]} backdrop-blur-sm`}>
            <span className="opacity-70">{icon}</span>
            <div className="flex flex-col">
                <span className="text-[10px] uppercase tracking-wider text-zinc-500">{label}</span>
                <span className={`text-sm font-mono font-bold ${accentColors[accent].split(' ')[0]}`}>{value}</span>
            </div>
        </div>
    );
};

// Log Entry Card
const LogEntry = ({ log, isLatest }) => {
    const { status, direction, nodes, stats, message, time } = log.parsed;

    // Style configurations per status
    const getStatusConfig = () => {
        switch (status) {
            case 'exploring':
                if (direction === 'forward') {
                    return {
                        borderColor: 'border-l-blue-500',
                        bgColor: 'bg-blue-500/5',
                        icon: <IconArrowRight />,
                        iconBg: 'bg-blue-500/20 text-blue-400',
                        badge: '🔵 FORWARD',
                        badgeColor: 'bg-blue-500/20 text-blue-300'
                    };
                } else {
                    return {
                        borderColor: 'border-l-purple-500',
                        bgColor: 'bg-purple-500/5',
                        icon: <IconArrowLeft />,
                        iconBg: 'bg-purple-500/20 text-purple-400',
                        badge: '🟣 BACKWARD',
                        badgeColor: 'bg-purple-500/20 text-purple-300'
                    };
                }
            case 'finished':
                return {
                    borderColor: 'border-l-green-500',
                    bgColor: 'bg-green-500/10',
                    icon: <IconTarget />,
                    iconBg: 'bg-green-500/20 text-green-400',
                    badge: '🎯 FOUND',
                    badgeColor: 'bg-green-500/20 text-green-300',
                    isSuccess: true
                };
            case 'error':
                return {
                    borderColor: 'border-l-red-500',
                    bgColor: 'bg-red-500/10',
                    icon: <IconAlert />,
                    iconBg: 'bg-red-500/20 text-red-400',
                    badge: '⚠️ ERROR',
                    badgeColor: 'bg-red-500/20 text-red-300',
                    isError: true
                };
            case 'heartbeat':
                return {
                    isHeartbeat: true
                };
            case 'info':
                return {
                    borderColor: 'border-l-zinc-600',
                    bgColor: 'bg-zinc-500/5',
                    icon: <IconActivity />,
                    iconBg: 'bg-zinc-500/20 text-zinc-400',
                    badge: 'ℹ️ INFO',
                    badgeColor: 'bg-zinc-500/20 text-zinc-400'
                };
            default:
                return {
                    borderColor: 'border-l-zinc-600',
                    bgColor: 'bg-zinc-500/5',
                    icon: <IconActivity />,
                    iconBg: 'bg-zinc-500/20 text-zinc-400',
                    badge: '📝 LOG',
                    badgeColor: 'bg-zinc-500/20 text-zinc-400'
                };
        }
    };

    const config = getStatusConfig();

    // Heartbeat: Minimal dot indicator
    if (config.isHeartbeat) {
        return (
            <div className="flex items-center gap-2 py-1 px-3 text-zinc-600">
                <span className="w-1.5 h-1.5 rounded-full bg-zinc-500 animate-pulse" />
                <span className="text-xs font-mono">System active...</span>
            </div>
        );
    }

    // Success card (larger)
    if (config.isSuccess) {
        return (
            <div className={`
                border-l-4 ${config.borderColor} ${config.bgColor}
                rounded-r-xl p-4 mb-2 animate-slideIn
            `}>
                <div className="flex items-center gap-3">
                    <div className={`p-2 rounded-full ${config.iconBg}`}>
                        {config.icon}
                    </div>
                    <div>
                        <div className="text-green-400 font-bold text-lg">🎯 Target Found!</div>
                        <div className="text-green-300/70 text-sm">Path successfully computed</div>
                    </div>
                </div>
            </div>
        );
    }

    // Error card
    if (config.isError) {
        return (
            <div className={`
                border-l-4 ${config.borderColor} ${config.bgColor}
                rounded-r-xl p-3 mb-2 animate-slideIn
            `}>
                <div className="flex items-center gap-3">
                    <div className={`p-2 rounded-full ${config.iconBg}`}>
                        {config.icon}
                    </div>
                    <div>
                        <div className="text-red-400 font-bold">Error</div>
                        <div className="text-red-300/70 text-sm">{message || 'Unknown error'}</div>
                    </div>
                </div>
            </div>
        );
    }

    // Get node name to display
    const nodeName = nodes && nodes.length > 0 ? nodes[0] : null;
    const displayMessage = message || (nodeName ? `Visiting: ${nodeName}` : 'Processing...');

    return (
        <div className={`
            border-l-2 ${config.borderColor} ${config.bgColor}
            rounded-r-lg px-3 py-2 mb-1.5 transition-all duration-200
            ${isLatest ? 'ring-1 ring-white/10' : ''}
            animate-slideIn
        `}>
            <div className="flex items-center gap-3">
                {/* Icon */}
                <div className={`p-1.5 rounded-md ${config.iconBg} flex-shrink-0`}>
                    {config.icon}
                </div>

                {/* Content */}
                <div className="flex-grow min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                        {/* Badge */}
                        <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${config.badgeColor}`}>
                            {config.badge}
                        </span>

                        {/* Node name or message */}
                        {nodeName ? (
                            <span className="text-zinc-200 font-medium truncate">
                                {nodeName}
                            </span>
                        ) : (
                            <span className="text-zinc-400 text-sm truncate">
                                {displayMessage}
                            </span>
                        )}
                    </div>

                    {/* Stats row */}
                    {stats && (
                        <div className="flex items-center gap-3 mt-1 text-[10px] text-zinc-500 font-mono">
                            <span>V: {stats.visited}</span>
                            <span>T: {stats.time}s</span>
                        </div>
                    )}
                </div>

                {/* Timestamp */}
                <div className="text-[10px] text-zinc-600 font-mono flex-shrink-0">
                    {log.time}
                </div>
            </div>
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

    // Reset logs when loading starts (transition from false to true)
    useEffect(() => {
        if (loading && !wasLoadingRef.current) {
            // Loading just started - reset logs
            setLogs([]);
            console.log('[StatusConsole] Loading started, logs reset');
        }
        wasLoadingRef.current = loading;
    }, [loading]);

    // ALWAYS listen for events (not conditional on loading)
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
            console.log('[StatusConsole] Received event:', parsed.status, parsed.nodes?.[0] || parsed.message);

            setLogs(prev => [...prev, {
                time: timeString,
                parsed,
                id: Date.now() + Math.random()
            }]);
        };

        // Attach listener immediately on mount
        window.addEventListener('bfs-log', handleLog);
        console.log('[StatusConsole] Event listener attached');

        return () => {
            window.removeEventListener('bfs-log', handleLog);
            console.log('[StatusConsole] Event listener removed');
        };
    }, []); // Empty deps - only run once on mount

    // Auto-scroll to bottom
    useEffect(() => {
        logsEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [logs]);

    // Calculate live metrics from latest log
    const metrics = useMemo(() => {
        const latestExploring = [...logs].reverse().find(l => l.parsed.status === 'exploring');
        const stats = latestExploring?.parsed?.stats || {};
        const visited = stats.visited || 0;
        const time = stats.time || 0;
        const speed = time > 0 ? (visited / time).toFixed(1) : '0';

        return { visited, time, speed };
    }, [logs]);

    // Filter out consecutive heartbeats (show max 1)
    const displayLogs = useMemo(() => {
        const filtered = [];
        let lastWasHeartbeat = false;

        for (const log of logs) {
            if (log.parsed.status === 'heartbeat') {
                if (!lastWasHeartbeat) {
                    filtered.push(log);
                    lastWasHeartbeat = true;
                }
            } else {
                filtered.push(log);
                lastWasHeartbeat = false;
            }
        }
        return filtered;
    }, [logs]);

    return (
        <div className="h-full flex flex-col bg-zinc-900/80 backdrop-blur-xl rounded-2xl border border-zinc-700/50 overflow-hidden shadow-2xl">

            {/* HUD Header */}
            <div className="px-4 py-3 bg-zinc-800/50 border-b border-zinc-700/50">
                {/* Title Row */}
                <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                        <div className={`w-2 h-2 rounded-full ${loading ? 'bg-cyan-400 animate-pulse shadow-lg shadow-cyan-400/50' : 'bg-zinc-600'}`} />
                        <span className="text-xs font-mono text-zinc-400 uppercase tracking-widest">
                            BFS Engine
                        </span>
                    </div>
                    {loading && (
                        <span className="text-xs font-mono text-cyan-400 animate-pulse flex items-center gap-1">
                            <span className="w-1 h-1 rounded-full bg-cyan-400" />
                            LIVE
                        </span>
                    )}
                </div>

                {/* Metrics Row */}
                <div className="flex flex-wrap gap-2">
                    <MetricCard
                        icon="⏱️"
                        label="Time"
                        value={`${metrics.time}s`}
                        accent="cyan"
                    />
                    <MetricCard
                        icon="🔍"
                        label="Visited"
                        value={`${metrics.visited}`}
                        accent="purple"
                    />
                    <MetricCard
                        icon="⚡"
                        label="Speed"
                        value={`${metrics.speed}/s`}
                        accent="amber"
                    />
                </div>
            </div>

            {/* Log List */}
            <div
                ref={containerRef}
                className="flex-grow overflow-y-auto p-3 custom-scrollbar bg-gradient-to-b from-zinc-900/50 to-zinc-900"
            >
                {displayLogs.length === 0 ? (
                    <div className="h-full flex flex-col items-center justify-center text-zinc-600">
                        <svg className="w-12 h-12 mb-3 opacity-30" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1" d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" />
                        </svg>
                        <span className="text-sm font-mono">Awaiting search...</span>
                        <span className="text-xs text-zinc-700 mt-1">Enter names above and click Find Connection</span>
                    </div>
                ) : (
                    <>
                        {displayLogs.map((log, index) => (
                            <LogEntry
                                key={log.id || index}
                                log={log}
                                isLatest={index === displayLogs.length - 1}
                            />
                        ))}
                        <div ref={logsEndRef} />
                    </>
                )}
            </div>

            {/* Footer Stats Bar */}
            {logs.length > 0 && (
                <div className="px-4 py-2 bg-zinc-800/30 border-t border-zinc-700/30 flex justify-between items-center">
                    <span className="text-[10px] text-zinc-600 font-mono">
                        {logs.length} events logged
                    </span>
                    <span className="text-[10px] text-zinc-600 font-mono">
                        {displayLogs.filter(l => l.parsed.status === 'exploring').length} nodes explored
                    </span>
                </div>
            )}
        </div>
    );
};

export default StatusConsole;
