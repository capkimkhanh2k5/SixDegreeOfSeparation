import React, { useState, useEffect } from 'react';

const MOCK_SUGGESTIONS = [
    "Python (programming language)",
    "Philosophy",
    "Kevin Bacon",
    "Barack Obama",
    "Albert Einstein",
    "Vietnam",
    "Artificial intelligence",
    "Google",
    "React (software)",
    "Tailwind CSS"
];

const SearchInput = ({ label, value, onChange, placeholder }) => {
    const [suggestions, setSuggestions] = useState([]);
    const [showSuggestions, setShowSuggestions] = useState(false);

    useEffect(() => {
        if (value.length > 1) {
            const filtered = MOCK_SUGGESTIONS.filter(item =>
                item.toLowerCase().includes(value.toLowerCase())
            );
            setSuggestions(filtered);
            setShowSuggestions(true);
        } else {
            setSuggestions([]);
            setShowSuggestions(false);
        }
    }, [value]);

    const handleSelect = (suggestion) => {
        onChange(suggestion);
        setShowSuggestions(false);
    };

    return (
        <div className="relative mb-4 w-full">
            <label className="block text-sm font-medium text-gray-300 mb-1">{label}</label>
            <input
                type="text"
                value={value}
                onChange={(e) => onChange(e.target.value)}
                placeholder={placeholder}
                className="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg focus:ring-2 focus:ring-blue-500 focus:outline-none text-white placeholder-gray-500"
                onBlur={() => setTimeout(() => setShowSuggestions(false), 200)}
                onFocus={() => value.length > 1 && setShowSuggestions(true)}
            />

            {showSuggestions && suggestions.length > 0 && (
                <ul className="absolute z-10 w-full bg-gray-800 border border-gray-700 rounded-lg mt-1 max-h-60 overflow-y-auto shadow-lg">
                    {suggestions.map((suggestion, index) => (
                        <li
                            key={index}
                            onClick={() => handleSelect(suggestion)}
                            className="px-4 py-2 hover:bg-gray-700 cursor-pointer text-gray-200"
                        >
                            {suggestion}
                        </li>
                    ))}
                </ul>
            )}
        </div>
    );
};

export default SearchInput;
