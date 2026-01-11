import { useState, useEffect } from 'react';
import { BarChart2, TrendingUp, TrendingDown, Activity } from 'lucide-react';

// Dummy order book data for when API is not available
const DUMMY_ORDER_BOOK = {
    bids: [
        { price: 9850, volume: 15000, total: 15000 },
        { price: 9825, volume: 28000, total: 43000 },
        { price: 9800, volume: 45000, total: 88000 },
        { price: 9775, volume: 32000, total: 120000 },
        { price: 9750, volume: 25000, total: 145000 },
        { price: 9725, volume: 18000, total: 163000 },
        { price: 9700, volume: 52000, total: 215000 },
        { price: 9675, volume: 12000, total: 227000 },
    ],
    asks: [
        { price: 9875, volume: 12000, total: 12000 },
        { price: 9900, volume: 22000, total: 34000 },
        { price: 9925, volume: 38000, total: 72000 },
        { price: 9950, volume: 15000, total: 87000 },
        { price: 9975, volume: 28000, total: 115000 },
        { price: 10000, volume: 65000, total: 180000 },
        { price: 10025, volume: 20000, total: 200000 },
        { price: 10050, volume: 8000, total: 208000 },
    ],
    lastPrice: 9850,
    spread: 25,
    spreadPercent: 0.25,
    imbalance: 0.35, // positive = more bids, negative = more asks
};

/**
 * OrderBookPanel - Professional Order Book visualization
 * Features: Depth bars, bid/ask ladder, spread display, imbalance indicator
 */
export default function OrderBookPanel({ data, ticker }) {
    const [displayData, setDisplayData] = useState(DUMMY_ORDER_BOOK);
    // Check if using demo data: no data at all, or is_demo flag is true
    const isUsingDemo = !data || data.is_demo === true;

    useEffect(() => {
        if (data) {
            setDisplayData(data);
        }
    }, [data]);

    // Calculate max volume for scaling bars
    const maxBidVolume = Math.max(...displayData.bids.map(b => b.volume));
    const maxAskVolume = Math.max(...displayData.asks.map(a => a.volume));
    const maxVolume = Math.max(maxBidVolume, maxAskVolume);

    // Calculate total volumes for imbalance
    const totalBidVolume = displayData.bids.reduce((sum, b) => sum + b.volume, 0);
    const totalAskVolume = displayData.asks.reduce((sum, a) => sum + a.volume, 0);
    const imbalanceRatio = totalBidVolume / (totalBidVolume + totalAskVolume);

    const formatVolume = (vol) => {
        if (vol >= 1000000) return (vol / 1000000).toFixed(1) + 'M';
        if (vol >= 1000) return (vol / 1000).toFixed(0) + 'K';
        return vol.toString();
    };

    const formatPrice = (price) => {
        return new Intl.NumberFormat('id-ID').format(price);
    };

    return (
        <div className="glass-card">
            {/* Header */}
            <div className="p-3 border-b border-white/10 flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <BarChart2 size={16} className="text-brand-accent" />
                    <h3 className="font-semibold text-sm">Order Book</h3>
                    {isUsingDemo ? (
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-yellow-500/20 text-yellow-400">Demo</span>
                    ) : (
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-green-500/20 text-green-400">Real Data</span>
                    )}
                </div>
                <div className="flex items-center gap-2">
                    <span className="text-xs text-gray-400">Spread:</span>
                    <span className="text-xs font-mono text-white">{displayData.spread} ({displayData.spreadPercent}%)</span>
                </div>
            </div>

            {/* Imbalance Bar */}
            <div className="px-3 py-2 border-b border-white/5">
                <div className="flex items-center justify-between mb-1">
                    <span className="text-[10px] text-green-400 flex items-center gap-1">
                        <TrendingUp size={10} /> Bid {(imbalanceRatio * 100).toFixed(0)}%
                    </span>
                    <span className="text-[10px] text-gray-500">Volume Imbalance</span>
                    <span className="text-[10px] text-red-400 flex items-center gap-1">
                        Ask {((1 - imbalanceRatio) * 100).toFixed(0)}% <TrendingDown size={10} />
                    </span>
                </div>
                <div className="h-1.5 bg-gray-700 rounded-full overflow-hidden flex">
                    <div
                        className="h-full bg-gradient-to-r from-green-600 to-green-400 transition-all duration-500"
                        style={{ width: `${imbalanceRatio * 100}%` }}
                    />
                    <div
                        className="h-full bg-gradient-to-r from-red-400 to-red-600 transition-all duration-500"
                        style={{ width: `${(1 - imbalanceRatio) * 100}%` }}
                    />
                </div>
            </div>

            {/* Order Book Table */}
            <div className="p-2">
                {/* Column Headers */}
                <div className="grid grid-cols-2 gap-1 mb-2">
                    <div className="grid grid-cols-3 text-[10px] text-gray-500 px-1">
                        <span>Total</span>
                        <span className="text-center">Vol</span>
                        <span className="text-right">Bid</span>
                    </div>
                    <div className="grid grid-cols-3 text-[10px] text-gray-500 px-1">
                        <span>Ask</span>
                        <span className="text-center">Vol</span>
                        <span className="text-right">Total</span>
                    </div>
                </div>

                {/* Order Book Rows */}
                <div className="space-y-0.5">
                    {displayData.bids.map((bid, idx) => {
                        const ask = displayData.asks[idx];
                        const bidBarWidth = (bid.volume / maxVolume) * 100;
                        const askBarWidth = ask ? (ask.volume / maxVolume) * 100 : 0;

                        return (
                            <div key={idx} className="grid grid-cols-2 gap-1">
                                {/* Bid Side */}
                                <div className="relative grid grid-cols-3 items-center text-xs py-1 px-1 rounded-l hover:bg-green-500/10 transition-colors">
                                    {/* Background bar */}
                                    <div
                                        className="absolute right-0 top-0 h-full bg-green-500/20 rounded-l transition-all duration-300"
                                        style={{ width: `${bidBarWidth}%` }}
                                    />
                                    <span className="relative text-gray-400 font-mono text-[10px]">{formatVolume(bid.total)}</span>
                                    <span className="relative text-center text-green-400 font-mono">{formatVolume(bid.volume)}</span>
                                    <span className="relative text-right text-green-300 font-bold">{formatPrice(bid.price)}</span>
                                </div>

                                {/* Ask Side */}
                                {ask && (
                                    <div className="relative grid grid-cols-3 items-center text-xs py-1 px-1 rounded-r hover:bg-red-500/10 transition-colors">
                                        {/* Background bar */}
                                        <div
                                            className="absolute left-0 top-0 h-full bg-red-500/20 rounded-r transition-all duration-300"
                                            style={{ width: `${askBarWidth}%` }}
                                        />
                                        <span className="relative text-red-300 font-bold">{formatPrice(ask.price)}</span>
                                        <span className="relative text-center text-red-400 font-mono">{formatVolume(ask.volume)}</span>
                                        <span className="relative text-right text-gray-400 font-mono text-[10px]">{formatVolume(ask.total)}</span>
                                    </div>
                                )}
                            </div>
                        );
                    })}
                </div>

                {/* Summary Footer */}
                <div className="mt-3 pt-2 border-t border-white/5 grid grid-cols-2 gap-4">
                    <div className="text-center">
                        <div className="text-[10px] text-gray-500 mb-1">Total Bid Volume</div>
                        <div className="text-sm font-bold text-green-400">{formatVolume(totalBidVolume)}</div>
                    </div>
                    <div className="text-center">
                        <div className="text-[10px] text-gray-500 mb-1">Total Ask Volume</div>
                        <div className="text-sm font-bold text-red-400">{formatVolume(totalAskVolume)}</div>
                    </div>
                </div>
            </div>
        </div>
    );
}
