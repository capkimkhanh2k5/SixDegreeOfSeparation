import React, { useState } from 'react';
import SearchInput from './SearchInput';
import ResultTimeline from './ResultTimeline';
import StatusConsole from './StatusConsole';
import NeuronAnimation from './NeuronAnimation';
import ErrorMessage from './ErrorMessage';
import ThemeToggle from './ThemeToggle';

function App() {
  const [startPage, setStartPage] = useState('');
  const [endPage, setEndPage] = useState('');
  const [loading, setLoading] = useState(false);
  const [path, setPath] = useState(null);
  const [error, setError] = useState(null);
  // Removed 'view' state as we now use conditional rendering based on data

  const handleSearch = async () => {
    if (!startPage || !endPage) return;

    setLoading(true);
    setPath(null);
    setError(null); // Clear previous errors

    try {
      const response = await fetch('/api/shortest-path', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ start_page: startPage, end_page: endPage }),
      });

      if (!response.ok) {
        throw new Error('Network response was not ok');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.trim()) {
            try {
              const data = JSON.parse(line);

              if (data.status === 'finished') {
                // PROGRESSIVE STREAMING: Set path immediately with null contexts
                // The path_with_context has structure: [{node: {...}, edge_context: null/string}, ...]
                const pathData = data.path_with_context || data.path;
                setPath(pathData);
                setLoading(false);
                console.log('[PROGRESSIVE] Path received immediately!', pathData.length, 'nodes');

              } else if (data.status === 'context_update') {
                // PROGRESSIVE STREAMING: Update specific edge context
                // Immutably update the path state
                setPath(prevPath => {
                  if (!prevPath) return prevPath;
                  const newPath = [...prevPath];
                  if (data.edge_index >= 0 && data.edge_index < newPath.length) {
                    newPath[data.edge_index] = {
                      ...newPath[data.edge_index],
                      edge_context: data.context
                    };
                  }
                  return newPath;
                });
                console.log(`[PROGRESSIVE] Context ${data.edge_index + 1} updated:`, data.context?.substring(0, 50) + '...');

              } else if (data.status === 'heartbeat') {
                // Heartbeat - keep connection alive, optionally log
                console.log(`[HEARTBEAT] ${data.time}s - ${data.message || 'alive'}`);
                window.dispatchEvent(new CustomEvent('bfs-log', { detail: data }));

              } else if (data.status === 'exploring') {
                // BFS exploration update
                window.dispatchEvent(new CustomEvent('bfs-log', { detail: data }));

              } else if (data.status === 'error') {
                setError(data.message);
                setLoading(false);

              } else if (data.status === 'info' || data.status === 'visiting') {
                window.dispatchEvent(new CustomEvent('bfs-log', { detail: data }));
              }
            } catch (e) {
              console.error('Error parsing JSON:', e);
            }
          }
        }
      }
    } catch (error) {
      console.error('Error fetching data:', error);
      setError("Connection failed. Please check if backend is running.");
      setLoading(false);
    }
  };

  const handleReset = () => {
    setStartPage('');
    setEndPage('');
    setPath(null);
    setError(null);
  };

  return (
    <div className="relative min-h-screen overflow-hidden transition-colors duration-500 bg-gray-50 dark:bg-gray-900 font-sans">

      {/* Animated Background Mesh */}
      <div className="absolute inset-0 z-0 overflow-hidden pointer-events-none">
        <div className="absolute top-[-10%] left-[-10%] w-[50%] h-[50%] rounded-full bg-purple-400/20 dark:bg-purple-900/20 blur-[100px] animate-blob mix-blend-multiply dark:mix-blend-screen" />
        <div className="absolute top-[-10%] right-[-10%] w-[50%] h-[50%] rounded-full bg-blue-400/20 dark:bg-blue-900/20 blur-[100px] animate-blob animation-delay-2000 mix-blend-multiply dark:mix-blend-screen" />
        <div className="absolute bottom-[-20%] left-[20%] w-[60%] h-[60%] rounded-full bg-pink-400/20 dark:bg-pink-900/20 blur-[100px] animate-blob animation-delay-4000 mix-blend-multiply dark:mix-blend-screen" />
      </div>

      <div className="relative z-10 container mx-auto px-4 py-8 flex flex-col min-h-screen">

        {/* Top Navigation */}
        <header className="flex justify-between items-center mb-8">
          {/* Logo Area */}
          <div className="flex items-center gap-3">
            <div className="p-2 bg-white/30 dark:bg-white/10 backdrop-blur-md rounded-xl border border-white/50 dark:border-white/10 shadow-lg">
              <svg className="w-8 h-8 text-indigo-600 dark:text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
            <div className="flex flex-col">
              <h1 className="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-indigo-600 via-purple-600 to-pink-600 dark:from-indigo-400 dark:via-purple-400 dark:to-pink-400 animate-text-shimmer bg-[length:200%_auto]">
                Six Degrees
              </h1>
              <span className="text-xs font-medium text-gray-500 dark:text-gray-400 tracking-wider">
                BY <span className="font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-500 to-teal-400 animate-pulse">CAP KIM KHANH</span>
              </span>
            </div>
          </div>
          <ThemeToggle />
        </header>

        {/* Main Content Grid */}
        <main className="flex-grow grid grid-cols-1 lg:grid-cols-2 gap-8 items-start">

          {/* LEFT COLUMN: Inputs & Controls */}
          <div className="space-y-6 animate-fadeInLeft">

            <div className="bg-white/40 dark:bg-gray-800/40 backdrop-blur-xl rounded-3xl p-8 shadow-2xl border border-white/50 dark:border-white/10">
              <div className="space-y-6">
                <div>
                  <h2 className="text-3xl font-extrabold text-gray-900 dark:text-white mb-2">
                    Start Search
                  </h2>
                  <p className="text-gray-600 dark:text-gray-300 text-sm">
                    Find the shortest path between any two Wikipedia articles.
                  </p>
                </div>

                <div className="space-y-4">
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-gray-700 dark:text-gray-300 ml-1">Start Article</label>
                    <SearchInput
                      value={startPage}
                      onChange={setStartPage}
                      placeholder="e.g., Taylor Swift"
                    />
                  </div>

                  <div className="space-y-2">
                    <label className="text-sm font-medium text-gray-700 dark:text-gray-300 ml-1">Target Article</label>
                    <SearchInput
                      value={endPage}
                      onChange={setEndPage}
                      placeholder="e.g., Kevin Bacon"
                    />
                  </div>
                </div>

                <button
                  onClick={handleSearch}
                  disabled={loading || !startPage || !endPage}
                  className={`
                    w-full group relative px-8 py-4 rounded-2xl font-bold text-lg shadow-xl transition-all duration-300
                    ${loading || !startPage || !endPage
                      ? 'bg-gray-200 dark:bg-gray-700 text-gray-400 dark:text-gray-500 cursor-not-allowed'
                      : 'bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white hover:scale-[1.02] hover:shadow-indigo-500/25'
                    }
                  `}
                >
                  {loading ? (
                    <div className="flex items-center justify-center gap-2">
                      <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                      <span>Searching...</span>
                    </div>
                  ) : (
                    <span className="flex items-center justify-center gap-2">
                      Find Connection
                      <svg className="w-5 h-5 group-hover:translate-x-1 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17 8l4 4m0 0l-4 4m4-4H3" />
                      </svg>
                    </span>
                  )}
                </button>
              </div>
            </div>

            {/* Status Console (Always visible or conditional?) - User said "below is the table showing process" */}
            <div className="h-[300px]">
              <StatusConsole loading={loading} />
            </div>

            {error && (
              <ErrorMessage
                message={error}
                onDismiss={() => setError(null)}
              />
            )}

          </div>

          {/* RIGHT COLUMN: Visualization / Results */}
          <div className="relative h-full min-h-[500px] bg-white/20 dark:bg-gray-800/20 backdrop-blur-sm rounded-3xl border border-white/30 dark:border-white/5 overflow-hidden flex flex-col animate-fadeInRight">

            {!path ? (
              <div className="absolute inset-0 flex flex-col items-center justify-center p-6 text-center overflow-hidden">
                <div className="w-full h-full absolute inset-0">
                  <NeuronAnimation />
                </div>
              </div>
            ) : (
              <div className="flex-grow flex flex-col p-6 overflow-y-auto custom-scrollbar">
                <div className="flex justify-between items-center mb-6">
                  <h2 className="text-2xl font-bold text-gray-900 dark:text-white">Connection Found!</h2>
                  <button
                    onClick={handleReset}
                    className="px-4 py-2 rounded-xl bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-300 dark:hover:bg-gray-600 transition-colors font-medium text-sm"
                  >
                    Reset
                  </button>
                </div>
                <ResultTimeline path={path} />
              </div>
            )}
          </div>

        </main>

        <footer className="mt-8 py-6 flex flex-col items-center gap-4 w-full border-t border-gray-200 dark:border-gray-800">
          <div className="flex items-center gap-4 text-gray-500 text-sm font-medium">
            <span>Powered by Wikipedia API</span>
            <span className="w-1 h-1 bg-gray-600 rounded-full"></span>
            <span>v2.1.0 Premium UI</span>
          </div>
        </footer>
      </div>
    </div>
  );
}

export default App;
