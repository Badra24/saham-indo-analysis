import { useState, useEffect } from 'react';
import { X, Building2, TrendingUp, TrendingDown, Activity, RefreshCw, Calendar, ArrowUpRight, ArrowDownRight } from 'lucide-react';
import { API_BASE_URL } from '../config';

/**
 * BrokerDetailModal - Shows broker activity history from GoAPI
 * Features: 30-day activity, running position, trend analysis
 */
export default function BrokerDetailModal({ brokerCode, brokerName, ticker, onClose }) {
    const [loading, setLoading] = useState(false);
    const [data, setData] = useState(null);
    const [error, setError] = useState(null);

    // Fetch broker history when modal opens
    useEffect(() => {
        if (!brokerCode || !ticker) return;

        const fetchHistory = async () => {
            setLoading(true);
            setError(null);
            try {
                const response = await fetch(`${API_BASE_URL}/api/v1/broker/${brokerCode}/history/${ticker}?days=30`);
                if (response.ok) {
                    const result = await response.json();
                    setData(result);
                } else {
                    setError('Failed to fetch broker history');
                }
            } catch (e) {
                setError(e.message);
            } finally {
                setLoading(false);
            }
        };

        fetchHistory();
    }, [brokerCode, ticker]);

    if (!brokerCode) return null;

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

    // Get trend config
    const getTrendConfig = (trend) => {
        const configs = {
            'AKUMULASI_AKTIF': { color: 'text-green-400', bg: 'bg-green-500/20', icon: '📈', label: 'Akumulasi Aktif' },
            'DISTRIBUSI_AKTIF': { color: 'text-red-400', bg: 'bg-red-500/20', icon: '📉', label: 'Distribusi Aktif' },
            'MULAI_AKUMULASI': { color: 'text-green-300', bg: 'bg-green-500/10', icon: '🔼', label: 'Mulai Akumulasi' },
            'MULAI_DISTRIBUSI': { color: 'text-orange-400', bg: 'bg-orange-500/20', icon: '🔽', label: 'Mulai Distribusi' },
            'NETRAL': { color: 'text-gray-400', bg: 'bg-gray-500/20', icon: '⚪', label: 'Netral' },
            'DATA_TERBATAS': { color: 'text-gray-500', bg: 'bg-gray-500/10', icon: '❓', label: 'Data Terbatas' }
        };
        return configs[trend] || configs['DATA_TERBATAS'];
    };

    // Type badge component
    const TypeBadge = ({ type, isForeign }) => {
        const typeColors = {
            'INSTITUTION': 'bg-green-500/30 text-green-400',
            'RETAIL': 'bg-blue-500/30 text-blue-400',
            'MIXED': 'bg-gray-500/30 text-gray-400',
            'UNKNOWN': 'bg-gray-500/20 text-gray-500'
        };
        return (
            <div className="flex items-center gap-1">
                <span className={`text-xs px-2 py-0.5 rounded ${typeColors[type] || typeColors['UNKNOWN']}`}>
                    {type || 'Unknown'}
                </span>
                {isForeign && <span className="text-xs px-1.5 py-0.5 bg-yellow-500/20 text-yellow-400 rounded">🌐 Foreign</span>}
            </div>
        );
    };

    // Mini bar component for activity chart
    const ActivityBar = ({ buyValue, sellValue, maxValue }) => {
        const buyWidth = (buyValue / maxValue) * 100;
        const sellWidth = (sellValue / maxValue) * 100;

        return (
            <div className="flex flex-col gap-0.5">
                <div className="h-2 bg-gray-700/50 rounded-sm overflow-hidden">
                    <div className="h-full bg-green-500 rounded-sm" style={{ width: `${buyWidth}%` }} />
                </div>
                <div className="h-2 bg-gray-700/50 rounded-sm overflow-hidden">
                    <div className="h-full bg-red-500 rounded-sm" style={{ width: `${sellWidth}%` }} />
                </div>
            </div>
        );
    };

    const trendConfig = data ? getTrendConfig(data.trend) : getTrendConfig('DATA_TERBATAS');
    const maxDailyValue = data?.daily_activity?.length > 0
        ? Math.max(...data.daily_activity.map(d => Math.max(d.buy_value, d.sell_value)))
        : 1;

    return (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
            <div className="bg-[#1E1E24] border border-gray-700 rounded-xl shadow-2xl w-full max-w-2xl overflow-hidden animate-in fade-in zoom-in duration-200 max-h-[90vh] overflow-y-auto">

                {/* Header */}
                <div className="p-4 border-b border-gray-700 flex justify-between items-center bg-gray-800/50 sticky top-0">
                    <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-full bg-brand-accent/20 flex items-center justify-center text-brand-accent font-bold text-lg">
                            {brokerCode}
                        </div>
                        <div>
                            <h2 className="text-xl font-bold text-white">{data?.broker_name || brokerName}</h2>
                            <TypeBadge type={data?.broker_type} isForeign={data?.is_foreign} />
                        </div>
                    </div>
                    <button
                        onClick={onClose}
                        className="p-2 hover:bg-gray-700 rounded-full text-gray-400 hover:text-white transition-colors"
                    >
                        <X size={20} />
                    </button>
                </div>

                {/* Loading State */}
                {loading && (
                    <div className="p-8 flex items-center justify-center">
                        <RefreshCw size={24} className="animate-spin text-brand-accent" />
                        <span className="ml-2 text-gray-400">Memuat data 30 hari...</span>
                    </div>
                )}

                {/* Error State */}
                {error && !loading && (
                    <div className="p-8 text-center text-red-400">
                        <p>Error: {error}</p>
                    </div>
                )}

                {/* Data Loaded */}
                {data && !loading && (
                    <>
                        {/* Stats Grid */}
                        <div className="grid grid-cols-3 gap-4 p-4 bg-gray-800/20">
                            <div className="text-center">
                                <div className="text-gray-400 text-xs mb-1">Total Buy (30d)</div>
                                <div className="text-lg font-bold text-green-400">{formatValue(data.running_buy)}</div>
                            </div>
                            <div className="text-center">
                                <div className="text-gray-400 text-xs mb-1">Total Sell (30d)</div>
                                <div className="text-lg font-bold text-red-400">{formatValue(data.running_sell)}</div>
                            </div>
                            <div className="text-center">
                                <div className="text-gray-400 text-xs mb-1">Net Position</div>
                                <div className={`text-lg font-bold ${data.running_position >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                    {data.running_position >= 0 ? '+' : ''}{formatValue(data.running_position)}
                                </div>
                            </div>
                        </div>

                        {/* Trend Banner */}
                        <div className={`mx-4 mt-4 p-3 rounded-lg ${trendConfig.bg} flex items-center justify-between`}>
                            <div className="flex items-center gap-2">
                                <span className="text-xl">{trendConfig.icon}</span>
                                <div>
                                    <div className={`font-semibold ${trendConfig.color}`}>{trendConfig.label}</div>
                                    <div className="text-xs text-gray-400">
                                        {data.active_days} hari aktif dari {data.days_analyzed} hari
                                    </div>
                                </div>
                            </div>
                            <div className="text-right">
                                <div className="text-xs text-gray-400">Avg Daily Volume</div>
                                <div className="font-mono text-sm">{formatVolume(data.avg_daily_volume)} lot</div>
                            </div>
                        </div>

                        {/* Activity Chart (Mini Bars) */}
                        <div className="p-4">
                            <div className="flex items-center gap-2 mb-3 text-sm font-semibold text-gray-300">
                                <Activity size={16} className="text-brand-accent" />
                                <span>Aktivitas 10 Hari Terakhir untuk {ticker}</span>
                            </div>

                            {data.daily_activity?.length > 0 ? (
                                <div className="grid grid-cols-10 gap-1">
                                    {data.daily_activity.slice(0, 10).map((day, idx) => (
                                        <div key={day.date} className="flex flex-col items-center">
                                            <ActivityBar
                                                buyValue={day.buy_value}
                                                sellValue={day.sell_value}
                                                maxValue={maxDailyValue}
                                            />
                                            <div className="text-[8px] text-gray-500 mt-1">
                                                {new Date(day.date).getDate()}
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            ) : (
                                <div className="text-center text-gray-500 py-4">
                                    Tidak ada aktivitas dalam 30 hari terakhir
                                </div>
                            )}

                            <div className="flex items-center gap-4 mt-2 text-[10px] text-gray-500">
                                <div className="flex items-center gap-1">
                                    <div className="w-2 h-2 bg-green-500 rounded-sm" />
                                    <span>Buy</span>
                                </div>
                                <div className="flex items-center gap-1">
                                    <div className="w-2 h-2 bg-red-500 rounded-sm" />
                                    <span>Sell</span>
                                </div>
                            </div>
                        </div>

                        {/* Recent Activity Table */}
                        <div className="p-4 border-t border-gray-700">
                            <div className="flex items-center gap-2 mb-3 text-sm font-semibold text-gray-300">
                                <Calendar size={16} className="text-brand-accent" />
                                <span>Riwayat Transaksi</span>
                            </div>

                            {data.daily_activity?.length > 0 ? (
                                <div className="overflow-x-auto">
                                    <table className="w-full text-sm">
                                        <thead>
                                            <tr className="text-gray-500 border-b border-gray-700">
                                                <th className="text-left py-2 font-medium">Tanggal</th>
                                                <th className="text-right py-2 font-medium">Buy</th>
                                                <th className="text-right py-2 font-medium">Sell</th>
                                                <th className="text-right py-2 font-medium">Net</th>
                                            </tr>
                                        </thead>
                                        <tbody className="divide-y divide-gray-800">
                                            {data.daily_activity.slice(0, 5).map((day) => (
                                                <tr key={day.date} className="hover:bg-gray-800/50">
                                                    <td className="py-2 text-gray-300">
                                                        {new Date(day.date).toLocaleDateString('id-ID', { weekday: 'short', day: 'numeric', month: 'short' })}
                                                    </td>
                                                    <td className="py-2 text-right font-mono text-green-400">
                                                        {formatValue(day.buy_value)}
                                                    </td>
                                                    <td className="py-2 text-right font-mono text-red-400">
                                                        {formatValue(day.sell_value)}
                                                    </td>
                                                    <td className="py-2 text-right">
                                                        <span className={`px-2 py-0.5 rounded text-xs font-bold ${day.net_value >= 0 ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400'}`}>
                                                            {day.net_value >= 0 ? '+' : ''}{formatValue(day.net_value)}
                                                        </span>
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            ) : (
                                <div className="text-center text-gray-500 py-4">
                                    Belum ada transaksi tercatat
                                </div>
                            )}
                        </div>
                    </>
                )}

                {/* Footer */}
                <div className={`p-3 border-t border-gray-700 text-xs flex items-center justify-center gap-2 ${data?.is_demo ? 'bg-yellow-500/10 text-yellow-500/80' : 'bg-green-500/10 text-green-500/80'}`}>
                    <Activity size={12} />
                    <span>
                        {data?.is_demo
                            ? 'Data simulasi - GoAPI tidak tersedia'
                            : `Data real dari GoAPI (${data?.symbol})`
                        }
                    </span>
                </div>
            </div>
        </div>
    );
}
