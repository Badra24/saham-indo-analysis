import { useState, useEffect, useRef, useCallback } from 'react';
import { FileText, TrendingUp, Building2, DollarSign, Percent, RefreshCw, AlertCircle } from 'lucide-react';
import { API_BASE_URL } from '../config';

/**
 * FinancialReportPanel - Displays financial data from Stockbit
 * 
 * Fetches key financial metrics directly from Stockbit API.
 * No manual PDF uploads required!
 */
export default function FinancialReportPanel({ ticker }) {
    const [data, setData] = useState(null);
    const [companyInfo, setCompanyInfo] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    // Cache to prevent redundant fetches
    const cacheRef = useRef({});
    const abortControllerRef = useRef(null);

    const fetchData = useCallback(async (forceRefresh = false) => {
        if (!ticker) return;

        // Check cache first
        if (!forceRefresh && cacheRef.current[ticker]) {
            setData(cacheRef.current[ticker].data);
            setCompanyInfo(cacheRef.current[ticker].company);
            return;
        }

        // Abort previous request
        if (abortControllerRef.current) {
            abortControllerRef.current.abort();
        }
        abortControllerRef.current = new AbortController();

        setLoading(true);
        setError(null);

        try {
            const [finRes, compRes] = await Promise.all([
                fetch(`${API_BASE_URL}/api/v1/stockbit/financial/${ticker}`, {
                    signal: abortControllerRef.current.signal
                }),
                fetch(`${API_BASE_URL}/api/v1/stockbit/company/${ticker}`, {
                    signal: abortControllerRef.current.signal
                })
            ]);

            let finData = null;
            let compData = null;

            if (finRes.ok) {
                finData = await finRes.json();
                setData(finData);
            }

            if (compRes.ok) {
                compData = await compRes.json();
                setCompanyInfo(compData.data);
            }

            // Cache the results
            cacheRef.current[ticker] = { data: finData, company: compData?.data };
        } catch (err) {
            if (err.name !== 'AbortError') {
                setError(err.message);
            }
        } finally {
            setLoading(false);
        }
    }, [ticker]);

    useEffect(() => {
        fetchData();

        // Cleanup on unmount
        return () => {
            if (abortControllerRef.current) {
                abortControllerRef.current.abort();
            }
        };
    }, [fetchData]);

    const formatValue = (val) => {
        if (!val) return '-';
        if (val >= 1e15) return `Rp ${(val / 1e15).toFixed(2)} Kuadriliun`;
        if (val >= 1e12) return `Rp ${(val / 1e12).toFixed(2)} Triliun`;
        if (val >= 1e9) return `Rp ${(val / 1e9).toFixed(2)} Miliar`;
        if (val >= 1e6) return `Rp ${(val / 1e6).toFixed(2)} Juta`;
        return val.toLocaleString('id-ID');
    };

    const MetricCard = ({ label, value, icon: Icon, color = "text-white" }) => (
        <div className="bg-gray-800/50 rounded-lg p-3">
            <div className="flex items-center gap-2 mb-1">
                {Icon && <Icon size={14} className="text-gray-400" />}
                <span className="text-xs text-gray-400">{label}</span>
            </div>
            <div className={`text-lg font-bold ${color}`}>{value}</div>
        </div>
    );

    return (
        <div className="glass-card">
            {/* Header */}
            <div className="p-4 border-b border-white/10 flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <FileText size={18} className="text-blue-400" />
                    <h3 className="font-semibold">Financial Report</h3>
                    <span className="text-xs text-gray-500">Stockbit Data</span>
                </div>
                <button
                    onClick={() => fetchData(true)}
                    disabled={loading}
                    className="p-2 hover:bg-gray-700 rounded-lg transition-colors"
                >
                    <RefreshCw size={16} className={loading ? 'animate-spin text-blue-400' : 'text-gray-400'} />
                </button>
            </div>

            {/* Content */}
            <div className="p-4">
                {loading && (
                    <div className="flex items-center justify-center py-8 text-gray-400">
                        <RefreshCw size={20} className="animate-spin mr-2" />
                        Loading financial data...
                    </div>
                )}

                {error && (
                    <div className="flex items-center gap-2 py-4 text-red-400">
                        <AlertCircle size={16} />
                        <span>{error}</span>
                    </div>
                )}

                {!loading && !error && data && (
                    <>
                        {/* Company Info */}
                        {companyInfo && (
                            <div className="mb-4 pb-4 border-b border-gray-700/50">
                                <div className="flex items-center gap-3">
                                    <Building2 size={20} className="text-blue-400" />
                                    <div>
                                        <div className="font-bold text-white">{companyInfo.name || ticker}</div>
                                        <div className="text-xs text-gray-400">
                                            {companyInfo.sector} • {companyInfo.subsector}
                                        </div>
                                    </div>
                                </div>
                            </div>
                        )}

                        {/* Metrics Grid */}
                        {data.metrics && Object.keys(data.metrics).length > 0 ? (
                            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                                {data.metrics.market_cap && (
                                    <MetricCard
                                        label="Market Cap"
                                        value={formatValue(data.metrics.market_cap.value)}
                                        icon={DollarSign}
                                        color="text-blue-400"
                                    />
                                )}
                                {data.metrics.price && (
                                    <MetricCard
                                        label="Price"
                                        value={`Rp ${data.metrics.price.value?.toLocaleString('id-ID')}`}
                                        icon={TrendingUp}
                                        color="text-white"
                                    />
                                )}
                                {data.metrics.dividend_yield && (
                                    <MetricCard
                                        label="Dividend Yield"
                                        value={`${data.metrics.dividend_yield.value?.toFixed(2)}%`}
                                        icon={Percent}
                                        color="text-green-400"
                                    />
                                )}
                                {data.metrics.current_ratio && data.metrics.current_ratio.value > 0 && (
                                    <MetricCard
                                        label="Current Ratio"
                                        value={data.metrics.current_ratio.value?.toFixed(2)}
                                        color="text-yellow-400"
                                    />
                                )}
                                {data.metrics.debt_to_equity && data.metrics.debt_to_equity.value > 0 && (
                                    <MetricCard
                                        label="Debt/Equity"
                                        value={data.metrics.debt_to_equity.value?.toFixed(2)}
                                        color={data.metrics.debt_to_equity.value > 1 ? 'text-red-400' : 'text-green-400'}
                                    />
                                )}
                            </div>
                        ) : (
                            <div className="text-center py-6 text-gray-500">
                                <FileText size={32} className="mx-auto mb-2 opacity-50" />
                                <div>No financial data available</div>
                                <div className="text-xs">Data may not be available for this stock</div>
                            </div>
                        )}

                        {/* Source Info */}
                        <div className="mt-4 pt-3 border-t border-gray-700/50 text-xs text-gray-500 flex items-center justify-between">
                            <span>Source: {data.source === 'stockbit' ? 'Stockbit API (Live)' : 'Uploaded Data'}</span>
                            {data.metrics?.market_cap?.date && (
                                <span>Updated: {data.metrics.market_cap.date}</span>
                            )}
                        </div>
                    </>
                )}

                {!loading && !error && !data && (
                    <div className="text-center py-6 text-gray-500">
                        <FileText size={32} className="mx-auto mb-2 opacity-50" />
                        <div>Select a stock to view financial data</div>
                    </div>
                )}
            </div>
        </div>
    );
}
