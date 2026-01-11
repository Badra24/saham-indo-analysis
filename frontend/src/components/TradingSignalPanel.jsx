import React from 'react';
import { Target, Shield, AlertCircle, ArrowUpCircle, ArrowDownCircle, MinusCircle } from 'lucide-react';

/**
 * Trading Signal Panel - Displays Looping Strategy signals
 */
export const TradingSignalPanel = ({ signal }) => {
    if (!signal) {
        return (
            <div className="glass-card p-4">
                <h3 className="text-sm font-semibold text-gray-400 mb-3 flex items-center gap-2">
                    <Target size={16} /> Trading Signal
                </h3>
                <p className="text-gray-500 text-sm">Run analysis to see trading signals</p>
            </div>
        );
    }

    const { action, confidence, entry_price, stop_loss, take_profit, position_size, phase, reasoning } = signal;

    // Get action styling
    const getActionStyle = (act) => {
        switch (act) {
            case 'BUY':
            case 'RE_ENTRY':
                return { color: 'text-green-400', bg: 'bg-green-900/30', border: 'border-green-500/50', Icon: ArrowUpCircle };
            case 'SELL':
            case 'FULL_EXIT':
            case 'PARTIAL_EXIT':
                return { color: 'text-red-400', bg: 'bg-red-900/30', border: 'border-red-500/50', Icon: ArrowDownCircle };
            default:
                return { color: 'text-gray-400', bg: 'bg-gray-800/50', border: 'border-gray-600/50', Icon: MinusCircle };
        }
    };

    const actionStyle = getActionStyle(action);
    const ActionIcon = actionStyle.Icon;

    // Format price
    const formatPrice = (price) => {
        if (!price) return '-';
        return new Intl.NumberFormat('id-ID', { style: 'currency', currency: 'IDR' }).format(price);
    };

    return (
        <div className="glass-card p-4 space-y-4">
            <h3 className="text-sm font-semibold text-gray-400 flex items-center gap-2">
                <Target size={16} /> Trading Signal (Looping Strategy)
            </h3>

            {/* Main Action Badge */}
            <div className={`${actionStyle.bg} ${actionStyle.border} border rounded-lg p-3 flex items-center justify-between`}>
                <div className="flex items-center gap-2">
                    <ActionIcon size={24} className={actionStyle.color} />
                    <div>
                        <div className={`text-xl font-bold ${actionStyle.color}`}>{action}</div>
                        <div className="text-xs text-gray-500">Phase: {phase}</div>
                    </div>
                </div>
                <div className="text-right">
                    <div className="text-xs text-gray-500">Confidence</div>
                    <div className={`text-lg font-bold ${actionStyle.color}`}>
                        {((confidence || 0) * 100).toFixed(0)}%
                    </div>
                </div>
            </div>

            {/* Position Sizing (30-30-40 Rule) */}
            {position_size > 0 && (
                <div className="space-y-1">
                    <div className="flex justify-between text-xs">
                        <span className="text-gray-500">Position Size</span>
                        <span className="text-brand-accent">{(position_size * 100).toFixed(0)}%</span>
                    </div>
                    <div className="h-2 bg-gray-700 rounded-full overflow-hidden flex">
                        <div className="h-full bg-blue-500" style={{ width: '30%' }} title="Scout 30%" />
                        <div className="h-full bg-green-500" style={{ width: '30%' }} title="Confirm 30%" />
                        <div className="h-full bg-yellow-500" style={{ width: '40%' }} title="Attack 40%" />
                    </div>
                    <div className="flex justify-between text-[10px] text-gray-600">
                        <span>Scout 30%</span>
                        <span>Confirm 30%</span>
                        <span>Attack 40%</span>
                    </div>
                </div>
            )}

            {/* Price Levels */}
            {(entry_price || stop_loss || take_profit) && (
                <div className="grid grid-cols-3 gap-2 text-center">
                    {entry_price && (
                        <div className="bg-gray-800/50 rounded p-2">
                            <div className="text-xs text-gray-500">Entry</div>
                            <div className="text-sm font-bold text-white">{formatPrice(entry_price)}</div>
                        </div>
                    )}
                    {stop_loss && (
                        <div className="bg-red-900/20 rounded p-2">
                            <div className="text-xs text-red-400">Stop Loss</div>
                            <div className="text-sm font-bold text-red-400">{formatPrice(stop_loss)}</div>
                        </div>
                    )}
                    {take_profit && (
                        <div className="bg-green-900/20 rounded p-2">
                            <div className="text-xs text-green-400">Take Profit</div>
                            <div className="text-sm font-bold text-green-400">{formatPrice(take_profit)}</div>
                        </div>
                    )}
                </div>
            )}

            {/* Reasoning */}
            {reasoning && (
                <div className="text-xs text-gray-400 italic border-t border-gray-700 pt-2">
                    {reasoning}
                </div>
            )}

            {/* Iceberg Support Badge */}
            {signal.iceberg_support && (
                <div className="bg-blue-900/30 border border-blue-500/50 rounded p-2 flex items-center gap-2">
                    <Shield size={14} className="text-blue-400" />
                    <span className="text-xs text-blue-300">Institutional Support Detected</span>
                </div>
            )}
        </div>
    );
};

export default TradingSignalPanel;
