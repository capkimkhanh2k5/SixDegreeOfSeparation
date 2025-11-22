import React, { useEffect, useState, useRef } from 'react';

const StatusConsole = ({ loading }) => {
    const [logs, setLogs] = useState([{
        time: new Date().toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' }),
        step: "•",
        message: "System ready. Enter search parameters and click 'Find Connection' to begin."
    }]);
    const logsEndRef = useRef(null);

    useEffect(() => {
        if (loading) {
            setLogs([]); // Reset logs on new search

            const handleLog = (event) => {
                const data = event.detail;
                const now = new Date();
                const timeString = now.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' }) + "." + String(now.getMilliseconds()).padStart(3, '0');

                let message = "";
                let step = data.step || "-";

                if (data.status === 'visiting') {
                    message = `Visiting: ${data.node} (${data.direction})`;
                } else if (data.status === 'info') {
                    message = data.message;
                } else {
                    message = JSON.stringify(data);
                }

                setLogs(prev => [...prev, { time: timeString, step, message }]);
            };

            window.addEventListener('bfs-log', handleLog);

            return () => {
                window.removeEventListener('bfs-log', handleLog);
            };
        }
    }, [loading]);

    // Auto-scroll to bottom
    useEffect(() => {
        logsEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [logs]);

    // Removed early return to keep console visible


    return (
        <div className="h-full flex flex-col bg-white/40 dark:bg-black/40 backdrop-blur-md rounded-2xl border border-white/50 dark:border-white/10 overflow-hidden shadow-lg transition-colors duration-500">
            <div className="px-4 py-3 bg-white/50 dark:bg-white/5 border-b border-white/20 dark:border-white/5 flex justify-between items-center">
                <div className="flex items-center gap-2">
                    <div className={`w-2 h-2 rounded-full ${loading ? 'bg-green-500 animate-pulse' : 'bg-gray-400'}`} />
                    <span className="text-xs font-mono text-gray-600 dark:text-gray-400 uppercase tracking-wider">System Status</span>
                </div>
                {loading && <span className="text-xs text-indigo-600 dark:text-indigo-400 font-medium animate-pulse">Processing...</span>}
            </div>

            <div
                className="flex-grow overflow-y-auto p-4 font-mono text-sm space-y-2 custom-scrollbar"
            >
                {logs.length === 0 ? (
                    <div className="h-full flex flex-col items-center justify-center text-gray-400 dark:text-gray-600 opacity-50">
                        <svg className="w-12 h-12 mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.384-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
                        </svg>
                        <span>Ready to search</span>
                    </div>
                ) : (
                    <>
                        {logs.map((log, index) => (
                            <div key={index} className="animate-slideIn">
                                <span className="text-gray-400 dark:text-gray-600 mr-2">[{log.time}]</span>
                                <span className={
                                    log.type === 'error' ? 'text-red-500 dark:text-red-400' :
                                        log.type === 'finished' ? 'text-green-600 dark:text-green-400 font-bold' :
                                            log.type === 'visiting' ? 'text-indigo-600 dark:text-indigo-400' :
                                                'text-gray-700 dark:text-gray-300'
                                }>
                                    {log.message}
                                </span>
                            </div>
                        ))}
                        <div ref={logsEndRef} />
                    </>
                )}
            </div>
        </div>
    );
};

export default StatusConsole;
