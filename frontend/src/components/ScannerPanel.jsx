import { useState, useEffect, useCallback } from 'react';
import { Search, TrendingUp, TrendingDown, Flame, ThermometerSun, Activity, RefreshCw, BarChart3, Target, Zap, X, Users, DollarSign } from 'lucide-react';
import { API_BASE_URL } from '../config';

/**
 * ScannerPanel - Complete Stock Scanner with Full Technical + Bandarmology Analysis
 * 
 * Features:
 * - Card-based UI showing all indicators
 * - Recommendation, Price Targets, Key Indicators
 * - Technical Analysis (MA20, MA50, VWAP, RSI, Stoch)
 * - Bandarmology (Top Buyers/Sellers, Bandar Volume)
 */
export default function ScannerPanel({ onSelectStock, onClose }) {
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
                : `${API_BASE_URL}/api/v1/scanner/volume?min_rvol=${minRvol}&min_value=${minValue}&limit=30`;

            const response = await fetch(endpoint);
            if (!response.ok) throw new Error('Scan failed');

            const data = await response.json();
            setResults(showHotOnly ? data.hot_stocks || data.results : data.results);
            setLastScan(new Date().toLocaleTimeString());
        } catch (err) {
            setError(err.message);
            setResults([]);
        } finally {
            setLoading(false);
        }
    }, [minRvol, minValue, showHotOnly]);

    useEffect(() => {
        scanStocks();
    }, [scanStocks]);

    const getRecommendationBadge = (rec) => {
        const styles = {
            'STRONG BUY': 'bg-emerald-500 text-white',
            'BUY / ACCUMULATE': 'bg-green-500/80 text-white',
            'HOLD': 'bg-gray-500 text-white',
            'REDUCE': 'bg-orange-500 text-white',
            'SELL': 'bg-red-500 text-white'
        };
        return (
            <span className={`px-2 py-1 rounded text-xs font-bold ${styles[rec] || styles['HOLD']}`}>
                {rec}
            </span>
        );
    };

    const getMomentumIndicator = (momentum) => {
        if (momentum === 'bullish') {
            return <div className="flex gap-0.5"><span className="text-green-400">▲</span><span className="text-green-400">▲</span><span className="text-green-400">▲</span></div>;
        } else if (momentum === 'bearish') {
            return <div className="flex gap-0.5"><span className="text-red-400">▼</span><span className="text-red-400">▼</span><span className="text-red-400">▼</span></div>;
        }
        return <div className="flex gap-0.5"><span className="text-gray-400">●</span><span className="text-gray-400">●</span><span className="text-gray-400">●</span></div>;
    };

    const formatPrice = (price) => `Rp ${price?.toLocaleString('id-ID') || 0}`;

    const formatValue = (val) => {
        if (!val) return '0';
        if (val >= 1_000_000_000_000) return `${(val / 1_000_000_000_000).toFixed(1)}T`;
        if (val >= 1_000_000_000) return `${(val / 1_000_000_000).toFixed(1)}B`;
        if (val >= 1_000_000) return `${(val / 1_000_000).toFixed(1)}M`;
        return val.toLocaleString('id-ID');
    };

    const StockCard = ({ stock }) => (
        <div
            onClick={() => onSelectStock && onSelectStock(stock.ticker)}
            className="bg-gray-900/80 border border-gray-700/50 rounded-xl p-4 cursor-pointer 
                       hover:border-emerald-500/50 hover:bg-gray-800/90 transition-all duration-200"
        >
            {/* Header */}
            <div className="flex items-start justify-between mb-3">
                <div>
                    <div className="text-gray-400 text-xs">Ticker</div>
                    <div className="text-white font-bold text-xl">{stock.ticker}</div>
                    <div className="text-gray-500 text-xs truncate max-w-[150px]">{stock.name}</div>
                </div>
                <div className="flex flex-col items-end gap-1">
                    <span className="text-xs text-emerald-400 font-medium">Fresh</span>
                    {getRecommendationBadge(stock.recommendation)}
                </div>
            </div>

            {/* Price & Change */}
            <div className="flex items-center justify-between mb-3">
                <div>
                    <div className="text-gray-400 text-xs">Last close</div>
                    <div className="text-white font-bold text-lg">{formatPrice(stock.price)}</div>
                </div>
                <div className={`text-right ${stock.change_percent >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    <div className="text-xs">% change</div>
                    <div className="font-bold text-lg flex items-center gap-1">
                        {stock.change_percent >= 0 ? <TrendingUp size={16} /> : <TrendingDown size={16} />}
                        {stock.change_percent >= 0 ? '+' : ''}{stock.change_percent?.toFixed(2)}%
                    </div>
                </div>
            </div>

            {/* Recommendation & Momentum */}
            <div className="flex items-center gap-4 mb-3 pb-3 border-b border-gray-700/50">
                <div>
                    <div className="text-gray-400 text-xs flex items-center gap-1">
                        <Zap size={10} /> Recommendation
                    </div>
                    <div className="text-white text-sm font-medium">{stock.recommendation}</div>
                </div>
                <div className="border-l border-gray-700 pl-4">
                    <div className="text-gray-400 text-xs">momentum</div>
                    {getMomentumIndicator(stock.momentum)}
                </div>
            </div>

            {/* Signals */}
            {stock.signals_list && stock.signals_list.length > 0 && (
                <div className="mb-3">
                    <div className="text-gray-400 text-xs mb-1">Signals</div>
                    <div className="flex flex-wrap gap-1">
                        {stock.signals_list.slice(0, 4).map((sig, idx) => (
                            <span key={idx} className={`px-2 py-0.5 rounded text-xs ${sig.includes('ACCUMULATION') ? 'bg-green-500/20 text-green-300' :
                                sig.includes('DISTRIBUTION') ? 'bg-red-500/20 text-red-300' :
                                    sig.includes('OVERBOUGHT') ? 'bg-orange-500/20 text-orange-300' :
                                        sig.includes('OVERSOLD') ? 'bg-blue-500/20 text-blue-300' :
                                            'bg-blue-500/20 text-blue-300'
                                }`}>
                                {sig.replace(/_/g, ' ')}
                            </span>
                        ))}
                    </div>
                </div>
            )}

            {/* Price Targets */}
            {stock.price_targets && (
                <div className="mb-3">
                    <div className="text-gray-400 text-xs mb-2">PRICE TARGETS</div>
                    <div className="grid grid-cols-3 gap-2">
                        <div className="bg-gray-800/50 p-2 rounded text-center">
                            <div className="text-xs text-gray-400">Conservative</div>
                            <div className="text-emerald-400 font-bold text-sm">
                                {formatPrice(stock.price_targets.conservative)}
                            </div>
                            <div className="text-emerald-400/70 text-xs">+5%</div>
                        </div>
                        <div className="bg-gray-800/50 p-2 rounded text-center">
                            <div className="text-xs text-gray-400">Moderate</div>
                            <div className="text-yellow-400 font-bold text-sm">
                                {formatPrice(stock.price_targets.moderate)}
                            </div>
                            <div className="text-yellow-400/70 text-xs">+10%</div>
                        </div>
                        <div className="bg-gray-800/50 p-2 rounded text-center">
                            <div className="text-xs text-gray-400">Aggressive</div>
                            <div className="text-orange-400 font-bold text-sm">
                                {formatPrice(stock.price_targets.aggressive)}
                            </div>
                            <div className="text-orange-400/70 text-xs">+20%</div>
                        </div>
                    </div>
                </div>
            )}

            {/* Technical Analysis */}
            {stock.technicals && (
                <div className="mb-3 pb-3 border-b border-gray-700/50">
                    <div className="text-gray-400 text-xs mb-2 flex items-center gap-1">
                        <BarChart3 size={10} /> Technical Analysis
                    </div>
                    <div className="grid grid-cols-5 gap-1 text-xs">
                        <div className="text-center">
                            <div className="text-gray-500">MA20</div>
                            <div className="text-white font-medium">{stock.technicals.ma20?.toLocaleString('id-ID')}</div>
                        </div>
                        <div className="text-center">
                            <div className="text-gray-500">MA50</div>
                            <div className="text-white font-medium">{stock.technicals.ma50?.toLocaleString('id-ID')}</div>
                        </div>
                        <div className="text-center">
                            <div className="text-gray-500">VWAP</div>
                            <div className={`font-medium ${stock.price > stock.technicals.vwap ? 'text-green-400' : 'text-red-400'}`}>
                                {stock.technicals.vwap?.toLocaleString('id-ID')}
                            </div>
                        </div>
                        <div className="text-center">
                            <div className="text-gray-500">RSI</div>
                            <div className={`font-medium ${stock.technicals.rsi > 70 ? 'text-red-400' :
                                stock.technicals.rsi < 30 ? 'text-green-400' : 'text-white'
                                }`}>
                                {stock.technicals.rsi?.toFixed(1)}
                            </div>
                        </div>
                        <div className="text-center">
                            <div className="text-gray-500">Stoch</div>
                            <div className={`font-medium ${stock.technicals.stoch_k > 80 ? 'text-red-400' :
                                stock.technicals.stoch_k < 20 ? 'text-green-400' : 'text-white'
                                }`}>
                                {stock.technicals.stoch_k?.toFixed(0)}
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* Key Indicators */}
            <div className="mb-3 pb-3 border-b border-gray-700/50">
                <div className="text-gray-400 text-xs mb-2 flex items-center gap-1">
                    <Activity size={10} /> Key Indicators
                </div>
                <div className="grid grid-cols-4 gap-2 text-xs">
                    <div>
                        <span className="text-gray-500">RSI(14)</span>
                        <div className={`font-bold ${stock.key_indicators?.rsi > 70 ? 'text-red-400' :
                            stock.key_indicators?.rsi < 30 ? 'text-green-400' : 'text-white'
                            }`}>
                            {stock.key_indicators?.rsi?.toFixed(1)}
                        </div>
                    </div>
                    <div>
                        <span className="text-gray-500">MACD</span>
                        <div className="text-white font-bold">
                            {stock.key_indicators?.macd?.toFixed(1) || '0.0'}
                        </div>
                    </div>
                    <div>
                        <span className="text-gray-500">Vol Ratio</span>
                        <div className={`font-bold ${stock.key_indicators?.vol_ratio > 2 ? 'text-red-400' :
                            stock.key_indicators?.vol_ratio > 1.5 ? 'text-orange-400' : 'text-white'
                            }`}>
                            {stock.key_indicators?.vol_ratio?.toFixed(2)}x
                        </div>
                    </div>
                    <div>
                        <span className="text-gray-500">Volume</span>
                        <div className="text-blue-400 font-bold">
                            {stock.volume_formatted}
                        </div>
                    </div>
                </div>
            </div>

            {/* Bandarmology */}
            <div>
                <div className="text-gray-400 text-xs mb-2 flex items-center gap-1">
                    <Users size={10} /> Bandarmology
                </div>
                <div className="flex items-center justify-between mb-2">
                    <div className={`px-2 py-1 rounded text-xs font-bold ${stock.bandar_status?.includes('Acc') ? 'bg-green-500/20 text-green-400' :
                        stock.bandar_status?.includes('Dist') ? 'bg-red-500/20 text-red-400' :
                            'bg-gray-500/20 text-gray-400'
                        }`}>
                        {stock.bandar_status || 'NEUTRAL'}
                    </div>
                    {stock.bandar_volume > 0 && (
                        <div className="text-xs text-gray-400">
                            Vol: <span className="text-white font-medium">{formatValue(stock.bandar_volume)}</span>
                        </div>
                    )}
                </div>

                {/* Top Buyers & Sellers */}
                <div className="grid grid-cols-2 gap-2 text-xs">
                    <div>
                        <div className="text-green-400/70 mb-1">Top Buyers</div>
                        {stock.top_buyers?.slice(0, 3).map((b, idx) => (
                            <div key={idx} className="flex justify-between items-center text-green-400">
                                <span title={`${b.name} (${b.category})`}>
                                    {b.code}<span className="text-[10px] text-gray-500 ml-1">({b.name}/{b.category})</span>
                                </span>
                                <span className="text-gray-400">{formatValue(b.val)}</span>
                            </div>
                        ))}
                        {(!stock.top_buyers || stock.top_buyers.length === 0) && (
                            <div className="text-gray-500">-</div>
                        )}
                    </div>
                    <div>
                        <div className="text-red-400/70 mb-1">Top Sellers</div>
                        {stock.top_sellers?.slice(0, 3).map((s, idx) => (
                            <div key={idx} className="flex justify-between items-center text-red-400">
                                <span title={`${s.name} (${s.category})`}>
                                    {s.code}<span className="text-[10px] text-gray-500 ml-1">({s.name}/{s.category})</span>
                                </span>
                                <span className="text-gray-400">{formatValue(s.val)}</span>
                            </div>
                        ))}
                        {(!stock.top_sellers || stock.top_sellers.length === 0) && (
                            <div className="text-gray-500">-</div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );

    return (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 overflow-y-auto">
            <div className="min-h-screen p-4">
                {/* Header */}
                <div className="sticky top-0 bg-gray-900/95 backdrop-blur-sm p-4 rounded-xl mb-4 border border-gray-700/50 z-10">
                    <div className="flex items-center justify-between mb-4">
                        <div className="flex items-center gap-3">
                            <Search size={20} className="text-emerald-400" />
                            <div>
                                <h2 className="font-bold text-lg text-white">Stock Scanner</h2>
                                <p className="text-xs text-gray-400">AI-Powered Market Screening • Technical + Bandarmology</p>
                            </div>
                        </div>
                        <div className="flex items-center gap-2">
                            <button
                                onClick={scanStocks}
                                disabled={loading}
                                className="flex items-center gap-2 px-4 py-2 rounded-lg bg-emerald-500 hover:bg-emerald-600 
                                          disabled:opacity-50 font-medium text-sm transition-colors"
                            >
                                <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
                                Scan Now
                            </button>
                            {onClose && (
                                <button
                                    onClick={onClose}
                                    className="p-2 rounded-lg bg-gray-700 hover:bg-gray-600 transition-colors"
                                >
                                    <X size={18} />
                                </button>
                            )}
                        </div>
                    </div>

                    {/* Filters */}
                    <div className="flex gap-4 flex-wrap items-center">
                        <label className="flex items-center gap-2 text-sm">
                            <span className="text-gray-400">RVOL ≥</span>
                            <select
                                value={minRvol}
                                onChange={(e) => setMinRvol(parseFloat(e.target.value))}
                                className="bg-gray-800 border border-gray-600 rounded px-3 py-1.5 text-white"
                            >
                                <option value="1.0">1.0x</option>
                                <option value="1.5">1.5x</option>
                                <option value="2.0">2.0x</option>
                                <option value="3.0">3.0x</option>
                            </select>
                        </label>

                        <label className="flex items-center gap-2 text-sm">
                            <span className="text-gray-400">Value ≥</span>
                            <select
                                value={minValue}
                                onChange={(e) => setMinValue(parseFloat(e.target.value))}
                                className="bg-gray-800 border border-gray-600 rounded px-3 py-1.5 text-white"
                            >
                                <option value="5">5 Miliar</option>
                                <option value="10">10 Miliar</option>
                                <option value="20">20 Miliar</option>
                                <option value="50">50 Miliar</option>
                            </select>
                        </label>

                        <label className="flex items-center gap-2 cursor-pointer text-sm">
                            <input
                                type="checkbox"
                                checked={showHotOnly}
                                onChange={(e) => setShowHotOnly(e.target.checked)}
                                className="rounded border-gray-600"
                            />
                            <span className="text-gray-400 flex items-center gap-1">
                                <Flame size={14} className="text-red-400" /> HOT stocks only
                            </span>
                        </label>

                        {lastScan && (
                            <div className="text-xs text-gray-500 ml-auto">
                                Last scan: {lastScan} • {results.length} results
                            </div>
                        )}
                    </div>
                </div>

                {/* Results */}
                {loading && (
                    <div className="flex items-center justify-center py-20">
                        <Activity size={32} className="animate-pulse text-emerald-400" />
                        <span className="ml-3 text-gray-400 text-lg">Scanning 800+ stocks with AI...</span>
                    </div>
                )}

                {error && (
                    <div className="text-center py-20 text-red-400">
                        <div className="text-lg font-bold mb-2">Scan Error</div>
                        <div>{error}</div>
                    </div>
                )}

                {!loading && results.length === 0 && (
                    <div className="text-center py-20 text-gray-500">
                        <Target size={48} className="mx-auto mb-4 opacity-50" />
                        <div className="text-lg">No stocks match your criteria</div>
                        <div className="text-sm">Try lowering the RVOL or Value thresholds</div>
                    </div>
                )}

                {!loading && results.length > 0 && (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                        {results.map((stock) => (
                            <StockCard key={stock.ticker} stock={stock} />
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}
