import { useState, useEffect } from 'react';
import { Activity, TrendingUp, TrendingDown, AlertTriangle, Eye, EyeOff, Zap } from 'lucide-react';
import { API_BASE_URL } from '../config';

/**
 * TransactionAnalysisPanel - Lee-Ready HAKA/HAKI Analysis
 * 
 * Shows:
 * - HAKA/HAKI volume breakdown
 * - Net Flow indicator
 * - OBI Divergence alerts
 * - Sweep detection
 * - Iceberg order detection
 */
export default function TransactionAnalysisPanel({ ticker, orderFlow }) {
    const [expanded, setExpanded] = useState(true);

    if (!orderFlow) {
        return (
            <div className="glass-card p-4">
                <div className="flex items-center gap-2 text-gray-400">
                    <Activity size={16} />
                    <span>Load a stock to see transaction analysis</span>
                </div>
            </div>
        );
    }

    const hakaPercent = orderFlow.flow_ratio ? (orderFlow.flow_ratio * 100).toFixed(1) : 50;
    const hakiPercent = (100 - hakaPercent).toFixed(1);

    const netFlowColor = orderFlow.net_flow > 0 ? 'text-green-400' : orderFlow.net_flow < 0 ? 'text-red-400' : 'text-gray-400';
    const netFlowIcon = orderFlow.net_flow > 0 ? <TrendingUp size={14} /> : <TrendingDown size={14} />;

    return (
        <div className="glass-card">
            <div
                className="p-3 border-b border-white/10 flex items-center justify-between cursor-pointer"
                onClick={() => setExpanded(!expanded)}
            >
                <div className="flex items-center gap-2">
                    <Activity size={16} className="text-brand-accent" />
                    <h3 className="font-semibold text-sm">Transaction Analysis</h3>
                    {orderFlow.divergence_detected && (
                        <span className="px-2 py-0.5 rounded text-xs bg-red-500/20 text-red-400 flex items-center gap-1">
                            <AlertTriangle size={10} /> Alert
                        </span>
                    )}
                </div>
                <span className="text-xs text-gray-500">{ticker}</span>
            </div>

            {expanded && (
                <div className="p-3 space-y-4">
                    {/* HAKA/HAKI Volume Breakdown */}
                    <div className="space-y-2">
                        <div className="flex justify-between text-xs text-gray-400">
                            <span>HAKA (Buy Aggr.)</span>
                            <span>HAKI (Sell Aggr.)</span>
                        </div>
                        <div className="flex h-3 rounded-full overflow-hidden">
                            <div
                                className="bg-green-500 transition-all duration-500"
                                style={{ width: `${hakaPercent}%` }}
                            />
                            <div
                                className="bg-red-500 transition-all duration-500"
                                style={{ width: `${hakiPercent}%` }}
                            />
                        </div>
                        <div className="flex justify-between text-xs font-semibold">
                            <span className="text-green-400">{hakaPercent}%</span>
                            <span className="text-red-400">{hakiPercent}%</span>
                        </div>
                    </div>

                    {/* Volume Stats */}
                    <div className="grid grid-cols-2 gap-2 text-xs">
                        <div className="bg-green-500/10 rounded p-2">
                            <div className="text-gray-400">HAKA Volume</div>
                            <div className="text-green-400 font-bold">
                                {(orderFlow.haka_volume || 0).toLocaleString('id-ID')}
                            </div>
                        </div>
                        <div className="bg-red-500/10 rounded p-2">
                            <div className="text-gray-400">HAKI Volume</div>
                            <div className="text-red-400 font-bold">
                                {(orderFlow.haki_volume || 0).toLocaleString('id-ID')}
                            </div>
                        </div>
                    </div>

                    {/* Net Flow */}
                    <div className="flex items-center justify-between p-2 bg-gray-800/50 rounded">
                        <span className="text-xs text-gray-400">Net Flow</span>
                        <div className={`flex items-center gap-1 font-bold ${netFlowColor}`}>
                            {netFlowIcon}
                            {(orderFlow.net_flow || 0).toLocaleString('id-ID')}
                        </div>
                    </div>

                    {/* OBI Divergence Alert */}
                    {orderFlow.divergence_detected && (
                        <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg">
                            <div className="flex items-center gap-2 text-red-400 font-semibold text-sm mb-1">
                                <AlertTriangle size={14} />
                                OBI Divergence Detected
                            </div>
                            <div className="text-xs text-gray-400">
                                {orderFlow.divergence_message || 'Possible manipulation detected. Trade with caution.'}
                            </div>
                        </div>
                    )}

                    {/* Sweep Detection */}
                    {orderFlow.sweep_detected && (
                        <div className="p-3 bg-purple-500/10 border border-purple-500/30 rounded-lg">
                            <div className="flex items-center gap-2 text-purple-400 font-semibold text-sm mb-1">
                                <Zap size={14} />
                                Sweep Pattern Detected
                            </div>
                            <div className="text-xs text-gray-400">
                                Institutional {orderFlow.net_flow > 0 ? 'buying' : 'selling'} sweep in progress.
                                {orderFlow.net_flow > 0 ? ' Consider following momentum.' : ' Consider exit.'}
                            </div>
                        </div>
                    )}

                    {/* Iceberg Detection */}
                    {orderFlow.iceberg_detected && (
                        <div className="p-3 bg-blue-500/10 border border-blue-500/30 rounded-lg">
                            <div className="flex items-center gap-2 text-blue-400 font-semibold text-sm mb-1">
                                {orderFlow.iceberg_details?.type === 'ICEBERG_BID' ? <Eye size={14} /> : <EyeOff size={14} />}
                                Iceberg Order Detected
                            </div>
                            <div className="text-xs text-gray-400">
                                {orderFlow.iceberg_details?.interpretation || 'Hidden liquidity detected at current level.'}
                            </div>
                            {orderFlow.hidden_volume_estimate > 0 && (
                                <div className="text-xs text-blue-400 mt-1">
                                    Est. Hidden Volume: {orderFlow.hidden_volume_estimate.toLocaleString('id-ID')}
                                </div>
                            )}
                        </div>
                    )}

                    {/* Institutional Levels */}
                    {orderFlow.institutional_levels && (
                        <div className="space-y-2">
                            {orderFlow.institutional_levels.institutional_support?.length > 0 && (
                                <div className="text-xs">
                                    <div className="text-gray-400 mb-1">🟢 Institutional Support</div>
                                    <div className="flex flex-wrap gap-1">
                                        {orderFlow.institutional_levels.institutional_support.slice(0, 3).map((level, i) => (
                                            <span key={i} className="px-2 py-1 bg-green-500/10 text-green-400 rounded">
                                                Rp {level.price?.toLocaleString('id-ID')}
                                            </span>
                                        ))}
                                    </div>
                                </div>
                            )}
                            {orderFlow.institutional_levels.institutional_resistance?.length > 0 && (
                                <div className="text-xs">
                                    <div className="text-gray-400 mb-1">🔴 Institutional Resistance</div>
                                    <div className="flex flex-wrap gap-1">
                                        {orderFlow.institutional_levels.institutional_resistance.slice(0, 3).map((level, i) => (
                                            <span key={i} className="px-2 py-1 bg-red-500/10 text-red-400 rounded">
                                                Rp {level.price?.toLocaleString('id-ID')}
                                            </span>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </div>
                    )}

                    {/* Signal Summary */}
                    <div className="pt-2 border-t border-white/10">
                        <div className="text-xs text-gray-400 mb-1">Signal</div>
                        <div className="text-sm font-semibold">
                            {orderFlow.signal || 'NEUTRAL'}
                        </div>
                        {orderFlow.recommendation && (
                            <div className="text-xs text-gray-500 mt-1">
                                {orderFlow.recommendation}
                            </div>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}
