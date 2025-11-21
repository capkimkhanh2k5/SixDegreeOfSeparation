import React from 'react';

const ResultTimeline = ({ path }) => {
    if (!path || path.length === 0) return null;

    return (
        <div className="mt-4 w-full max-w-xl animate-fadeInUp">
            <h2 className="text-3xl font-bold text-center mb-10 text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-purple-400">
                {path.length - 1} Degrees of Separation
            </h2>
            <div className="relative border-l-2 border-purple-500/30 ml-8 space-y-0 pb-2">
                {path.map((page, index) => (
                    <div
                        key={index}
                        className="relative pl-10 pb-12 last:pb-0 group"
                        style={{ animationDelay: `${index * 150}ms` }}
                    >
                        {/* Dot */}
                        <div className={`absolute -left-[9px] top-6 p-1 rounded-full border-4 border-gray-900 transition-transform duration-300 group-hover:scale-125 ${index === 0 ? 'bg-green-500 shadow-[0_0_15px_rgba(34,197,94,0.5)]' :
                                index === path.length - 1 ? 'bg-pink-500 shadow-[0_0_15px_rgba(236,72,153,0.5)]' :
                                    'bg-blue-500 shadow-[0_0_10px_rgba(59,130,246,0.5)]'
                            } h-5 w-5 z-10`}></div>

                        {/* Card */}
                        <a
                            href={page.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="block bg-gray-800/50 p-4 rounded-2xl shadow-lg border border-gray-700/50 hover:border-purple-500/50 hover:bg-gray-800/80 transition-all duration-300 backdrop-blur-sm transform hover:-translate-y-1 group/card"
                        >
                            <div className="flex items-center gap-5">
                                {/* Image */}
                                <div className="relative flex-shrink-0">
                                    {page.image_url ? (
                                        <img
                                            src={page.image_url}
                                            alt={page.title}
                                            className="w-16 h-16 rounded-full object-cover border-2 border-gray-600 group-hover/card:border-purple-500 transition-colors shadow-md"
                                        />
                                    ) : (
                                        <div className="w-16 h-16 rounded-full bg-gradient-to-br from-gray-700 to-gray-600 flex items-center justify-center border-2 border-gray-600 group-hover/card:border-purple-500 transition-colors shadow-md">
                                            <span className="text-2xl">📄</span>
                                        </div>
                                    )}
                                </div>

                                {/* Content */}
                                <div className="flex-grow">
                                    <h3 className="text-xl font-bold text-white tracking-tight group-hover/card:text-purple-300 transition-colors">
                                        {page.title}
                                    </h3>
                                    {index < path.length - 1 && (
                                        <p className="text-xs font-semibold text-purple-400 mt-1 uppercase tracking-widest opacity-70 flex items-center gap-1">
                                            <span>↓</span> links to
                                        </p>
                                    )}
                                </div>

                                {/* External Link Icon */}
                                <div className="text-gray-500 group-hover/card:text-white transition-colors opacity-0 group-hover/card:opacity-100">
                                    <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                                    </svg>
                                </div>
                            </div>
                        </a>
                    </div>
                ))}
            </div>
        </div>
    );
};

export default ResultTimeline;
