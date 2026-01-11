import { BarChart3, TrendingUp, Activity, Waves } from 'lucide-react';

/**
 * IndicatorPanel - Toggle panel for chart indicators
 * Grouped by category with toggle switches
 */
function IndicatorPanel({ indicators, onToggle }) {
    const indicatorGroups = [
        {
            title: 'Moving Averages',
            icon: <TrendingUp size={14} className="text-yellow-400" />,
            items: [
                { key: 'ema9', label: 'EMA 9', color: '#fbbf24' },
                { key: 'ema21', label: 'EMA 21', color: '#f59e0b' },
                { key: 'ema55', label: 'EMA 55', color: '#8b5cf6' },
                { key: 'ema200', label: 'EMA 200', color: '#ec4899' },
                { key: 'sma50', label: 'SMA 50', color: '#84cc16' },
                { key: 'sma100', label: 'SMA 100', color: '#22c55e' },
                { key: 'sma200', label: 'SMA 200', color: '#f97316' },
            ]
        },
        {
            title: 'Oscillators',
            icon: <Waves size={14} className="text-purple-400" />,
            items: [
                { key: 'rsi', label: 'RSI (14)', color: '#a855f7' },
                { key: 'macdV', label: 'MACD-V', color: '#3b82f6' },
                { key: 'stochastic', label: 'Stochastic', color: '#f472b6', description: '%K & %D' },
                { key: 'cci', label: 'CCI (20)', color: '#fb923c', description: 'Commodity Channel' },
            ]
        },
        {
            title: 'Volume',
            icon: <BarChart3 size={14} className="text-cyan-400" />,
            items: [
                { key: 'vwap', label: 'VWAP', color: '#06b6d4' },
                { key: 'obv', label: 'OBV', color: '#0ea5e9', description: 'On-Balance Volume' },
                { key: 'volumeProfile', label: 'Volume Anomaly', color: '#14b8a6', description: 'Detects unusual volume spikes' },
            ]
        },
        {
            title: 'Ichimoku Cloud',
            icon: <Activity size={14} className="text-red-400" />,
            items: [
                { key: 'ichimokuCloud', label: 'Kumo Cloud', color: '#ef4444' },
                { key: 'ichimokuTenkan', label: 'Tenkan-sen', color: '#3b82f6' },
                { key: 'ichimokuKijun', label: 'Kijun-sen', color: '#dc2626' },
            ]
        },
        {
            title: 'Support/Resistance',
            icon: <TrendingUp size={14} className="text-emerald-400" />,
            items: [
                { key: 'pivotPoints', label: 'Pivot Points', color: '#10b981' },
                { key: 'bollingerBands', label: 'Bollinger', color: '#6366f1' },
            ]
        },
        {
            title: 'Smart Money',
            icon: <Activity size={14} className="text-green-400" />,
            items: [
                { key: 'orderFlow', label: 'Order Flow (Panel)', color: '#10b981', description: 'Shows in dedicated panel' },
                { key: 'brokerFlow', label: 'Broker Summary', color: '#22c55e', description: 'See Broker Summary panel below' },
            ]
        }
    ];

    return (
        <div className="glass-card">
            <div className="p-3 border-b border-white/10 flex items-center gap-2">
                <BarChart3 size={16} className="text-brand-accent" />
                <h3 className="font-semibold text-sm">Indicators</h3>
            </div>
            <div className="p-3 space-y-4 max-h-[320px] overflow-y-auto">
                {indicatorGroups.map((group) => (
                    <div key={group.title}>
                        <div className="flex items-center gap-2 mb-2 text-xs text-gray-400 uppercase tracking-wider">
                            {group.icon}
                            <span>{group.title}</span>
                        </div>
                        <div className="space-y-1">
                            {group.items.map((item) => (
                                <div
                                    key={item.key}
                                    className="flex items-center justify-between p-2 rounded hover:bg-white/5 cursor-pointer transition-colors"
                                    onClick={() => onToggle(item.key)}
                                >
                                    <div className="flex items-center gap-2">
                                        <div
                                            className="w-3 h-3 rounded-full"
                                            style={{ backgroundColor: item.color }}
                                        />
                                        <span className="text-sm">{item.label}</span>
                                    </div>
                                    <div
                                        className={`w-8 h-4 rounded-full transition-colors relative ${indicators[item.key]
                                            ? 'bg-brand-accent'
                                            : 'bg-gray-600'
                                            }`}
                                    >
                                        <div
                                            className={`absolute top-0.5 w-3 h-3 rounded-full bg-white transition-transform ${indicators[item.key]
                                                ? 'translate-x-4'
                                                : 'translate-x-0.5'
                                                }`}
                                        />
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}

export { IndicatorPanel };
export default IndicatorPanel;
