import React from 'react';

const ErrorMessage = ({ message, onDismiss }) => {
    if (!message) return null;

    return (
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6 my-4 backdrop-blur-xl animate-fadeIn">
            <div className="flex items-start gap-4">
                <div className="flex-shrink-0">
                    <div className="w-12 h-12 rounded-full bg-red-500/20 flex items-center justify-center">
                        <svg className="w-6 h-6 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                        </svg>
                    </div>
                </div>

                <div className="flex-1">
                    <h3 className="text-red-400 font-bold text-lg mb-2">Search Failed</h3>
                    <p className="text-gray-300 text-sm leading-relaxed mb-4">{message}</p>

                    <div className="bg-gray-900/50 rounded-lg p-3 text-xs text-gray-400 border border-gray-700/50">
                        <p className="mb-2"><strong className="text-gray-300">Possible reasons:</strong></p>
                        <ul className="list-disc list-inside space-y-1 ml-2">
                            <li>No connection exists between these two people</li>
                            <li>The path is too long (more than 6 degrees)</li>
                            <li>Wikipedia articles don't have enough links</li>
                        </ul>
                    </div>
                </div>

                {onDismiss && (
                    <button
                        onClick={onDismiss}
                        className="flex-shrink-0 text-gray-500 hover:text-white transition-colors text-2xl leading-none p-1"
                        aria-label="Dismiss error"
                    >
                        ×
                    </button>
                )}
            </div>
        </div>
    );
};

export default ErrorMessage;
