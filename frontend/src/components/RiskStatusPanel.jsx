import React from 'react';
import { ShieldAlert, ShieldCheck, AlertTriangle, DollarSign } from 'lucide-react';

/**
 * Risk Status Panel - Displays Kill Switch and Daily P&L status
 */
export const RiskStatusPanel = ({ riskStatus }) => {
    if (!riskStatus) {
        return (
            <div className="glass-card p-4">
                <h3 className="text-sm font-semibold text-gray-400 mb-3 flex items-center gap-2">
                    <ShieldCheck size={16} /> Risk Status
                </h3>
                <p className="text-gray-500 text-sm">Loading risk status...</p>
            </div>
        );
    }

    const {
        daily_pnl,
        daily_pnl_percent,
        kill_switch_active,
        remaining_risk_budget,
        positions_count,
        total_exposure,
        message
    } = riskStatus;

    const isProfit = (daily_pnl_percent || 0) >= 0;
    const riskUsedPercent = ((0.025 - (remaining_risk_budget || 0.025)) / 0.025) * 100;

    return (
        <div className="glass-card p-4 space-y-3">
            <h3 className="text-sm font-semibold text-gray-400 flex items-center gap-2">
                {kill_switch_active ? (
                    <ShieldAlert size={16} className="text-red-400" />
                ) : (
                    <ShieldCheck size={16} className="text-green-400" />
                )}
                Risk Management
            </h3>

            {/* Kill Switch Status */}
            <div className={`rounded p-2 flex items-center justify-between ${kill_switch_active
                    ? 'bg-red-900/30 border border-red-500/50'
                    : 'bg-green-900/20 border border-green-500/30'
                }`}>
                <span className="text-xs text-gray-300">Kill Switch</span>
                <span className={`text-sm font-bold ${kill_switch_active ? 'text-red-400' : 'text-green-400'}`}>
                    {kill_switch_active ? '🛑 ACTIVE' : '✅ OFF'}
                </span>
            </div>

            {/* Daily P&L */}
            <div className="flex justify-between items-center">
                <span className="text-xs text-gray-500">Daily P&L</span>
                <span className={`text-sm font-bold ${isProfit ? 'text-green-400' : 'text-red-400'}`}>
                    {isProfit ? '+' : ''}{((daily_pnl_percent || 0) * 100).toFixed(2)}%
                </span>
            </div>

            {/* Risk Budget Used */}
            <div className="space-y-1">
                <div className="flex justify-between text-xs">
                    <span className="text-gray-500">Risk Budget Used</span>
                    <span className="text-gray-400">{riskUsedPercent.toFixed(0)}%</span>
                </div>
                <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
                    <div
                        className={`h-full transition-all duration-300 ${riskUsedPercent > 80 ? 'bg-red-500' : riskUsedPercent > 50 ? 'bg-yellow-500' : 'bg-green-500'
                            }`}
                        style={{ width: `${Math.min(riskUsedPercent, 100)}%` }}
                    />
                </div>
            </div>

            {/* Quick Stats */}
            <div className="grid grid-cols-2 gap-2 text-xs">
                <div className="bg-gray-800/50 rounded p-2">
                    <span className="text-gray-500">Positions</span>
                    <div className="text-white font-bold">{positions_count || 0}</div>
                </div>
                <div className="bg-gray-800/50 rounded p-2">
                    <span className="text-gray-500">Exposure</span>
                    <div className="text-white font-bold">{((total_exposure || 0) * 100).toFixed(0)}%</div>
                </div>
            </div>

            {/* Status Message */}
            {message && (
                <div className="text-xs text-gray-400 italic">
                    {message}
                </div>
            )}
        </div>
    );
};

export default RiskStatusPanel;
