import { useState, useEffect, useCallback } from 'react';
import { Search, TrendingUp, TrendingDown, Flame, ThermometerSun, Activity, RefreshCw } from 'lucide-react';
import { API_BASE_URL } from '../config';

/**
 * ScannerPanel - Volume Scanner for Remora-Quant
 * 
 * Scans stocks for abnormal volume (RVOL) to detect Smart Money activity.
 * Based on riset criteria: RVOL > 2x, Value > 20 Miliar
 */
export default function ScannerPanel({ onSelectStock }) {
    const [results, setResults] = useState([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [lastScan, setLastScan] = useState(null);

    // Filters
    const [minRvol, setMinRvol] = useState(1.5);
    const [minValue, setMinValue] = useState(10);
    const [showHotOnly, setShowHotOnly] = useState(false);

    const scanStocks = useCallback(async () => {
        setLoading(true);
        setError(null);

        try {
            const endpoint = showHotOnly
                ? `${API_BASE_URL}/api/v1/scanner/hot`
                : `${API_BASE_URL}/api/v1/scanner/volume?min_rvol=${minRvol}&min_value=${minValue}`;

            const response = await fetch(endpoint);
            if (!response.ok) throw new Error('Scan failed');

            const data = await response.json();
            setResults(showHotOnly ? data.hot_stocks : data.results);
            setLastScan(new Date().toLocaleTimeString());
        } catch (err) {
            setError(err.message);
            setResults([]);
        } finally {
            setLoading(false);
        }
    }, [minRvol, minValue, showHotOnly]);

    // Auto-scan on mount
    useEffect(() => {
        scanStocks();
    }, [scanStocks]);

    const getSignalBadge = (signal) => {
        switch (signal) {
            case 'HOT':
                return (
                    <span className="flex items-center gap-1 px-2 py-1 rounded text-xs font-bold bg-red-500/20 text-red-400">
                        <Flame size={12} /> HOT
                    </span>
                );
            case 'WARM':
                return (
                    <span className="flex items-center gap-1 px-2 py-1 rounded text-xs font-bold bg-orange-500/20 text-orange-400">
                        <ThermometerSun size={12} /> WARM
                    </span>
                );
            default:
                return (
                    <span className="px-2 py-1 rounded text-xs bg-gray-500/20 text-gray-400">
                        NORMAL
                    </span>
                );
        }
    };

    const formatValue = (value) => {
        if (value >= 1000) return `${(value / 1000).toFixed(1)}T`;
        return `${value.toFixed(1)}M`;
    };

    return (
        <div className="scanner-panel glass-card">
            <div className="p-3 border-b border-white/10">
                <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                        <Search size={16} className="text-brand-accent" />
                        <h3 className="font-semibold text-sm">Volume Scanner</h3>
                    </div>
                    <button
                        onClick={scanStocks}
                        disabled={loading}
                        className="flex items-center gap-1 px-2 py-1 rounded text-xs bg-brand-accent hover:bg-brand-accent/80 disabled:opacity-50"
                    >
                        <RefreshCw size={12} className={loading ? 'animate-spin' : ''} />
                        Scan
                    </button>
                </div>

                {/* Filters */}
                <div className="flex gap-2 flex-wrap text-xs">
                    <label className="flex items-center gap-1">
                        <span className="text-gray-400">RVOL ≥</span>
                        <select
                            value={minRvol}
                            onChange={(e) => setMinRvol(parseFloat(e.target.value))}
                            className="bg-gray-800 border border-gray-700 rounded px-2 py-1"
                        >
                            <option value="1.0">1.0x</option>
                            <option value="1.5">1.5x</option>
                            <option value="2.0">2.0x</option>
                            <option value="3.0">3.0x</option>
                        </select>
                    </label>

                    <label className="flex items-center gap-1">
                        <span className="text-gray-400">Value ≥</span>
                        <select
                            value={minValue}
                            onChange={(e) => setMinValue(parseFloat(e.target.value))}
                            className="bg-gray-800 border border-gray-700 rounded px-2 py-1"
                        >
                            <option value="5">5M</option>
                            <option value="10">10M</option>
                            <option value="20">20M</option>
                            <option value="50">50M</option>
                        </select>
                    </label>

                    <label className="flex items-center gap-2 cursor-pointer">
                        <input
                            type="checkbox"
                            checked={showHotOnly}
                            onChange={(e) => setShowHotOnly(e.target.checked)}
                            className="rounded"
                        />
                        <span className="text-gray-400">HOT only</span>
                    </label>
                </div>

                {lastScan && (
                    <div className="text-xs text-gray-500 mt-2">
                        Last scan: {lastScan} • {results.length} results
                    </div>
                )}
            </div>

            <div className="p-3 max-h-96 overflow-y-auto">
                {loading && (
                    <div className="flex items-center justify-center py-8">
                        <Activity size={24} className="animate-pulse text-brand-accent" />
                        <span className="ml-2 text-gray-400">Scanning {showHotOnly ? 'hot' : 'all'} stocks...</span>
                    </div>
                )}

                {error && (
                    <div className="text-center py-8 text-red-400">
                        Error: {error}
                    </div>
                )}

                {!loading && results.length === 0 && (
                    <div className="text-center py-8 text-gray-500">
                        No stocks match criteria. Try lower thresholds.
                    </div>
                )}

                {!loading && results.length > 0 && (
                    <div className="space-y-2">
                        {results.map((stock, idx) => (
                            <div
                                key={stock.ticker}
                                onClick={() => onSelectStock && onSelectStock(stock.ticker)}
                                className="p-3 bg-gray-800/50 hover:bg-gray-800 rounded-lg cursor-pointer transition-all border border-transparent hover:border-brand-accent/30"
                            >
                                <div className="flex items-center justify-between mb-2">
                                    <div className="flex items-center gap-2">
                                        <span className="font-bold text-white">{stock.ticker}</span>
                                        {getSignalBadge(stock.signal)}
                                    </div>
                                    <div className={`flex items-center gap-1 text-sm font-semibold ${stock.change_percent >= 0 ? 'text-green-400' : 'text-red-400'
                                        }`}>
                                        {stock.change_percent >= 0 ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
                                        {stock.change_percent >= 0 ? '+' : ''}{stock.change_percent}%
                                    </div>
                                </div>

                                <div className="text-xs text-gray-400 mb-2 truncate">
                                    {stock.name || stock.ticker}
                                </div>

                                <div className="grid grid-cols-3 gap-2 text-xs">
                                    <div>
                                        <span className="text-gray-500">RVOL</span>
                                        <div className={`font-bold ${stock.rvol >= 2 ? 'text-red-400' : stock.rvol >= 1.5 ? 'text-orange-400' : 'text-gray-300'}`}>
                                            {stock.rvol}x
                                        </div>
                                    </div>
                                    <div>
                                        <span className="text-gray-500">Value</span>
                                        <div className="font-bold text-blue-400">
                                            Rp {formatValue(stock.value_miliar)}
                                        </div>
                                    </div>
                                    <div>
                                        <span className="text-gray-500">Price</span>
                                        <div className="font-bold text-white">
                                            {stock.price?.toLocaleString('id-ID')}
                                        </div>
                                    </div>
                                </div>

                                {stock.signal_reason && stock.signal !== 'NORMAL' && (
                                    <div className="mt-2 text-xs text-gray-500 italic">
                                        {stock.signal_reason}
                                    </div>
                                )}
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}
