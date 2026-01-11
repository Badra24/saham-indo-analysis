import React from 'react';
import { TrendingUp, TrendingDown, Activity, AlertTriangle, Eye } from 'lucide-react';

/**
 * Order Flow Panel - Displays OBI, HAKA/HAKI, and Smart Money signals
 */
export const OrderFlowPanel = ({ orderFlow }) => {
    if (!orderFlow) {
        return (
            <div className="glass-card p-4">
                <h3 className="text-sm font-semibold text-gray-400 mb-3 flex items-center gap-2">
                    <Activity size={16} /> Order Flow Analysis
                </h3>
                <p className="text-gray-500 text-sm">Run analysis to see order flow data</p>
            </div>
        );
    }

    const { obi, signal, signal_strength, haka_volume, haki_volume, net_flow, iceberg_detected, recommendation } = orderFlow;

    // Determine signal color
    const getSignalColor = (sig) => {
        if (sig?.includes('ACCUMULATION')) return 'text-green-400';
        if (sig?.includes('DISTRIBUTION')) return 'text-red-400';
        if (sig?.includes('SPOOFING')) return 'text-yellow-400';
        return 'text-gray-400';
    };

    // OBI Bar visualization
    const obiPercent = Math.abs(obi || 0) * 100;
    const obiIsPositive = (obi || 0) >= 0;

    return (
        <div className="glass-card p-4 space-y-4">
            <h3 className="text-sm font-semibold text-gray-400 flex items-center gap-2">
                <Activity size={16} /> Order Flow Analysis
            </h3>

            {/* OBI Meter */}
            <div className="space-y-1">
                <div className="flex justify-between text-xs">
                    <span className="text-gray-500">OBI (Order Book Imbalance)</span>
                    <span className={obiIsPositive ? 'text-green-400' : 'text-red-400'}>
                        {(obi || 0).toFixed(4)}
                    </span>
                </div>
                <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
                    <div
                        className={`h-full transition-all duration-300 ${obiIsPositive ? 'bg-green-500' : 'bg-red-500'}`}
                        style={{ width: `${Math.min(obiPercent, 100)}%` }}
                    />
                </div>
            </div>

            {/* Signal Badge */}
            <div className="flex items-center justify-between">
                <span className="text-xs text-gray-500">Signal</span>
                <span className={`text-sm font-bold ${getSignalColor(signal)}`}>
                    {signal || 'NEUTRAL'}
                </span>
            </div>

            {/* HAKA/HAKI Volume */}
            <div className="grid grid-cols-2 gap-3">
                <div className="bg-green-900/20 rounded p-2">
                    <div className="flex items-center gap-1 text-green-400 text-xs">
                        <TrendingUp size={12} /> HAKA
                    </div>
                    <div className="text-lg font-bold text-green-400">
                        {((haka_volume || 0) / 1000).toFixed(1)}K
                    </div>
                </div>
                <div className="bg-red-900/20 rounded p-2">
                    <div className="flex items-center gap-1 text-red-400 text-xs">
                        <TrendingDown size={12} /> HAKI
                    </div>
                    <div className="text-lg font-bold text-red-400">
                        {((haki_volume || 0) / 1000).toFixed(1)}K
                    </div>
                </div>
            </div>

            {/* Net Flow */}
            <div className="flex justify-between items-center text-sm">
                <span className="text-gray-500">Net Flow</span>
                <span className={net_flow >= 0 ? 'text-green-400' : 'text-red-400'}>
                    {net_flow >= 0 ? '+' : ''}{((net_flow || 0) / 1000).toFixed(1)}K
                </span>
            </div>

            {/* Iceberg Alert */}
            {iceberg_detected && (
                <div className="bg-blue-900/30 border border-blue-500/50 rounded p-2 flex items-center gap-2">
                    <Eye size={14} className="text-blue-400" />
                    <span className="text-xs text-blue-300">Iceberg Order Detected!</span>
                </div>
            )}

            {/* Recommendation */}
            {recommendation && (
                <div className="text-xs text-gray-400 italic border-t border-gray-700 pt-2">
                    {recommendation}
                </div>
            )}

            {/* Signal Strength Bar */}
            <div className="space-y-1">
                <div className="flex justify-between text-xs">
                    <span className="text-gray-500">Signal Strength</span>
                    <span className="text-gray-400">{((signal_strength || 0) * 100).toFixed(0)}%</span>
                </div>
                <div className="h-1 bg-gray-700 rounded-full overflow-hidden">
                    <div
                        className="h-full bg-brand-accent transition-all duration-300"
                        style={{ width: `${(signal_strength || 0) * 100}%` }}
                    />
                </div>
            </div>
        </div>
    );
};

export default OrderFlowPanel;
