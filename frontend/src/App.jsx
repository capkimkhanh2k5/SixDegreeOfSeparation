import React, { useState } from 'react';
import SearchInput from './SearchInput';
import LoadingSpinner from './LoadingSpinner';
import ResultTimeline from './ResultTimeline';

function App() {
  const [startPage, setStartPage] = useState('');
  const [endPage, setEndPage] = useState('');
  const [loading, setLoading] = useState(false);
  const [path, setPath] = useState(null);

  const handleSearch = async () => {
    if (!startPage || !endPage) return;

    setLoading(true);
    setPath(null);

    // Mock API call
    setTimeout(() => {
      setLoading(false);
      // Mock result
      setPath([startPage, "Tuple", "Mathematics", "Logic", endPage]);
    }, 3000);
  };

  return (
    <div className="min-h-screen bg-gray-900 text-white flex flex-col items-center p-4 font-sans">
      <header className="mt-10 mb-12 text-center">
        <h1 className="text-5xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-purple-600 mb-2">
          Six Degrees of Wikipedia
        </h1>
        <p className="text-gray-400 text-lg">
          Find the shortest path between any two pages.
        </p>
      </header>

      <main className="w-full max-w-2xl bg-gray-800/50 p-8 rounded-2xl shadow-2xl backdrop-blur-sm border border-gray-700">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
          <SearchInput
            label="Start Person / Page"
            value={startPage}
            onChange={setStartPage}
            placeholder="e.g. Kevin Bacon"
          />
          <SearchInput
            label="Target Person / Page"
            value={endPage}
            onChange={setEndPage}
            placeholder="e.g. Barack Obama"
          />
        </div>

        <button
          onClick={handleSearch}
          disabled={loading || !startPage || !endPage}
          className={`w-full py-3 rounded-lg font-bold text-lg transition-all transform hover:scale-[1.02] ${loading || !startPage || !endPage
              ? 'bg-gray-700 text-gray-500 cursor-not-allowed'
              : 'bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-500 hover:to-purple-500 text-white shadow-lg hover:shadow-blue-500/25'
            }`}
        >
          {loading ? 'Searching...' : 'Find Path'}
        </button>

        <div className="mt-8 min-h-[200px] flex justify-center">
          {loading && <LoadingSpinner />}
          {!loading && path && <ResultTimeline path={path} />}
        </div>
      </main>

      <footer className="mt-auto py-6 text-gray-500 text-sm">
        Built with React, Tailwind & Python
      </footer>
    </div>
  );
}

export default App;
