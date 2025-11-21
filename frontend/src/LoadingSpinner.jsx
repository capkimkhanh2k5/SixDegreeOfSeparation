import React, { useState, useEffect } from 'react';

const FUNNY_TEXTS = [
    "Đang truy cập Wikipedia...",
    "Đang hỏi bác Google...",
    "Đang kết nối các nơ-ron...",
    "Đang tìm đường tắt...",
    "Chờ xíu, mạng hơi lag...",
    "Đang đọc lướt 6 triệu bài viết..."
];

const LoadingSpinner = () => {
    const [textIndex, setTextIndex] = useState(0);

    useEffect(() => {
        const interval = setInterval(() => {
            setTextIndex((prev) => (prev + 1) % FUNNY_TEXTS.length);
        }, 2000);
        return () => clearInterval(interval);
    }, []);

    return (
        <div className="flex flex-col items-center justify-center py-8">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mb-4"></div>
            <p className="text-gray-400 animate-pulse text-lg font-medium">
                {FUNNY_TEXTS[textIndex]}
            </p>
        </div>
    );
};

export default LoadingSpinner;
