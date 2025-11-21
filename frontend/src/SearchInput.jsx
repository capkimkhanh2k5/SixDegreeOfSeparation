import React, { useState, useEffect, useRef } from 'react';

const SearchInput = ({ label, value, onChange, placeholder }) => {
    const [suggestions, setSuggestions] = useState([]);
    const [showSuggestions, setShowSuggestions] = useState(false);
    const wrapperRef = useRef(null);

    useEffect(() => {
        const fetchSuggestions = async () => {
            if (value.length > 1) {
                try {
                    const response = await fetch(`http://127.0.0.1:8001/api/search?q=${encodeURIComponent(value)}`);
                    if (response.ok) {
                        const data = await response.json();
                        setSuggestions(data);
                        setShowSuggestions(true);
                    }
                } catch (error) {
                    console.error("Error fetching suggestions:", error);
                }
            } else {
                setSuggestions([]);
                setShowSuggestions(false);
            }
        };

        const timeoutId = setTimeout(fetchSuggestions, 300); // Debounce
        return () => clearTimeout(timeoutId);
    }, [value]);

    // Close suggestions when clicking outside
    useEffect(() => {
        const handleClickOutside = (event) => {
            if (wrapperRef.current && !wrapperRef.current.contains(event.target)) {
                setShowSuggestions(false);
            }
        };
        document.addEventListener("mousedown", handleClickOutside);
        return () => document.removeEventListener("mousedown", handleClickOutside);
    }, [wrapperRef]);

    const handleSelect = (suggestion) => {
        onChange(suggestion);
        setShowSuggestions(false);
    };

    return (
        <div className="relative mb-6 w-full" ref={wrapperRef}>
            <label className="block text-sm font-semibold text-blue-200 mb-2 uppercase tracking-wider">{label}</label>
            <div className="relative group">
                <div className="absolute -inset-0.5 bg-gradient-to-r from-pink-600 to-purple-600 rounded-xl opacity-75 group-hover:opacity-100 transition duration-1000 group-hover:duration-200 animate-tilt blur"></div>
                <input
                    type="text"
                    value={value}
                    onChange={(e) => onChange(e.target.value)}
                    placeholder={placeholder}
                    className="relative w-full px-5 py-3 bg-gray-900/90 border border-gray-700/50 rounded-xl focus:ring-2 focus:ring-purple-500 focus:outline-none text-white placeholder-gray-500 backdrop-blur-xl transition-all shadow-xl"
                    onFocus={() => value.length > 1 && setShowSuggestions(true)}
                />
            </div>

            {showSuggestions && suggestions.length > 0 && (
                <ul className="absolute z-50 w-full bg-gray-900/95 border border-gray-700/50 rounded-xl mt-2 max-h-60 overflow-y-auto shadow-2xl backdrop-blur-xl divide-y divide-gray-800 animate-fadeIn">
                    {suggestions.map((suggestion, index) => (
                        <li
                            key={index}
                            onClick={() => handleSelect(suggestion)}
                            className="px-5 py-3 hover:bg-purple-600/20 hover:text-purple-300 cursor-pointer text-gray-300 transition-colors duration-200 flex items-center"
                        >
                            <span className="mr-2 text-gray-500">🔍</span>
                            {suggestion}
                        </li>
                    ))}
                </ul>
            )}
        </div>
    );
};

export default SearchInput;
