import { useState, useEffect, useRef, useCallback } from 'react';
import { Search, X } from 'lucide-react';
import { API_BASE_URL } from '../config';

/**
 * StockSearch - TradingView style stock search component
 * Features:
 * - Real-time search as user types
 * - Dropdown showing matching stocks
 * - Click/keyboard selection
 */
const StockSearch = ({ onSelect, initialValue = 'BBCA' }) => {
    const [query, setQuery] = useState('');
    const [displayValue, setDisplayValue] = useState(initialValue);
    const [results, setResults] = useState([]);
    const [isOpen, setIsOpen] = useState(false);
    const [isLoading, setIsLoading] = useState(false);
    const [selectedIndex, setSelectedIndex] = useState(-1);
    const [isFocused, setIsFocused] = useState(false);

    const wrapperRef = useRef(null);
    const inputRef = useRef(null);
    const debounceRef = useRef(null);

    // Close dropdown when clicking outside
    useEffect(() => {
        const handleClickOutside = (event) => {
            if (wrapperRef.current && !wrapperRef.current.contains(event.target)) {
                setIsOpen(false);
                setIsFocused(false);
            }
        };
        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);

    // Debounced search
    const searchStocks = useCallback(async (searchQuery) => {
        if (!searchQuery || searchQuery.length < 1) {
            setResults([]);
            return;
        }

        setIsLoading(true);
        try {
            const response = await fetch(
                `${API_BASE_URL}/api/v1/search?q=${encodeURIComponent(searchQuery)}&limit=10`
            );
            const data = await response.json();
            setResults(data.results || []);
            setSelectedIndex(-1);
        } catch (error) {
            console.error('Search error:', error);
            setResults([]);
        } finally {
            setIsLoading(false);
        }
    }, []);

    // Handle input change with debounce
    const handleInputChange = (e) => {
        const value = e.target.value.toUpperCase();
        setQuery(value);
        setIsOpen(true);

        if (debounceRef.current) {
            clearTimeout(debounceRef.current);
        }
        debounceRef.current = setTimeout(() => {
            searchStocks(value);
        }, 300);
    };

    // Handle selection
    const handleSelect = (item) => {
        setDisplayValue(item.ticker);
        setQuery('');
        setIsOpen(false);
        setIsFocused(false);
        setResults([]);
        onSelect && onSelect(item.ticker);
    };

    // Keyboard navigation
    const handleKeyDown = (e) => {
        if (!isOpen || results.length === 0) {
            if (e.key === 'Enter') {
                e.preventDefault();
                if (displayValue) {
                    onSelect && onSelect(displayValue);
                }
            }
            return;
        }

        switch (e.key) {
            case 'ArrowDown':
                e.preventDefault();
                setSelectedIndex(prev =>
                    prev < results.length - 1 ? prev + 1 : prev
                );
                break;
            case 'ArrowUp':
                e.preventDefault();
                setSelectedIndex(prev => prev > 0 ? prev - 1 : 0);
                break;
            case 'Enter':
                e.preventDefault();
                if (selectedIndex >= 0 && results[selectedIndex]) {
                    handleSelect(results[selectedIndex]);
                }
                break;
            case 'Escape':
                setIsOpen(false);
                setQuery('');
                setIsFocused(false);
                inputRef.current?.blur();
                break;
            default:
                break;
        }
    };

    // Clear search
    const handleClear = () => {
        setQuery('');
        setResults([]);
        inputRef.current?.focus();
    };

    // Status badge styling
    const getStatusClass = (sector) => {
        const sectorColors = {
            'Banking': 'bg-blue-500/20 text-blue-400',
            'Consumer': 'bg-green-500/20 text-green-400',
            'Mining': 'bg-yellow-500/20 text-yellow-400',
            'Telecom': 'bg-purple-500/20 text-purple-400',
            'Property': 'bg-orange-500/20 text-orange-400',
        };
        return sectorColors[sector] || 'bg-gray-500/20 text-gray-400';
    };

    return (
        <div className="stock-search-container relative" ref={wrapperRef}>
            <div className="relative flex items-center">
                <Search className="absolute left-3 text-gray-500" size={16} />
                <input
                    ref={inputRef}
                    type="text"
                    value={isFocused ? query : displayValue}
                    onChange={handleInputChange}
                    onFocus={() => {
                        setIsFocused(true);
                        setQuery('');
                        setIsOpen(true);
                    }}
                    onBlur={() => {
                        setTimeout(() => {
                            if (!isOpen) {
                                setIsFocused(false);
                            }
                        }, 150);
                    }}
                    onKeyDown={handleKeyDown}
                    placeholder="Search stock..."
                    className="bg-brand-card border border-white/10 rounded-lg pl-10 pr-12 py-2 w-48 focus:outline-none focus:border-brand-accent transition-colors"
                />
                {query && (
                    <button
                        onClick={handleClear}
                        className="absolute right-10 text-gray-500 hover:text-white"
                    >
                        <X size={14} />
                    </button>
                )}
                <span className="absolute right-3 text-gray-500 text-sm">.JK</span>
                {isLoading && (
                    <div className="absolute right-16 w-4 h-4 border-2 border-brand-accent border-t-transparent rounded-full animate-spin" />
                )}
            </div>

            {isOpen && (
                <div className="absolute top-full mt-1 w-80 bg-brand-card border border-white/10 rounded-lg shadow-xl z-50 max-h-80 overflow-y-auto">
                    {results.length === 0 && query && !isLoading && (
                        <div className="p-4 text-center text-gray-500">
                            No results for "{query}"
                        </div>
                    )}

                    {results.length === 0 && !query && (
                        <div className="p-4 text-center text-gray-500 text-sm">
                            Type to search stocks...
                        </div>
                    )}

                    {results.map((item, index) => {
                        // Handle both backend formats (ticker vs symbol)
                        const ticker = item.symbol || item.ticker || "";
                        const name = item.name || "";

                        return (
                            <div
                                key={ticker}
                                className={`flex items-center justify-between p-3 cursor-pointer transition-colors ${index === selectedIndex
                                    ? 'bg-brand-accent/20'
                                    : 'hover:bg-white/5'
                                    }`}
                                onClick={() => handleSelect({ ...item, ticker })}
                                onMouseEnter={() => setSelectedIndex(index)}
                            >
                                <div className="flex items-center gap-3">
                                    <div className="w-8 h-8 rounded-full bg-gradient-to-br from-brand-accent to-blue-500 flex items-center justify-center font-bold text-sm">
                                        {ticker.charAt(0)}
                                    </div>
                                    <div>
                                        <div className="font-semibold">{ticker}</div>
                                        <div className="text-xs text-gray-500 truncate max-w-[180px]">
                                            {name}
                                        </div>
                                    </div>
                                </div>

                                <div className="flex items-center gap-2">
                                    <span className={`text-xs px-2 py-1 rounded ${getStatusClass(item.sector)}`}>
                                        {item.sector || 'Unknown'}
                                    </span>
                                    <span className={`text-xs px-2 py-1 rounded ${item.source === 'yahoo' || item.source === 'yahoo_finance'
                                        ? 'bg-green-500/20 text-green-400'
                                        : 'bg-blue-500/20 text-blue-400'
                                        }`}>
                                        {item.source === 'yahoo' || item.source === 'yahoo_finance' ? '🟢 YF' : '📦 IDX'}
                                    </span>
                                </div>
                            </div>
                        );
                    })}
                </div>
            )}
        </div>
    );
};

export { StockSearch };
export default StockSearch;
