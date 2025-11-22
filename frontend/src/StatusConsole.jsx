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
        <div className="w-full mt-8 bg-black/80 rounded-xl border border-green-500/30 overflow-hidden shadow-[0_0_30px_rgba(0,255,0,0.1)] font-mono text-sm">
            {/* Console Header */}
            <div className="bg-gray-900/90 px-4 py-2 border-b border-gray-800 flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <div className="w-3 h-3 rounded-full bg-red-500"></div>
                    <div className="w-3 h-3 rounded-full bg-yellow-500"></div>
                    <div className="w-3 h-3 rounded-full bg-green-500"></div>
                    <span className="ml-2 text-gray-400 text-xs">System Status: PROCESSING</span>
                </div>
                <span className="text-green-500 text-xs animate-pulse">● LIVE</span>
            </div>

            {/* Console Body */}
            <div className="p-4 h-64 overflow-y-auto custom-scrollbar">
                <table className="w-full text-left border-collapse">
                    <thead>
                        <tr className="text-gray-500 border-b border-gray-800">
                            <th className="pb-2 w-32">TIMESTAMP</th>
                            <th className="pb-2 w-20">STEP</th>
                            <th className="pb-2">STATUS MESSAGE</th>
                        </tr>
                    </thead>
                    <tbody>
                        {logs.map((log, index) => (
                            <tr key={index} className="text-green-400/90 hover:bg-green-900/10 transition-colors">
                                <td className="py-1 text-gray-500">{log.time}</td>
                                <td className="py-1 text-blue-400">STEP {String(log.step).padStart(2, '0')}</td>
                                <td className="py-1">{log.message}</td>
                            </tr>
                        ))}
                        <tr ref={logsEndRef}></tr>
                    </tbody>
                </table>
            </div>
        </div>
    );
};

export default StatusConsole;
