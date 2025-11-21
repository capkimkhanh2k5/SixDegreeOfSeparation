import React from 'react';

const ResultTimeline = ({ path }) => {
    if (!path || path.length === 0) return null;

    return (
        <div className="mt-8 w-full max-w-md">
            <h2 className="text-2xl font-bold text-center mb-6 text-blue-400">
                Found Path ({path.length - 1} degrees)
            </h2>
            <div className="relative border-l-2 border-blue-500 ml-6 space-y-8 pb-2">
                {path.map((page, index) => (
                    <div key={index} className="mb-8 flex items-center w-full">
                        <div className="absolute -left-3 bg-gray-900 p-1">
                            <div className={`h-4 w-4 rounded-full ${index === 0 || index === path.length - 1 ? 'bg-green-500' : 'bg-blue-500'}`}></div>
                        </div>
                        <div className="ml-6 bg-gray-800 p-4 rounded-lg shadow-md w-full border border-gray-700 hover:border-blue-500 transition-colors">
                            <h3 className="text-lg font-semibold text-white">{page}</h3>
                            {index < path.length - 1 && (
                                <p className="text-sm text-gray-500 mt-1">
                                    ↓ links to
                                </p>
                            )}
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
};

export default ResultTimeline;
