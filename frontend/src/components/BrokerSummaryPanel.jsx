import { useState, useEffect } from 'react';
import { Users, TrendingUp, TrendingDown, Minus, Building2, ArrowUpRight, ArrowDownRight, Calendar, RefreshCw, Upload } from 'lucide-react';
import BrokerDetailModal from './BrokerDetailModal';
import FileUploadPanel from './FileUploadPanel';
import { API_BASE_URL } from '../config';

// Loading Skeleton Component
const BrokerSummarySkeleton = () => (
    <div className="glass-card animate-pulse">
        <div className="p-3 border-b border-white/10 flex justify-between">
            <div className="h-5 w-32 bg-gray-700/50 rounded"></div>
            <div className="h-5 w-20 bg-gray-700/50 rounded"></div>
        </div>
        <div className="flex border-b border-white/10">
            <div className="flex-1 py-4 border-r border-white/10"></div>
            <div className="flex-1 py-4 border-r border-white/10"></div>
            <div className="flex-1 py-4"></div>
        </div>
        <div className="p-3 space-y-4">
            <div className="grid grid-cols-2 gap-3">
                <div className="h-16 bg-gray-700/30 rounded-lg"></div>
                <div className="h-16 bg-gray-700/30 rounded-lg"></div>
            </div>
            <div className="h-12 bg-gray-700/30 rounded-lg"></div>
            <div className="space-y-2">
                <div className="h-4 w-24 bg-gray-700/50 rounded"></div>
                <div className="h-8 bg-gray-700/30 rounded"></div>
                <div className="h-8 bg-gray-700/30 rounded"></div>
            </div>
        </div>
    </div>
);

/**
 * BrokerSummaryPanel - Stockbit-style Broker Summary visualization
 * Features: Horizontal volume bars, tabular layout, type indicators, date filtering
 */
function BrokerSummaryPanel({ data, ticker, isLoading }) {
    const [selectedBroker, setSelectedBroker] = useState(null);
    const [activeTab, setActiveTab] = useState('summary'); // 'summary' | 'buyers' | 'sellers'
    const [selectedDate, setSelectedDate] = useState(''); // YYYY-MM-DD format
    const [bandarData, setBandarData] = useState(null);
    const [internalLoading, setInternalLoading] = useState(false);
    const [showUpload, setShowUpload] = useState(false);

    // Combine loading states
    const isBusy = isLoading || internalLoading;

    // Use fetched data if available, otherwise prop data
    // NO DUMMY DATA FALLBACK
    const displayData = bandarData || data;

    // Fetch data when date changes
    const fetchBandarData = async (dateStr) => {
        if (!ticker) return;
        setInternalLoading(true);
        try {
            const url = dateStr
                ? `${API_BASE_URL}/api/v1/bandarmology/${ticker}?date=${dateStr}`
                : `${API_BASE_URL}/api/v1/bandarmology/${ticker}`;
            const response = await fetch(url);
            if (response.ok) {
                const result = await response.json();
                setBandarData(result);
                setShowUpload(false); // Hide upload on successful fetch
            }
        } catch (error) {
            console.error('Error fetching bandar data:', error);
        } finally {
            setInternalLoading(false);
        }
    };

    // Handle date change
    const handleDateChange = (e) => {
        const newDate = e.target.value;
        setSelectedDate(newDate);
        if (newDate) {
            fetchBandarData(newDate);
        } else {
            setBandarData(null); // Reset to use prop data
        }
    };

    // Refresh current data
    const handleRefresh = () => {
        fetchBandarData(selectedDate || undefined);
    };

    // Reset bandarData when ticker changes
    useEffect(() => {
        setBandarData(null);
        setSelectedDate('');
        setShowUpload(false);
    }, [ticker]);

    // Handle Loading State
    if (isBusy) {
        return <BrokerSummarySkeleton />;
    }

    // Handle Empty/Error State - Show upload fallback
    if (showUpload || !displayData || displayData.status === 'DATA_UNAVAILABLE' || displayData.source === 'error') {
        return (
            <div className="glass-card p-4">
                <div className="flex flex-col items-center justify-center text-center mb-4">
                    <Building2 size={32} className="text-gray-600 mb-3" />
                    <h3 className="text-sm font-semibold text-gray-400">Broker Data Unavailable</h3>
                    <p className="text-xs text-gray-500 mt-1 max-w-[200px]">
                        API limit reached or data unavailable. Upload broker summary file to continue.
                    </p>
                </div>
                <FileUploadPanel
                    ticker={ticker}
                    mode="broker_summary"
                    onUploadComplete={(result) => {
                        if (result.parsed_data) {
                            // Transform parsed data to display format
                            const parsed = result.parsed_data;

                            // Map broker entries to expected BrokerRow format
                            const mapBrokerEntry = (b, side) => ({
                                code: b.broker_code,
                                name: b.broker_code, // Use code as name for now
                                type: b.broker_type || 'UNKNOWN',
                                value: side === 'BUY' ? b.buy_value : b.sell_value,
                                volume: side === 'BUY' ? b.buy_volume : b.sell_volume,
                                is_foreign: b.is_foreign || false,
                                broker_type: b.broker_type || 'UNKNOWN'
                            });

                            const transformedBuyers = (parsed.top_buyers || []).map(b => mapBrokerEntry(b, 'BUY'));
                            const transformedSellers = (parsed.top_sellers || []).map(b => mapBrokerEntry(b, 'SELL'));

                            // Calculate totals from individual entries
                            const totalBuy = transformedBuyers.reduce((sum, b) => sum + (b.value || 0), 0);
                            const totalSell = transformedSellers.reduce((sum, b) => sum + (b.value || 0), 0);

                            // Calculate flows by broker type
                            const calcNetFlow = (type) => {
                                const buyVal = transformedBuyers
                                    .filter(b => b.broker_type === type)
                                    .reduce((sum, b) => sum + (b.value || 0), 0);
                                const sellVal = transformedSellers
                                    .filter(b => b.broker_type === type)
                                    .reduce((sum, b) => sum + (b.value || 0), 0);
                                return buyVal - sellVal;
                            };

                            // Backend sends lowercase snake_case values (e.g. 'retail_platform')
                            const retailFlow = calcNetFlow('retail_platform');
                            const localInstFlow = calcNetFlow('institutional_local');
                            const foreignInstFlow = parsed.net_foreign_flow || 0;

                            // Institutional = Local + Foreign
                            const institutionalFlow = localInstFlow + foreignInstFlow;

                            setBandarData({
                                status: parsed.phase || 'NEUTRAL',
                                top_buyers: transformedBuyers,
                                top_sellers: transformedSellers,
                                buy_value: parsed.total_buy || totalBuy,
                                sell_value: parsed.total_sell || totalSell,
                                net_flow: (parsed.total_buy && parsed.total_sell) ? (parsed.total_buy - parsed.total_sell) : (totalBuy - totalSell),
                                concentration_ratio: parsed.bcr ? parsed.bcr * 30 : 50,
                                foreign_net_flow: foreignInstFlow,
                                institutional_net_flow: institutionalFlow,
                                retail_net_flow: retailFlow,
                                source: 'upload',
                                bcr: parsed.bcr || 1.0
                            });
                            setShowUpload(false);
                        }
                    }}
                    showAsInline
                    apiLimitReached
                />
            </div>
        );
    }

    // Status configuration
    const getStatusConfig = (status) => {
        const configs = {
            'BIG_ACCUMULATION': { color: 'text-green-300', bgColor: 'bg-green-600/30', label: '🟢 Big Accumulation', signal: 2 },
            'ACCUMULATION': { color: 'text-green-400', bgColor: 'bg-green-500/20', label: 'Accumulation', signal: 1 },
            'NEUTRAL': { color: 'text-gray-400', bgColor: 'bg-gray-500/20', label: 'Neutral', signal: 0 },
            'DISTRIBUTION': { color: 'text-orange-400', bgColor: 'bg-orange-500/20', label: 'Distribution', signal: -1 },
            'BIG_DISTRIBUTION': { color: 'text-red-300', bgColor: 'bg-red-600/30', label: '🔴 Big Distribution', signal: -2 },
            'CHURNING': { color: 'text-purple-400', bgColor: 'bg-purple-500/20', label: '⚠️ Churning', signal: 0 },
        };
        return configs[status] || configs['NEUTRAL'];
    };

    const statusConfig = getStatusConfig(displayData.status);

    // Format helpers
    const formatValue = (val) => {
        if (!val) return '0';
        if (val >= 1e12) return (val / 1e12).toFixed(1) + 'T';
        if (val >= 1e9) return (val / 1e9).toFixed(1) + 'B';
        if (val >= 1e6) return (val / 1e6).toFixed(1) + 'M';
        return val.toLocaleString('id-ID');
    };

    const formatVolume = (vol) => {
        if (!vol) return '0';
        if (vol >= 1e6) return (vol / 1e6).toFixed(2) + 'M';
        if (vol >= 1e3) return (vol / 1e3).toFixed(0) + 'K';
        return vol.toString();
    };

    // Get max value for bar scaling
    const allBrokers = [...(displayData.top_buyers || []), ...(displayData.top_sellers || [])];
    const maxValue = Math.max(...allBrokers.map(b => b.value || 0), 1);

    // Type badge component
    const TypeBadge = ({ type, isForeign }) => {
        const typeColors = {
            'INSTITUTION': 'bg-green-500/30 text-green-400 border-green-500/50',
            'RETAIL': 'bg-blue-500/30 text-blue-400 border-blue-500/50',
            'MIXED': 'bg-gray-500/30 text-gray-400 border-gray-500/50',
            'UNKNOWN': 'bg-gray-500/20 text-gray-500 border-gray-500/30'
        };
        return (
            <div className="flex items-center gap-1">
                <span className={`text-[9px] px-1.5 py-0.5 rounded border ${typeColors[type] || typeColors['UNKNOWN']}`}>
                    {type === 'INSTITUTION' ? '🏦' : type === 'RETAIL' ? '👤' : '⚪'}
                </span>
                {isForeign && <span className="text-[9px] px-1 bg-yellow-500/20 text-yellow-400 rounded">🌐</span>}
            </div>
        );
    };

    // Broker Row Component (Stockbit-style)
    const BrokerRow = ({ broker, side, rank }) => {
        const brokerCode = typeof broker === 'string' ? broker : broker.code;
        const brokerName = typeof broker === 'string' ? broker : broker.name;
        const brokerType = typeof broker === 'object' ? broker.type : 'UNKNOWN';
        const brokerValue = typeof broker === 'object' ? broker.value : 0;
        const brokerVolume = typeof broker === 'object' ? broker.volume : 0;
        const isForeign = typeof broker === 'object' ? broker.is_foreign : false;

        const barWidth = (brokerValue / maxValue) * 100;
        const barColor = side === 'BUY' ? 'bg-green-500' : 'bg-red-500';

        return (
            <div
                className="relative flex items-center py-2 px-2 hover:bg-white/5 cursor-pointer transition-colors rounded"
                onClick={() => setSelectedBroker({ code: brokerCode, name: brokerName })}
            >
                {/* Rank */}
                <div className="w-6 text-xs text-gray-500 font-mono">{rank}</div>

                {/* Broker Code & Name */}
                <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                        <span className={`font-bold text-sm ${side === 'BUY' ? 'text-green-400' : 'text-red-400'}`}>
                            {brokerCode}
                        </span>
                        <span className="text-xs text-gray-500 truncate">{brokerName}</span>
                        <TypeBadge type={brokerType} isForeign={isForeign} />
                    </div>
                    {/* Volume Bar */}
                    <div className="mt-1 h-1.5 bg-gray-700/50 rounded-full overflow-hidden">
                        <div
                            className={`h-full ${barColor} rounded-full transition-all duration-500`}
                            style={{ width: `${barWidth}%` }}
                        />
                    </div>
                </div>

                {/* Value */}
                <div className="text-right ml-3">
                    <div className={`text-sm font-mono ${side === 'BUY' ? 'text-green-400' : 'text-red-400'}`}>
                        {formatValue(brokerValue)}
                    </div>
                    <div className="text-[10px] text-gray-500">{formatVolume(brokerVolume)} lot</div>
                </div>
            </div>
        );
    };

    return (
        <>
            <div className="glass-card">
                {/* Header */}
                <div className="p-3 border-b border-white/10">
                    <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                            <Building2 size={16} className="text-brand-accent" />
                            <h3 className="font-semibold text-sm">Broker Summary</h3>
                            {ticker && <span className="text-xs bg-white/10 px-2 py-0.5 rounded">{ticker}</span>}
                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-green-500/20 text-green-400">Real Data</span>
                            {internalLoading && <RefreshCw size={12} className="text-brand-accent animate-spin" />}
                        </div>
                        <span className={`text-xs px-2 py-1 rounded ${statusConfig.bgColor} ${statusConfig.color}`}>
                            {statusConfig.label}
                        </span>
                    </div>

                    {/* Date Picker Row */}
                    <div className="flex items-center gap-2">
                        <div className="flex items-center gap-1 text-xs text-gray-400">
                            <Calendar size={12} />
                            <span>Tanggal:</span>
                        </div>
                        <input
                            type="date"
                            value={selectedDate}
                            onChange={handleDateChange}
                            className="bg-white/5 border border-white/10 rounded px-2 py-1 text-xs text-white 
                                     focus:outline-none focus:border-brand-accent/50"
                            style={{ colorScheme: 'dark' }}
                        />
                        <button
                            onClick={handleRefresh}
                            disabled={internalLoading}
                            className="p-1.5 rounded bg-white/5 hover:bg-white/10 transition-colors disabled:opacity-50"
                            title="Refresh data"
                        >
                            <RefreshCw size={12} className={internalLoading ? 'animate-spin' : ''} />
                        </button>

                        {/* Re-upload Button */}
                        <button
                            onClick={() => {
                                setBandarData(null);
                                setShowUpload(true);
                            }}
                            className="p-1.5 rounded bg-white/5 hover:bg-white/10 transition-colors text-gray-400 hover:text-white"
                            title="Upload new file"
                        >
                            <Upload size={12} />
                        </button>

                        {selectedDate && (
                            <button
                                onClick={() => { setSelectedDate(''); setBandarData(null); }}
                                className="text-xs text-gray-400 hover:text-white"
                            >
                                Hari Ini
                            </button>
                        )}
                    </div>
                </div>

                {/* Tabs */}
                <div className="flex border-b border-white/10">
                    {[
                        { id: 'summary', label: 'Summary' },
                        { id: 'buyers', label: 'Top Buyers' },
                        { id: 'sellers', label: 'Top Sellers' }
                    ].map(tab => (
                        <button
                            key={tab.id}
                            onClick={() => setActiveTab(tab.id)}
                            className={`flex-1 py-2 text-xs font-medium transition-colors ${activeTab === tab.id
                                ? 'text-brand-accent border-b-2 border-brand-accent'
                                : 'text-gray-500 hover:text-gray-300'
                                }`}
                        >
                            {tab.label}
                        </button>
                    ))}
                </div>

                {/* Content */}
                <div className="p-3">
                    {activeTab === 'summary' && (
                        <div className="space-y-4">
                            {/* Net Flow Summary */}
                            <div className="grid grid-cols-2 gap-3">
                                <div className="bg-green-500/10 rounded-lg p-3 border border-green-500/20">
                                    <div className="flex items-center gap-2 text-xs text-gray-400 mb-1">
                                        <ArrowUpRight size={12} className="text-green-400" />
                                        Total Buy
                                    </div>
                                    <div className="text-lg font-bold text-green-400">{formatValue(displayData.buy_value)}</div>
                                </div>
                                <div className="bg-red-500/10 rounded-lg p-3 border border-red-500/20">
                                    <div className="flex items-center gap-2 text-xs text-gray-400 mb-1">
                                        <ArrowDownRight size={12} className="text-red-400" />
                                        Total Sell
                                    </div>
                                    <div className="text-lg font-bold text-red-400">{formatValue(displayData.sell_value)}</div>
                                </div>
                            </div>

                            {/* Net Flow */}
                            <div className={`rounded-lg p-3 ${displayData.net_flow >= 0 ? 'bg-green-500/10 border-green-500/20' : 'bg-red-500/10 border-red-500/20'} border`}>
                                <div className="flex justify-between items-center">
                                    <span className="text-xs text-gray-400">Net Flow</span>
                                    <span className={`text-lg font-bold ${displayData.net_flow >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                        {displayData.net_flow >= 0 ? '+' : ''}{formatValue(displayData.net_flow)}
                                    </span>
                                </div>
                            </div>

                            {/* Flow Breakdown */}
                            <div className="space-y-2">
                                <div className="text-xs text-gray-400 mb-2">Flow by Type</div>

                                {/* Institutional */}
                                <div className="flex items-center justify-between py-1.5 border-b border-white/5">
                                    <span className="text-xs flex items-center gap-2">
                                        <span className="text-green-400">🏦</span> Institutional
                                    </span>
                                    <span className={`text-sm font-mono ${(displayData.institutional_net_flow || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                        {(displayData.institutional_net_flow || 0) >= 0 ? '+' : ''}{formatValue(displayData.institutional_net_flow || 0)}
                                    </span>
                                </div>

                                {/* Retail */}
                                <div className="flex items-center justify-between py-1.5 border-b border-white/5">
                                    <span className="text-xs flex items-center gap-2">
                                        <span className="text-blue-400">👤</span> Retail
                                    </span>
                                    <span className={`text-sm font-mono ${(displayData.retail_net_flow || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                        {(displayData.retail_net_flow || 0) >= 0 ? '+' : ''}{formatValue(displayData.retail_net_flow || 0)}
                                    </span>
                                </div>

                                {/* Foreign */}
                                <div className="flex items-center justify-between py-1.5">
                                    <span className="text-xs flex items-center gap-2">
                                        <span className="text-yellow-400">🌐</span> Foreign
                                    </span>
                                    <span className={`text-sm font-mono ${(displayData.foreign_net_flow || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                        {(displayData.foreign_net_flow || 0) >= 0 ? '+' : ''}{formatValue(displayData.foreign_net_flow || 0)}
                                    </span>
                                </div>
                            </div>

                            {/* Concentration */}
                            <div>
                                <div className="flex justify-between items-center mb-2">
                                    <span className="text-xs text-gray-400">Top 5 Concentration</span>
                                    <span className="text-sm font-semibold">{displayData.concentration_ratio?.toFixed(1) || 0}%</span>
                                </div>
                                <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
                                    <div
                                        className={`h-full transition-all duration-500 ${displayData.concentration_ratio > 50 ? 'bg-brand-accent' :
                                            displayData.concentration_ratio > 30 ? 'bg-yellow-500' : 'bg-gray-500'
                                            }`}
                                        style={{ width: `${displayData.concentration_ratio || 0}%` }}
                                    />
                                </div>
                                <div className="text-[10px] text-gray-500 mt-1">
                                    {displayData.concentration_ratio > 50 ? 'High concentration - Institutional activity' :
                                        displayData.concentration_ratio > 30 ? 'Moderate concentration' : 'Low concentration - Mixed activity'}
                                </div>
                            </div>
                        </div>
                    )}

                    {activeTab === 'buyers' && (
                        <div className="space-y-1">
                            <div className="text-xs text-gray-500 flex items-center justify-between px-2 py-1 border-b border-white/5">
                                <span>#</span>
                                <span className="flex-1 ml-4">Broker</span>
                                <span>Value</span>
                            </div>
                            {displayData.top_buyers?.map((broker, idx) => (
                                <BrokerRow key={idx} broker={broker} side="BUY" rank={idx + 1} />
                            ))}
                        </div>
                    )}

                    {activeTab === 'sellers' && (
                        <div className="space-y-1">
                            <div className="text-xs text-gray-500 flex items-center justify-between px-2 py-1 border-b border-white/5">
                                <span>#</span>
                                <span className="flex-1 ml-4">Broker</span>
                                <span>Value</span>
                            </div>
                            {displayData.top_sellers?.map((broker, idx) => (
                                <BrokerRow key={idx} broker={broker} side="SELL" rank={idx + 1} />
                            ))}
                        </div>
                    )}
                </div>
            </div>

            {/* Modal */}
            <BrokerDetailModal
                brokerCode={selectedBroker?.code}
                brokerName={selectedBroker?.name}
                ticker={ticker}
                onClose={() => setSelectedBroker(null)}
            />
        </>
    );
}

export { BrokerSummaryPanel };
export default BrokerSummaryPanel;
