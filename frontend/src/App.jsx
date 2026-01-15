import { useState, useEffect, useCallback } from 'react';
import { StockChart } from './components/StockChart';

import { StockSearch } from './components/StockSearch';
import { IndicatorPanel } from './components/IndicatorPanel';
import { BrokerSummaryPanel } from './components/BrokerSummaryPanel';
import ADKChatPanel from './components/ADKChatPanel';
import ConvictionPanel from './components/ConvictionPanel';
import ScannerPanel from './components/ScannerPanel';
import FinancialReportPanel from './components/FinancialReportPanel';
import SettingsPanel from './components/SettingsPanel';

import { Activity, ShieldCheck, TrendingUp, BarChart3, Search, Settings } from 'lucide-react';
import { API_BASE_URL, WS_BASE_URL } from './config';

function App() {
  const [activeTicker, setActiveTicker] = useState('BBCA');
  const [consensus, setConsensus] = useState(null);
  const [candleData, setCandleData] = useState([]);
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [ws, setWs] = useState(null);

  // Panel state (like crypto-trades)
  const [activePanel, setActivePanel] = useState('ai');

  // Scanner modal state
  const [showScanner, setShowScanner] = useState(false);

  // Settings modal state
  const [showSettings, setShowSettings] = useState(false);

  // Remora-Quant features
  const [orderFlow, setOrderFlow] = useState(null);
  const [tradingSignal, setTradingSignal] = useState(null);
  const [riskStatus, setRiskStatus] = useState(null);
  const [indicatorData, setIndicatorData] = useState(null);
  const [currentPrice, setCurrentPrice] = useState(null);
  const [priceChange, setPriceChange] = useState(null);

  // AI Status tracking
  const [aiStatus, setAiStatus] = useState('idle');
  const [hasUnreadAi, setHasUnreadAi] = useState(false);

  // Timeframe state (like crypto-trades)
  const [timeframe, setTimeframe] = useState('1y');

  // Indicator toggles - all indicators from research
  const [indicators, setIndicators] = useState({
    // Moving Averages
    ema9: false,
    ema21: false,
    ema55: false,
    ema200: true,  // Default enabled
    sma50: false,
    sma100: false,
    sma200: false,
    // Oscillators
    rsi: true,     // Default enabled
    macdV: false,
    stochastic: false,
    cci: false,
    // Volume
    vwap: false,
    obv: false,
    volumeProfile: false,
    bubbleOverlay: false,
    // Ichimoku Cloud
    ichimokuCloud: false,
    ichimokuTenkan: false,
    ichimokuKijun: false,
    // Support/Resistance
    pivotPoints: false,
    fibonacci: false,
    bollingerBands: false,
    // Smart Money
    orderFlow: true,  // Default enabled
    brokerFlow: false,
  });

  const handleIndicatorToggle = useCallback((key) => {
    setIndicators(prev => ({ ...prev, [key]: !prev[key] }));
  }, []);

  // AI status handler
  const handleAiStatusChange = useCallback((status) => {
    setAiStatus(status);
    if (status === 'done' && activePanel !== 'ai') {
      setHasUnreadAi(true);
    }
  }, [activePanel]);

  // Clear unread when switching to AI panel
  useEffect(() => {
    if (activePanel === 'ai') {
      setHasUnreadAi(false);
    }
  }, [activePanel]);

  // Fetch Risk Status periodically
  useEffect(() => {
    const fetchRiskStatus = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/v1/risk/status`);
        if (response.ok) {
          const data = await response.json();
          setRiskStatus(data);
        }
      } catch (e) {
        console.error("Failed to fetch risk status:", e);
      }
    };

    fetchRiskStatus();
    const interval = setInterval(fetchRiskStatus, 30000);
    return () => clearInterval(interval);
  }, []);

  // AUTO-LOAD: Fetch data when stock is selected (like crypto-trades)
  const loadStockData = useCallback(async (ticker) => {
    if (!ticker) return;

    setCandleData([]);
    setOrderFlow(null);
    setIndicatorData(null);
    setLoading(true);

    try {
      // Fetch chart & indicators with timeframe
      const response = await fetch(`${API_BASE_URL}/api/v1/indicators/${ticker}?period=${timeframe}`);
      if (response.ok) {
        const data = await response.json();
        setIndicatorData(data);
        if (data.historical_prices?.length > 0) {
          setCandleData(data.historical_prices);
        }
      }

      // Fetch order flow
      const orderFlowRes = await fetch(`${API_BASE_URL}/api/v1/orderflow/${ticker}`);
      if (orderFlowRes.ok) {
        const ofData = await orderFlowRes.json();
        setOrderFlow(ofData);
      }

      // Fetch Analysis (Broker Summary / Bandarmology)
      // Use lightweight endpoint to avoid AI costs on initial load
      const analyzeRes = await fetch(`${API_BASE_URL}/api/v1/bandarmology/${ticker}`);
      if (analyzeRes.ok) {
        const analyzeData = await analyzeRes.json();
        // Wrap in expected structure for BrokerSummaryPanel
        setConsensus({ bandarmology: analyzeData });
      }

      setLogs(prev => [...prev, {
        timestamp: new Date().toLocaleTimeString(),
        analyst: "SYSTEM",
        content: `📊 Data loaded for ${ticker}`
      }]);

    } catch (e) {
      console.error(e);
      setLogs(prev => [...prev, {
        timestamp: new Date().toLocaleTimeString(),
        analyst: "SYSTEM",
        content: `Error: ${e.message}`
      }]);
    } finally {
      setLoading(false);
    }
  }, [timeframe]);  // CRITICAL: Include timeframe so API uses current value

  // Refresh only analysis data (called after CSV Upload)
  const refreshAnalysis = useCallback(async () => {
    if (!activeTicker) return;
    try {
      const analyzeRes = await fetch(`${API_BASE_URL}/api/v1/bandarmology/${activeTicker}`);
      if (analyzeRes.ok) {
        const analyzeData = await analyzeRes.json();
        setConsensus(prev => ({ ...prev, bandarmology: analyzeData }));
      }
    } catch (e) {
      console.error("Refresh analysis failed:", e);
    }
  }, [activeTicker]);

  // Handle stock selection - AUTO LOAD
  const handleStockSelect = useCallback((selectedTicker) => {
    setActiveTicker(selectedTicker);
    loadStockData(selectedTicker);
  }, [loadStockData]);

  // Initial load + reload when timeframe changes
  useEffect(() => {
    loadStockData(activeTicker);
  }, [timeframe]); // eslint-disable-line react-hooks/exhaustive-deps

  // WebSocket for real-time updates
  useEffect(() => {
    let socket = null;
    let isMounted = true;

    const connectTimeout = setTimeout(() => {
      if (!isMounted) return;

      socket = new WebSocket(`${WS_BASE_URL}/api/v1/ws/${activeTicker}`);

      socket.onopen = () => {
        if (!isMounted) return;
        console.log("WebSocket Connected");
        setLogs(prev => [...prev, {
          timestamp: new Date().toLocaleTimeString(),
          analyst: "SYSTEM",
          content: `🔌 Connected to Remora-Quant feed for ${activeTicker}`
        }]);
      };

      socket.onmessage = (event) => {
        if (!isMounted) return;
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'update') {
            const newCandle = {
              time: data.timestamp,
              open: data.price,
              high: data.price,
              low: data.price,
              close: data.price
            };

            setCandleData(prev => {
              if (prev.length > 0 && prev[prev.length - 1].time === data.timestamp) {
                const updated = [...prev];
                updated[updated.length - 1] = {
                  ...updated[updated.length - 1],
                  close: data.price,
                  high: Math.max(updated[updated.length - 1].high, data.price),
                  low: Math.min(updated[updated.length - 1].low, data.price)
                };
                return updated;
              }
              return [...prev, newCandle];
            });

            // Update current price for display
            setCurrentPrice(data.price);

            setConsensus(prev => prev ? { ...prev, current_price: data.price } : prev);

            if (data.order_flow) {
              setOrderFlow(prev => ({
                ...prev,
                obi: data.order_flow.obi,
                signal: data.order_flow.signal,
                signal_strength: data.order_flow.signal_strength,
                net_flow: data.order_flow.net_flow,
                iceberg_detected: data.order_flow.iceberg_detected,
                order_book: data.order_flow.order_book // Include order book updates
              }));
            }
          }
        } catch (e) {
          console.log("WebSocket message (non-JSON):", event.data);
        }
      };

      socket.onerror = () => {
        if (!isMounted) return;
        console.log("WebSocket connection error (will retry)");
      };

      socket.onclose = () => {
        console.log("WebSocket Disconnected");
      };

      setWs(socket);
    }, 100);

    return () => {
      isMounted = false;
      clearTimeout(connectTimeout);
      if (socket && socket.readyState === WebSocket.OPEN) {
        socket.close();
      }
    };
  }, [activeTicker]);

  const formatIDR = (value) => {
    if (typeof value !== 'number') return 'Rp 0';
    return new Intl.NumberFormat('id-ID', { style: 'currency', currency: 'IDR' }).format(value);
  }

  return (
    <div className="min-h-screen p-4 md:p-6 text-white bg-brand-dark">
      {/* Header with Search + Tabs */}
      <header className="mb-4">
        <div className="flex flex-col lg:flex-row lg:justify-between lg:items-center gap-4">
          {/* Title */}
          <div>
            <h1 className="text-xl md:text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-brand-accent to-blue-500">
              Saham Indo Analysis
            </h1>
            <p className="text-gray-500 text-xs">Smart Money Detection & Order Flow</p>
          </div>

          {/* Search + Tabs inline */}
          <div className="flex flex-wrap items-center gap-3">
            <StockSearch onSelect={handleStockSelect} initialValue={activeTicker} />

            {/* Timeframe Selector */}
            <div className="flex gap-1 bg-gray-800 rounded-lg p-1">
              {[
                { value: '1d', label: '1D' },
                { value: '5d', label: '1W' },
                { value: '1mo', label: '1M' },
                { value: '3mo', label: '3M' },
                { value: '6mo', label: '6M' },
                { value: '1y', label: '1Y' },
                { value: '2y', label: '2Y' },
              ].map(tf => (
                <button
                  key={tf.value}
                  onClick={() => setTimeframe(tf.value)}
                  className={`py-1 px-2 rounded text-xs font-medium transition-all ${timeframe === tf.value
                    ? 'bg-brand-accent text-white'
                    : 'text-gray-400 hover:text-white'
                    }`}
                >
                  {tf.label}
                </button>
              ))}
            </div>

            {loading && (
              <span className="text-sm text-gray-400 animate-pulse">Loading...</span>
            )}

            {/* Panel Tabs */}
            <div className="flex gap-1 bg-gray-800 rounded-lg p-1">
              <button
                onClick={() => setActivePanel('ai')}
                className={`py-1.5 px-3 rounded-md text-xs font-medium transition-all ${activePanel === 'ai'
                  ? 'bg-brand-accent text-white'
                  : 'text-gray-400 hover:text-white'
                  }`}
              >
                🤖 AI
                {aiStatus === 'loading' && activePanel !== 'ai' && (
                  <span className="ml-1 inline-block w-1.5 h-1.5 bg-yellow-400 rounded-full animate-pulse"></span>
                )}
                {hasUnreadAi && (
                  <span className="ml-1 inline-block w-1.5 h-1.5 bg-green-400 rounded-full"></span>
                )}
              </button>
              <button
                onClick={() => setActivePanel('conviction')}
                className={`py-1.5 px-3 rounded-md text-xs font-medium transition-all ${activePanel === 'conviction'
                  ? 'bg-brand-accent text-white'
                  : 'text-gray-400 hover:text-white'
                  }`}
              >
                🎯 Score
              </button>

              <button
                onClick={() => setActivePanel('indicators')}
                className={`py-1.5 px-3 rounded-md text-xs font-medium transition-all ${activePanel === 'indicators'
                  ? 'bg-brand-accent text-white'
                  : 'text-gray-400 hover:text-white'
                  }`}
              >
                📉 Ind
              </button>
            </div>

            {/* Settings Button */}
            <button
              onClick={() => setShowSettings(true)}
              className="p-2 rounded-lg bg-gray-800 text-gray-400 hover:text-white hover:bg-gray-700 transition-all"
              title="Settings"
            >
              <Settings size={18} />
            </button>
          </div>
        </div>
      </header>

      {/* Main Grid: Chart (Left) + Sidebar (Right) */}
      <div className="grid grid-cols-12 gap-4">
        {/* Left Column: Chart + Metrics */}
        <div className="col-span-12 lg:col-span-8 space-y-4">
          {/* Chart */}
          <div className="glass-card p-1">
            <StockChart
              key={activeTicker}
              candleData={candleData}
              consensusData={consensus}
              indicatorData={indicatorData}
              activeIndicators={indicators}
            />
          </div>

          {/* Metrics Row */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            <MetricCard
              label="Harga Terakhir"
              value={currentPrice ? formatIDR(currentPrice) : (candleData.length > 0 ? formatIDR(candleData[candleData.length - 1]?.close) : '-')}
              subvalue={priceChange ? `${priceChange >= 0 ? '+' : ''}${priceChange.toFixed(2)}%` : ''}
              icon={<Activity className="text-blue-400" size={16} />}
            />

            <MetricCard
              label="RSI"
              value={indicatorData?.indicators?.rsi ? indicatorData.indicators.rsi.toFixed(1) : '-'}
              subvalue={indicatorData?.indicators?.rsi > 70 ? 'Overbought' : indicatorData?.indicators?.rsi < 30 ? 'Oversold' : 'Neutral'}
              icon={<BarChart3 className="text-purple-400" size={16} />}
            />
            <MetricCard
              label="MACD"
              value={indicatorData?.indicators?.macd ? indicatorData.indicators.macd.toFixed(1) : '-'}
              subvalue={indicatorData?.overall_bias || 'Neutral'}
              icon={<TrendingUp className="text-yellow-400" size={16} />}
            />
          </div>
        </div>

        {/* Right Column: Panel Content (Sidebar) */}
        <div className="col-span-12 lg:col-span-4">
          <div className="sticky top-4">
            {activePanel === 'ai' && (
              <ADKChatPanel symbol={activeTicker} onStatusChange={handleAiStatusChange} />
            )}
            {activePanel === 'conviction' && (
              <ConvictionPanel
                symbol={activeTicker}
                orderFlow={orderFlow}
                indicatorData={indicatorData}
                bandarmologyData={consensus?.bandarmology}
              />
            )}

            {activePanel === 'indicators' && (
              <IndicatorPanel indicators={indicators} onToggle={handleIndicatorToggle} />
            )}
          </div>
        </div>

        {/* Bottom Row: Analysis Panels (Full Width) */}
        <div className="col-span-12 space-y-4">
          {/* Financial Report Panel (Stockbit Data) */}
          <FinancialReportPanel ticker={activeTicker} />

          {/* Broker Summary (Full Width - Stockbit Style) */}
          <BrokerSummaryPanel
            data={consensus?.bandarmology}
            ticker={activeTicker}
            isLoading={loading}
            onDataUpdate={refreshAnalysis}
          />

          {/* Scan Stocks Button */}
          <button
            onClick={() => setShowScanner(true)}
            className="w-full py-4 bg-gradient-to-r from-emerald-500 to-teal-600 
                       hover:from-emerald-600 hover:to-teal-700 
                       rounded-xl font-bold text-lg flex items-center justify-center gap-3
                       transition-all duration-200 shadow-lg hover:shadow-emerald-500/20"
          >
            <Search size={20} />
            Scan Stocks (AI-Powered Scanner)
          </button>
        </div>
      </div>

      {/* Scanner Modal Overlay */}
      {showScanner && (
        <ScannerPanel
          onSelectStock={(ticker) => {
            handleStockSelect(ticker);
            setShowScanner(false);
          }}
          onClose={() => setShowScanner(false)}
        />
      )}

      {/* Settings Modal */}
      <SettingsPanel
        isOpen={showSettings}
        onClose={() => setShowSettings(false)}
      />
    </div>
  );
}

const MetricCard = ({ label, value, subvalue, icon }) => (
  <div className="glass-card p-4 flex flex-col justify-between">
    <div className="flex justify-between items-start mb-2">
      <span className="text-gray-400 text-xs">{label}</span>
      {icon}
    </div>
    <div>
      <div className="text-xl font-bold">{value}</div>
      {subvalue && <div className="text-xs text-gray-500">{subvalue}</div>}
    </div>
  </div>
);

export default App;
