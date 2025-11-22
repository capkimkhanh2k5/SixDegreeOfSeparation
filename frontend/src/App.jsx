import React, { useState } from 'react';
import SearchInput from './SearchInput';
import ResultTimeline from './ResultTimeline';
import StatusConsole from './StatusConsole';
import NeuronAnimation from './NeuronAnimation';

function App() {
  const [startPage, setStartPage] = useState('');
  const [endPage, setEndPage] = useState('');
  const [loading, setLoading] = useState(false);
  const [path, setPath] = useState(null);
  // Removed 'view' state as we now use conditional rendering based on data

  const handleSearch = async () => {
    if (!startPage || !endPage) return;

    setLoading(true);
    setPath(null);

    try {
      const response = await fetch('http://127.0.0.1:8001/api/shortest-path', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ start_page: startPage, end_page: endPage }),
      });

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');

        // Process all complete lines
        for (let i = 0; i < lines.length - 1; i++) {
          const line = lines[i].trim();
          if (line) {
            try {
              const data = JSON.parse(line);

              if (data.status === 'visiting') {
                // Update status console via a custom event or state if StatusConsole was lifted
                // Since StatusConsole manages its own logs via props/internal state, 
                // we need to pass these logs down. 
                // Ideally, we should lift state, but for now let's dispatch a custom event
                // or simply rely on the fact that we are loading.
                // WAIT: StatusConsole currently simulates logs. We need to change that.
                // Let's emit an event that StatusConsole listens to.
                window.dispatchEvent(new CustomEvent('bfs-log', { detail: data }));
              } else if (data.status === 'finished') {
                setPath(data.path);
                setLoading(false);
              } else if (data.status === 'error') {
                alert(data.message);
                setLoading(false);
              } else if (data.status === 'info') {
                window.dispatchEvent(new CustomEvent('bfs-log', { detail: data }));
              }
            } catch (e) {
              console.error("Error parsing JSON line:", e);
            }
          }
        }

        // Keep the last incomplete line in buffer
        buffer = lines[lines.length - 1];
      }

    } catch (error) {
      console.error("Error fetching path:", error);
      alert("Failed to connect to the server.");
      setLoading(false);
    }
  };

  const handleReset = () => {
    setStartPage('');
    setEndPage('');
    setPath(null);
  };

  return (
    <div className="min-h-screen bg-[#0f172a] text-white flex flex-col items-center p-4 font-sans relative overflow-hidden selection:bg-purple-500 selection:text-white">
      {/* Animated Background */}
      <div className="absolute top-0 left-0 w-full h-full overflow-hidden -z-10">
        <div className="absolute top-[-10%] left-[-10%] w-[500px] h-[500px] bg-purple-900/30 rounded-full mix-blend-screen filter blur-3xl opacity-30 animate-blob"></div>
        <div className="absolute top-[-10%] right-[-10%] w-[500px] h-[500px] bg-blue-900/30 rounded-full mix-blend-screen filter blur-3xl opacity-30 animate-blob animation-delay-2000"></div>
        <div className="absolute bottom-[-20%] left-[20%] w-[500px] h-[500px] bg-pink-900/30 rounded-full mix-blend-screen filter blur-3xl opacity-30 animate-blob animation-delay-4000"></div>
      </div>

      <header className="mt-12 mb-8 text-center z-10 space-y-6">
        {/* Modern CapKimKhanh Signature */}
        <div className="relative group inline-block mb-6 hover:scale-105 transition-transform duration-500">
          <div className="absolute -inset-1 bg-gradient-to-r from-cyan-400 via-purple-500 to-pink-500 rounded-lg blur opacity-25 group-hover:opacity-75 transition duration-1000 group-hover:duration-200"></div>
          <div className="relative px-8 py-4 bg-black rounded-lg leading-none flex items-center">
            <span className="text-gray-400 text-xs font-bold uppercase tracking-widest mr-4 border-r border-gray-700 pr-4">
              Architected By
            </span>
            <span className="font-black text-3xl text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 via-purple-400 to-pink-400 animate-gradient-x bg-[length:200%_auto]">
              CapKimKhanh
            </span>
          </div>
        </div>

        <h1 className="text-6xl font-black text-transparent bg-clip-text bg-gradient-to-br from-white via-gray-200 to-gray-500 drop-shadow-2xl tracking-tight">
          Six Degrees
        </h1>

        <p className="text-gray-400 text-lg max-w-2xl mx-auto font-light leading-relaxed">
          Explore the hidden connections between any two people on Wikipedia.
          Powered by <span className="text-purple-400 font-medium">AI-driven analysis</span> to find the shortest factual path through history, politics, and pop culture.
        </p>
      </header>

      <main className="w-full max-w-7xl z-10 grid grid-cols-1 lg:grid-cols-2 gap-8 px-4">

        {/* LEFT PANEL: Search Inputs + Status Console */}
        <div className="bg-gray-900/60 p-8 rounded-3xl shadow-2xl backdrop-blur-xl border border-white/10 transition-all duration-500 hover:border-white/20 flex flex-col h-full min-h-[400px]">
          <div className="grid grid-cols-1 gap-6 mb-8">
            <SearchInput
              label="Start Journey"
              value={startPage}
              onChange={setStartPage}
              placeholder="e.g. Kevin Bacon"
            />
            <SearchInput
              label="Target Destination"
              value={endPage}
              onChange={setEndPage}
              placeholder="e.g. Barack Obama"
            />
          </div>

          <button
            onClick={handleSearch}
            disabled={loading || !startPage || !endPage}
            className={`w-full py-4 rounded-2xl font-bold text-xl tracking-wide transition-all duration-300 transform hover:scale-[1.01] shadow-xl mb-6 ${loading || !startPage || !endPage
              ? 'bg-gray-800 text-gray-500 cursor-not-allowed border border-gray-700'
              : 'bg-gradient-to-r from-indigo-600 via-purple-600 to-pink-600 hover:from-indigo-500 hover:to-pink-500 text-white shadow-purple-900/50 border border-white/10'
              }`}
          >
            {loading ? (
              <span className="flex items-center justify-center gap-3">
                <svg className="animate-spin h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Processing Request...
              </span>
            ) : 'Find Connection'}
          </button>

          {/* Status Console - Always visible */}
          <div className="flex-grow overflow-hidden">
            <StatusConsole loading={loading} />
          </div>
        </div>

        {/* RIGHT PANEL: Neuron Animation (Idle/Loading) OR Result Timeline */}
        <div className="min-h-[400px] lg:h-full transition-all duration-500">
          {path ? (
            // STATE: RESULT - Show Result Timeline
            <div className="bg-gray-900/60 p-8 rounded-3xl shadow-2xl backdrop-blur-xl border border-white/10 h-full animate-fadeInUp flex flex-col">
              <div className="flex justify-between items-center mb-6">
                <h2 className="text-2xl font-bold text-white">Connection Found</h2>
                <button
                  onClick={handleReset}
                  className="px-4 py-2 rounded-lg bg-white/10 hover:bg-white/20 text-sm font-medium transition-colors"
                >
                  Clear Results
                </button>
              </div>
              <div className="flex-grow overflow-y-auto custom-scrollbar">
                <ResultTimeline path={path} />
              </div>
            </div>
          ) : (
            // STATE: IDLE or LOADING - Always show Neuron Animation
            <div className="h-full min-h-[400px]">
              <NeuronAnimation />
            </div>
          )}
        </div>

      </main>

      <footer className="mt-auto py-12 flex flex-col items-center gap-6 w-full max-w-4xl">

        {/* Tech Stack Badges */}
        <div className="flex flex-wrap justify-center gap-3">
          {[
            { name: "Google Gemini 2.5", color: "bg-blue-500/20 text-blue-300 border-blue-500/30" },
            { name: "FastAPI", color: "bg-teal-500/20 text-teal-300 border-teal-500/30" },
            { name: "Bi-directional BFS", color: "bg-purple-500/20 text-purple-300 border-purple-500/30" },
            { name: "React + Vite", color: "bg-cyan-500/20 text-cyan-300 border-cyan-500/30" },
            { name: "Tailwind CSS", color: "bg-pink-500/20 text-pink-300 border-pink-500/30" },
          ].map((tech) => (
            <span key={tech.name} className={`px-4 py-1.5 rounded-full text-xs font-semibold border backdrop-blur-sm ${tech.color}`}>
              {tech.name}
            </span>
          ))}
        </div>

        <div className="flex items-center gap-4 text-gray-500 text-sm font-medium">
          <span>Powered by Wikipedia API</span>
          <span className="w-1 h-1 bg-gray-600 rounded-full"></span>
          <span>v2.0.0 Strict Mode</span>
        </div>
      </footer>
    </div>
  );
}

export default App;
