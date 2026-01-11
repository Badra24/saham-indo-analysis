import { createChart, ColorType, CandlestickSeries, LineSeries, HistogramSeries } from 'lightweight-charts';
import React, { useEffect, useRef, useState, useCallback } from 'react';
import DrawingToolbar from './DrawingToolbar';
import DrawingCanvas from './DrawingCanvas';
import useDrawingTools from '../hooks/useDrawingTools';

const INDICATOR_COLORS = {
    // Moving Averages
    ema9: '#fbbf24',   // amber
    ema21: '#f59e0b',  // orange
    ema55: '#8b5cf6',  // purple
    ema200: '#ec4899', // pink
    sma50: '#84cc16',  // lime
    sma100: '#22c55e', // green
    sma200: '#f97316', // orange
    // VWAP
    vwap: '#06b6d4',   // cyan
    // Bollinger Bands
    bb_upper: 'rgba(156, 163, 175, 0.5)',
    bb_middle: 'rgba(156, 163, 175, 0.3)',
    bb_lower: 'rgba(156, 163, 175, 0.5)',
    bollingerBands: 'rgba(156, 163, 175, 0.5)',
    // Ichimoku
    ichimoku_tenkan: '#3b82f6',  // blue
    ichimoku_kijun: '#dc2626',   // red
    ichimoku_span_a: 'rgba(34, 197, 94, 0.3)',  // green fill
    ichimoku_span_b: 'rgba(239, 68, 68, 0.3)',  // red fill
    // Pivot Points
    pivot: '#10b981',     // emerald
    pivot_r1: '#ef4444',  // red
    pivot_r2: '#dc2626',  // darker red
    pivot_s1: '#22c55e',  // green
    pivot_s2: '#16a34a',  // darker green
    // Oscillators
    rsi: '#818cf8',      // indigo
    stoch_k: '#3b82f6',  // blue
    stoch_d: '#f97316',  // orange
    cci: '#c084fc',      // purple
    obv: '#14b8a6',      // teal
    // MACD
    macd: '#2962FF',
    macd_signal: '#FF6D00',
    macd_hist: '#26a69a',
    macd_v: '#2962FF',
    volume_anomaly: '#ef4444',
};

// Indicators intended for separate panes
const PANE_INDICATORS = [
    { id: 'rsi', label: 'RSI (14)', keys: ['rsi'] },
    { id: 'stochastic', label: 'Stochastic', keys: ['stoch_k', 'stoch_d'] },
    { id: 'cci', label: 'CCI (20)', keys: ['cci'] },
    { id: 'obv', label: 'On-Balance Volume', keys: ['obv'] },
    { id: 'macdV', label: 'MACD-V', keys: ['macd', 'macd_signal', 'macd_hist'] },
];

export const StockChart = ({ candleData, consensusData, indicatorData, activeIndicators }) => {
    // Refs
    const chartContainerRef = useRef();
    const mainChartRef = useRef(null);
    const mainChartInstance = useRef(null);
    const candleSeriesRef = useRef(null);
    const mainSeriesRefs = useRef({}); // For overlays

    // Pane Refs
    const paneRefs = useRef({}); // { [paneId]: divElement }
    const paneInstances = useRef({}); // { [paneId]: chartInstance }
    const paneSeriesRefs = useRef({}); // { [paneId]: { [key]: series } }

    const [isChartReady, setIsChartReady] = useState(false);

    // DRAWING TOOLS HOOK - "EXACTLY LIKE crypto-trades"
    const {
        drawings,
        activeTool,
        selectedDrawing,
        isDrawing,
        currentDrawing,
        setActiveTool,
        startDrawing,
        updateCurrentDrawing,
        completeDrawing,
        addPointToDrawing,
        selectDrawing,
        deleteSelected,
        clearAllDrawings,
        clearDrawingsByType,
        getDrawingsCountByType,
        drawingsByType, // Hook might not return this directly if it returns function, let's check hook content
        // Hook returns getDrawingsCountByType function, not drawingsByType object. 
        // We will call it in render.
        deleteDrawing,
        magnetMode,
        setMagnetMode,
        dragState,
        startDrag,
        updateDraggedPoint,
        endDrag,
        hoveredHandle,
        setHoveredHandle,
        MAGNET_THRESHOLD
    } = useDrawingTools('STOCK_CHART_DEFAULT'); // Using a default ID for persistence

    // Active Panes State
    const [activePanes, setActivePanes] = useState([]);

    // Determine active panes based on activeIndicators
    useEffect(() => {
        if (!activeIndicators) return;

        const newPanes = [];
        if (activeIndicators.rsi) newPanes.push('rsi');
        if (activeIndicators.stochastic) newPanes.push('stochastic');
        if (activeIndicators.cci) newPanes.push('cci');
        if (activeIndicators.obv) newPanes.push('obv');
        if (activeIndicators.macdV) newPanes.push('macdV');

        // Only update if changed prevents unnecessary re-renders/chart creations
        if (JSON.stringify(newPanes) !== JSON.stringify(activePanes)) {
            setActivePanes(newPanes);
        }
    }, [activeIndicators, activePanes]);

    // Initialize Main Chart
    useEffect(() => {
        if (!mainChartRef.current) return;
        if (mainChartInstance.current) return;

        console.log("Initializing Main Chart");
        const chart = createChart(mainChartRef.current, {
            layout: { background: { type: ColorType.Solid, color: '#1E1E1E' }, textColor: '#DDD' },
            width: mainChartRef.current.clientWidth,
            height: mainChartRef.current.clientHeight,
            grid: { vertLines: { color: '#2B2B43' }, horzLines: { color: '#2B2B43' } },
            timeScale: { timeVisible: true, secondsVisible: false, borderColor: '#2B2B43' },
            crosshair: { mode: 1 },
        });

        const candleSeries = chart.addSeries(CandlestickSeries, {
            upColor: '#26a69a', downColor: '#ef5350', borderVisible: false,
            wickUpColor: '#26a69a', wickDownColor: '#ef5350',
        });

        mainChartInstance.current = chart;
        candleSeriesRef.current = candleSeries;
        setIsChartReady(true);

        const handleResize = () => {
            if (mainChartRef.current) {
                chart.applyOptions({ width: mainChartRef.current.clientWidth, height: mainChartRef.current.clientHeight });
            }
        };
        window.addEventListener('resize', handleResize);

        return () => {
            window.removeEventListener('resize', handleResize);
            chart.remove();
            mainChartInstance.current = null;
            setIsChartReady(false);
        };
    }, []);

    // Manage Pane Charts (Create/Destroy)
    useEffect(() => {
        if (!isChartReady) return;

        // Cleanup removed panes
        Object.keys(paneInstances.current).forEach(paneId => {
            if (!activePanes.includes(paneId)) {
                paneInstances.current[paneId].remove();
                delete paneInstances.current[paneId];
                delete paneSeriesRefs.current[paneId];
            }
        });

        // Sync Helper (local specific to this logic)
        const syncTimeScale = (source, target) => {
            const range = source.timeScale().getVisibleRange();
            if (range && typeof range.from === 'number' && typeof range.to === 'number') {
                try { target.timeScale().setVisibleRange(range); } catch (e) { }
            }
        };

        // Create new panes
        activePanes.forEach(paneId => {
            const container = paneRefs.current[paneId];
            if (container && !paneInstances.current[paneId]) {
                const chart = createChart(container, {
                    layout: { background: { type: ColorType.Solid, color: '#1E1E1E' }, textColor: '#DDD' },
                    width: container.clientWidth,
                    height: container.clientHeight,
                    grid: { vertLines: { color: '#2B2B43' }, horzLines: { color: '#2B2B43' } },
                    timeScale: { visible: false, borderColor: '#2B2B43' }, // Hide time axis for stacked panes
                    crosshair: { mode: 1 },
                    handleScale: { axisDoubleClickReset: true },
                });

                paneInstances.current[paneId] = chart;
                paneSeriesRefs.current[paneId] = {};

                // Sync with main chart
                if (mainChartInstance.current) {
                    // Initial sync
                    syncTimeScale(mainChartInstance.current, chart);

                    // Subscribe to main chart changes
                    mainChartInstance.current.timeScale().subscribeVisibleTimeRangeChange(range => {
                        if (range && typeof range.from === 'number' && typeof range.to === 'number') {
                            try {
                                chart.timeScale().setVisibleRange(range);
                            } catch (e) { }
                        }
                    });

                    // Subscribe to this pane changes (if user drags this pane)
                    chart.timeScale().subscribeVisibleTimeRangeChange(range => {
                        if (range && typeof range.from === 'number' && typeof range.to === 'number') {
                            try {
                                mainChartInstance.current.timeScale().setVisibleRange(range);
                                // Note: Ideally we sync all other panes too, but main<->pane is usually enough
                                Object.values(paneInstances.current).forEach(other => {
                                    if (other !== chart) {
                                        try {
                                            other.timeScale().setVisibleRange(range);
                                        } catch (e) { }
                                    }
                                });
                            } catch (e) { }
                        }
                    });
                }
            }
        });

        // Re-layout main chart height (managed by CSS flex/grid usually, but we might need resize trigger)
        requestAnimationFrame(() => {
            if (mainChartInstance.current && mainChartRef.current) {
                mainChartInstance.current.applyOptions({
                    width: mainChartRef.current.clientWidth,
                    height: mainChartRef.current.clientHeight
                });
            }
        });

    }, [activePanes, isChartReady]);

    // Data Updates (Main Chart)
    useEffect(() => {
        if (!mainChartInstance.current || !candleData || candleData.length === 0) return;
        candleSeriesRef.current.setData(candleData);
    }, [candleData, isChartReady]);

    // Data Updates (Overlays & Panes)
    useEffect(() => {
        if (!indicatorData?.indicator_lines) return;
        if (!activeIndicators) return;

        const lines = indicatorData.indicator_lines;

        // --- 1. OVERLAYS (Main Chart) ---
        if (mainChartInstance.current) {
            const overlayMapping = {
                'ema9': 'ema9', 'ema21': 'ema21', 'ema55': 'ema55', 'ema200': 'ema200',
                'sma50': 'sma50', 'sma100': 'sma100', 'sma200': 'sma200',
                'vwap': 'vwap',
                'bollingerBands': ['bb_upper', 'bb_middle', 'bb_lower'],
                'ichimokuCloud': ['ichimoku_span_a', 'ichimoku_span_b'],
                'ichimokuTenkan': 'ichimoku_tenkan',
                'ichimokuKijun': 'ichimoku_kijun',
                'pivotPoints': ['pivot', 'pivot_r1', 'pivot_r2', 'pivot_s1', 'pivot_s2'],
            };

            Object.entries(activeIndicators).forEach(([frontendKey, isActive]) => {
                if (PANE_INDICATORS.find(p => p.id === frontendKey)) return; // Skip pane indicators

                const backendKeys = overlayMapping[frontendKey];
                if (!backendKeys) return;

                const keysToProcess = Array.isArray(backendKeys) ? backendKeys : [backendKeys];

                keysToProcess.forEach(key => {
                    const lineData = lines[key];
                    if (isActive && lineData && lineData.length > 0) {
                        if (!mainSeriesRefs.current[key]) {
                            const isMain = ['ema200', 'sma200', 'ichimoku_kijun'].includes(key);
                            mainSeriesRefs.current[key] = mainChartInstance.current.addSeries(LineSeries, {
                                color: INDICATOR_COLORS[key] || '#fff',
                                lineWidth: isMain ? 3 : 1,  // Increased from 2 to 3 for visibility
                                lineStyle: key.includes('pivot') ? 2 : 0,
                                crosshairMarkerVisible: false,
                            });
                        }
                        mainSeriesRefs.current[key].setData(lineData);
                    } else if (mainSeriesRefs.current[key]) {
                        mainChartInstance.current.removeSeries(mainSeriesRefs.current[key]);
                        delete mainSeriesRefs.current[key];
                    }
                });
            });

            // --- Special: Volume Anomaly Markers ---
            const volumeAnomalyKey = 'volume_anomaly';
            if (activeIndicators['volumeProfile'] && lines[volumeAnomalyKey]) {
                const markers = lines[volumeAnomalyKey]
                    .filter(d => d.value === 1)
                    .map(d => ({
                        time: d.time,
                        position: 'aboveBar',
                        color: '#ef4444',
                        shape: 'arrowDown',
                        text: 'High Vol',
                    }));

                if (candleSeriesRef.current && typeof candleSeriesRef.current.setMarkers === 'function') {
                    candleSeriesRef.current.setMarkers(markers);
                }
            } else {
                if (candleSeriesRef.current && typeof candleSeriesRef.current.setMarkers === 'function') {
                    candleSeriesRef.current.setMarkers([]);
                }
            }
        }

        // --- 2. PANES (Sub Charts) ---
        activePanes.forEach(paneId => {
            const chart = paneInstances.current[paneId];
            if (!chart) return;

            const config = PANE_INDICATORS.find(p => p.id === paneId);
            if (!config) return;

            config.keys.forEach(key => {
                const lineData = lines[key];
                if (lineData && lineData.length > 0) {
                    if (!paneSeriesRefs.current[paneId][key]) {
                        // Decide series type (Line or Histogram for MACD/Volume, usually Line for osc)
                        const isHistogram = key.includes('hist') || key.includes('volume');
                        const seriesType = isHistogram ? HistogramSeries : LineSeries;

                        const series = chart.addSeries(seriesType, {
                            color: INDICATOR_COLORS[key] || '#fff',
                            lineWidth: 1,
                            crosshairMarkerVisible: true,
                        });
                        paneSeriesRefs.current[paneId][key] = series;

                        // Add horizontal levels for RSI/Stoch
                        if (paneId === 'rsi') {
                            series.createPriceLine({ price: 70, color: '#ef4444', lineWidth: 1, lineStyle: 2, axisLabelVisible: false });
                            series.createPriceLine({ price: 30, color: '#22c55e', lineWidth: 1, lineStyle: 2, axisLabelVisible: false });
                        }
                        if (paneId === 'stoch') {
                            series.createPriceLine({ price: 80, color: '#ef4444', lineWidth: 1, lineStyle: 2, axisLabelVisible: false });
                            series.createPriceLine({ price: 20, color: '#22c55e', lineWidth: 1, lineStyle: 2, axisLabelVisible: false });
                        }
                    }
                    paneSeriesRefs.current[paneId][key].setData(lineData);
                }
            });

            // Re-fit pane content once data is loaded
            chart.timeScale().fitContent();
        });

    }, [indicatorData, activeIndicators, isChartReady, activePanes]);

    return (
        <div ref={chartContainerRef} className="chart-wrapper w-full flex flex-col bg-gray-800 relative rounded-lg overflow-hidden border border-gray-700 select-none" style={{ height: '600px' }}>
            {/* Toolbar */}
            {/* Toolbar - CSS handles positioning */}
            <DrawingToolbar
                activeTool={activeTool}
                onToolSelect={setActiveTool}
                onDeleteSelected={deleteSelected}
                onClearAll={clearAllDrawings}
                onClearByType={clearDrawingsByType}
                drawingsByType={getDrawingsCountByType()} // Function call
                hasSelection={!!selectedDrawing}
                drawingsCount={drawings.length}
                magnetMode={magnetMode}
                onMagnetToggle={() => setMagnetMode(!magnetMode)}
            />

            {/* Main Chart */}
            <div className="relative w-full flex-grow" style={{ minHeight: '300px' }}>
                <div ref={mainChartRef} className="w-full h-full" />
                {/* Drawing Overlay */}
                {isChartReady && mainChartInstance.current && candleSeriesRef.current && (
                    <DrawingCanvas
                        containerRef={mainChartRef}
                        chartRef={mainChartInstance}
                        candleSeriesRef={candleSeriesRef}
                        candleData={candleData}

                        // Hook Props
                        drawings={drawings}
                        currentDrawing={currentDrawing}
                        selectedDrawing={selectedDrawing}
                        activeTool={activeTool}
                        isDrawing={isDrawing}
                        magnetMode={magnetMode}

                        // Handlers
                        onStartDrawing={startDrawing}
                        onUpdateDrawing={updateCurrentDrawing}
                        onCompleteDrawing={completeDrawing}
                        onAddPoint={addPointToDrawing}
                        onSelectDrawing={selectDrawing}
                        onDeleteDrawing={deleteDrawing} // Direct deletion or deleteSelected? deleteDrawing(id) passed to canvas

                        // Drag & Magnet Props
                        dragState={dragState}
                        onStartDrag={startDrag}
                        onUpdateDraggedPoint={updateDraggedPoint}
                        onEndDrag={endDrag}
                        hoveredHandle={hoveredHandle}
                        onSetHoveredHandle={setHoveredHandle}
                        magnetThreshold={MAGNET_THRESHOLD}
                    />
                )}
                {/* Status Bar */}
                <div className="absolute top-2 left-2 px-2 py-1 bg-black/50 text-xs text-white z-20 pointer-events-none rounded flex gap-2 ml-12 lg:ml-0">
                    <span>{candleData?.length ? `Last: ${candleData[candleData.length - 1].close}` : 'No Data'}</span>
                </div>
            </div>

            {/* Indicator Panes */}
            {activePanes.map(paneId => (
                <div key={paneId} className="w-full relative border-t border-gray-700" style={{ height: '120px', minHeight: '120px' }}>
                    <div className="absolute top-1 left-1 z-10 text-xs text-gray-400 bg-black/30 px-1 rounded">
                        {PANE_INDICATORS.find(p => p.id === paneId)?.label}
                    </div>
                    <div
                        ref={el => {
                            if (el) paneRefs.current[paneId] = el;
                            else delete paneRefs.current[paneId];
                        }}
                        className="w-full h-full"
                    />
                </div>
            ))}
        </div>
    );
};
