import React from 'react';

// ============================================================================
// ICONS
// ============================================================================

const LinkIcon = () => (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
    </svg>
);

const ExternalLinkIcon = () => (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
    </svg>
);

const SparklesIcon = () => (
    <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
        <path d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 00-2.456 2.456zM16.894 20.567L16.5 21.75l-.394-1.183a2.25 2.25 0 00-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 001.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 001.423 1.423l1.183.394-1.183.394a2.25 2.25 0 00-1.423 1.423z" />
    </svg>
);

// ============================================================================
// SUB-COMPONENTS
// ============================================================================

// Animated skeleton for loading context
const ContextSkeleton = () => (
    <div className="flex items-center gap-3 py-3 px-4 bg-gradient-to-r from-purple-900/20 to-indigo-900/20 rounded-xl border border-purple-500/20">
        <div className="flex gap-1.5">
            <span className="w-2 h-2 bg-purple-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
            <span className="w-2 h-2 bg-purple-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
            <span className="w-2 h-2 bg-purple-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
        </div>
        <span className="text-sm text-purple-300/70 italic flex items-center gap-2">
            <SparklesIcon />
            AI generating connection context...
        </span>
    </div>
);

// Beautiful context display with quote styling
const ContextDisplay = ({ context }) => (
    <div className="relative py-3 px-4 bg-gradient-to-r from-indigo-900/30 to-purple-900/30 rounded-xl border border-indigo-500/30 backdrop-blur-sm animate-fadeIn overflow-hidden">
        {/* Decorative gradient overlay */}
        <div className="absolute inset-0 bg-gradient-to-r from-indigo-500/5 via-transparent to-purple-500/5 pointer-events-none" />

        {/* Quote mark */}
        <div className="absolute -top-2 -left-1 text-4xl text-indigo-500/20 font-serif">"</div>

        {/* Content */}
        <p className="relative text-sm text-indigo-100 leading-relaxed pl-4">
            {context}
        </p>

        {/* AI badge */}
        <div className="flex items-center gap-1 mt-2 text-[10px] text-indigo-400/60 uppercase tracking-wider">
            <SparklesIcon />
            <span>AI-Generated Context</span>
        </div>
    </div>
);

// Animated connector between nodes
const ConnectionLine = ({ isLast }) => {
    if (isLast) return null;

    return (
        <div className="absolute left-[11px] top-[72px] bottom-0 w-0.5">
            {/* Animated gradient line */}
            <div className="h-full w-full bg-gradient-to-b from-blue-500 via-purple-500 to-pink-500 opacity-60 animate-pulse"
                style={{ animationDuration: '2s' }} />

            {/* Flowing dots animation */}
            <div className="absolute inset-0 overflow-hidden">
                <div className="absolute w-2 h-2 bg-white rounded-full -left-[3px] animate-flowDown opacity-50"
                    style={{ animationDuration: '1.5s', animationIterationCount: 'infinite' }} />
            </div>
        </div>
    );
};

// Node badge (Start/End/Step)
const NodeBadge = ({ index, total }) => {
    if (index === 0) {
        return (
            <span className="px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider bg-green-500/20 text-green-400 rounded-full border border-green-500/30">
                Start
            </span>
        );
    }
    if (index === total - 1) {
        return (
            <span className="px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider bg-pink-500/20 text-pink-400 rounded-full border border-pink-500/30">
                Target
            </span>
        );
    }
    return (
        <span className="px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider bg-blue-500/20 text-blue-400 rounded-full border border-blue-500/30">
            Step {index}
        </span>
    );
};

// ============================================================================
// MAIN COMPONENT
// ============================================================================

const ResultTimeline = ({ path }) => {
    if (!path || path.length === 0) return null;

    // Handle both old format (array of page objects) and new format (array of {node, edge_context})
    const getPageData = (item) => {
        if (item.node) return item.node;
        return item;
    };

    const getEdgeContext = (item) => {
        if (item.hasOwnProperty('edge_context')) return item.edge_context;
        return undefined;
    };

    return (
        <div className="w-full max-w-2xl mx-auto">
            {/* Header with degree count */}
            <div className="text-center mb-8 animate-fadeInUp">
                <div className="inline-flex items-center gap-3 px-6 py-3 bg-gradient-to-r from-indigo-500/20 via-purple-500/20 to-pink-500/20 rounded-2xl border border-white/10 backdrop-blur-xl">
                    <span className="text-5xl font-black bg-clip-text text-transparent bg-gradient-to-r from-blue-400 via-purple-400 to-pink-400">
                        {path.length - 1}
                    </span>
                    <div className="text-left">
                        <div className="text-lg font-bold text-white">Degrees of</div>
                        <div className="text-lg font-bold text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 to-purple-400">Separation</div>
                    </div>
                </div>
            </div>

            {/* Timeline */}
            <div className="relative pl-8">
                {path.map((item, index) => {
                    const page = getPageData(item);
                    const edgeContext = getEdgeContext(item);
                    const isLoading = edgeContext === null;
                    const hasContext = edgeContext && edgeContext !== null;
                    const isFirst = index === 0;
                    const isLast = index === path.length - 1;

                    // Determine dot color
                    const dotColor = isFirst
                        ? 'bg-green-500 shadow-green-500/50'
                        : isLast
                            ? 'bg-pink-500 shadow-pink-500/50'
                            : 'bg-blue-500 shadow-blue-500/50';

                    return (
                        <div
                            key={index}
                            className="relative pb-8 last:pb-0 animate-fadeInUp"
                            style={{ animationDelay: `${index * 100}ms` }}
                        >
                            {/* Connection Line (animated) */}
                            <ConnectionLine isLast={isLast} />

                            {/* Dot on timeline */}
                            <div className={`absolute left-0 top-6 w-6 h-6 rounded-full ${dotColor} shadow-lg z-10 
                                flex items-center justify-center border-4 border-zinc-900
                                transition-all duration-300 hover:scale-125`}>
                                {isFirst && <span className="text-xs">🚀</span>}
                                {isLast && <span className="text-xs">🎯</span>}
                            </div>

                            {/* Card */}
                            <div className="ml-10">
                                <a
                                    href={page.url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="group block"
                                >
                                    <div className={`
                                        relative overflow-hidden
                                        p-5 rounded-2xl
                                        bg-gradient-to-br from-zinc-800/80 to-zinc-900/80
                                        border border-zinc-700/50
                                        hover:border-purple-500/50
                                        backdrop-blur-xl
                                        shadow-xl hover:shadow-purple-500/10
                                        transition-all duration-300
                                        hover:-translate-y-1
                                    `}>
                                        {/* Shine effect on hover */}
                                        <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/5 to-transparent 
                                            -translate-x-full group-hover:translate-x-full transition-transform duration-700 ease-in-out" />

                                        <div className="relative flex items-center gap-4">
                                            {/* Avatar */}
                                            <div className="relative flex-shrink-0">
                                                {page.image_url ? (
                                                    <img
                                                        src={page.image_url}
                                                        alt={page.title}
                                                        className="w-20 h-20 rounded-2xl object-cover border-2 border-zinc-600 
                                                            group-hover:border-purple-500 transition-colors shadow-lg"
                                                    />
                                                ) : (
                                                    <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-indigo-600 to-purple-600 
                                                        flex items-center justify-center border-2 border-zinc-600 
                                                        group-hover:border-purple-500 transition-colors shadow-lg">
                                                        <span className="text-3xl">👤</span>
                                                    </div>
                                                )}

                                                {/* Wikipedia badge */}
                                                <div className="absolute -bottom-2 -right-2 w-8 h-8 bg-zinc-800 rounded-full 
                                                    flex items-center justify-center border-2 border-zinc-700 shadow-lg">
                                                    <span className="text-sm">W</span>
                                                </div>
                                            </div>

                                            {/* Content */}
                                            <div className="flex-grow min-w-0">
                                                {/* Badge */}
                                                <div className="mb-2">
                                                    <NodeBadge index={index} total={path.length} />
                                                </div>

                                                {/* Title */}
                                                <h3 className="text-xl font-bold text-white group-hover:text-purple-300 
                                                    transition-colors truncate leading-tight">
                                                    {page.title}
                                                </h3>

                                                {/* Wikipedia link hint */}
                                                <p className="text-xs text-zinc-500 mt-1 flex items-center gap-1 
                                                    group-hover:text-purple-400 transition-colors">
                                                    <LinkIcon />
                                                    <span>wikipedia.org</span>
                                                </p>
                                            </div>

                                            {/* External Link Icon */}
                                            <div className="flex-shrink-0 text-zinc-600 group-hover:text-purple-400 
                                                transition-all duration-300 opacity-0 group-hover:opacity-100 
                                                translate-x-2 group-hover:translate-x-0">
                                                <ExternalLinkIcon />
                                            </div>
                                        </div>
                                    </div>
                                </a>

                                {/* Edge Context (between nodes) */}
                                {!isLast && (
                                    <div className="mt-4 mb-2 ml-6">
                                        {/* Connection indicator */}
                                        <div className="flex items-center gap-2 mb-3 text-xs text-zinc-500">
                                            <div className="h-px flex-grow bg-gradient-to-r from-zinc-700 to-transparent" />
                                            <span className="uppercase tracking-widest">Connection</span>
                                            <div className="h-px flex-grow bg-gradient-to-l from-zinc-700 to-transparent" />
                                        </div>

                                        {isLoading ? (
                                            <ContextSkeleton />
                                        ) : hasContext ? (
                                            <ContextDisplay context={edgeContext} />
                                        ) : (
                                            <div className="text-sm text-zinc-500 italic text-center py-2">
                                                Connected via Wikipedia links
                                            </div>
                                        )}
                                    </div>
                                )}
                            </div>
                        </div>
                    );
                })}
            </div>

            {/* Footer */}
            <div className="mt-8 text-center text-xs text-zinc-600 animate-fadeIn">
                <span>Powered by </span>
                <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-purple-400 font-semibold">
                    Six Degrees of Wikipedia
                </span>
            </div>
        </div>
    );
};

export default ResultTimeline;
