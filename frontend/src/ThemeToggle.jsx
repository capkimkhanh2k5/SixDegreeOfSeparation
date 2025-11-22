import React, { useState, useEffect } from 'react';

const ThemeToggle = () => {
    const [theme, setTheme] = useState('light');

    useEffect(() => {
        // Check local storage or system preference
        if (localStorage.theme === 'dark' || (!('theme' in localStorage) && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
            setTheme('dark');
            document.documentElement.classList.add('dark');
        } else {
            setTheme('light');
            document.documentElement.classList.remove('dark');
        }
    }, []);

    const toggleTheme = () => {
        if (theme === 'light') {
            setTheme('dark');
            document.documentElement.classList.add('dark');
            localStorage.theme = 'dark';
        } else {
            setTheme('light');
            document.documentElement.classList.remove('dark');
            localStorage.theme = 'light';
        }
    };

    return (
        <button
            onClick={toggleTheme}
            data-testid="theme-btn"
            className="relative p-2 rounded-full bg-white/20 dark:bg-black/20 backdrop-blur-lg border border-white/30 dark:border-white/10 shadow-lg hover:scale-110 transition-all duration-300 group"
            aria-label="Toggle Dark Mode"
        >
            <div className="relative w-6 h-6 overflow-hidden">
                {/* Sun Icon */}
                <svg
                    className={`absolute inset-0 w-full h-full text-amber-400 transform transition-all duration-500 ${theme === 'dark' ? 'rotate-90 opacity-0 scale-0' : 'rotate-0 opacity-100 scale-100'}`}
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
                </svg>

                {/* Moon Icon */}
                <svg
                    className={`absolute inset-0 w-full h-full text-indigo-300 transform transition-all duration-500 ${theme === 'light' ? '-rotate-90 opacity-0 scale-0' : 'rotate-0 opacity-100 scale-100'}`}
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
                </svg>
            </div>

            {/* Glow Effect */}
            <div className={`absolute inset-0 rounded-full blur-md transition-opacity duration-500 ${theme === 'dark' ? 'bg-indigo-500/30' : 'bg-amber-400/30'} opacity-0 group-hover:opacity-100`} />
        </button>
    );
};

export default ThemeToggle;
