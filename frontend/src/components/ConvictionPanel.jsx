import { useState, useEffect, useCallback } from 'react';
import './ConvictionPanel.css';
import { API_BASE_URL } from '../config';
import AlphaVScoringPanel from './AlphaVScoringPanel';
import ADKChatPanel from './ADKChatPanel';

/**
 * ConvictionPanel - Remora-Quant Trading Dashboard for IDX
 * 
 * Tabs:
 * - Alpha-V: Hybrid scoring system (F: 30%, Q: 20%, S: 50%) - NEW
 * - Confluence: Combined score from Order Flow + Technical + Bandarmology
 * - Looping: Current phase (Scout/Confirm/Attack) based on Hengky methodology
 * - Risk: Position sizing with 30-30-40 pyramiding rule
 */
export default function ConvictionPanel({ symbol = 'BBCA', orderFlow, indicatorData, bandarmologyData }) {
    const [activeTab, setActiveTab] = useState('alpha-v');
    const [confluenceData, setConfluenceData] = useState(null);

    // Calculate confluence score from available data
    const calculateConfluence = useCallback(() => {
        if (!orderFlow && !indicatorData && !bandarmologyData) return null;

        let score = 50; // Neutral base
        let signals = [];

        let subscores = {
            orderFlow: 0, // Disabled
            technical: 50,
            bandarmology: 50
        };

        // 1. Order Flow scoring (REMOVED - Dummy Data)

        // 2. Technical scoring (40%)
        if (indicatorData?.indicators) {
            let techScore = 50;
            const rsi = indicatorData.indicators.rsi;
            if (rsi < 30) { techScore += 15; signals.push({ name: 'RSI Oversold', value: rsi.toFixed(1), bullish: true }); }
            else if (rsi > 70) { techScore -= 15; signals.push({ name: 'RSI Overbought', value: rsi.toFixed(1), bullish: false }); }

            const macd = indicatorData.indicators.macd;
            if (macd > 0) { techScore += 10; signals.push({ name: 'MACD', value: 'Bullish', bullish: true }); }
            else if (macd < 0) { techScore -= 10; signals.push({ name: 'MACD', value: 'Bearish', bullish: false }); }

            // VPVR Check (Real Engine)
            if (indicatorData.indicator_lines?.vpvr_poc?.length > 0) {
                const lastPoc = indicatorData.indicator_lines.vpvr_poc[indicatorData.indicator_lines.vpvr_poc.length - 1].value;
                const currentPrice = indicatorData.historical_prices[indicatorData.historical_prices.length - 1]?.close;
                if (currentPrice > lastPoc) {
                    techScore += 5;
                    signals.push({ name: 'Price > POC', value: lastPoc.toFixed(0), bullish: true });
                } else {
                    techScore -= 5;
                    signals.push({ name: 'Price < POC', value: lastPoc.toFixed(0), bullish: false });
                }
            }

            subscores.technical = Math.max(0, Math.min(100, techScore));
        }

        // 3. Bandarmology Scoring (60%) - REAL ENGINE
        if (bandarmologyData) {
            let bandarScore = 50;
            const status = bandarmologyData.status || "NEUTRAL";
            const bcr = bandarmologyData.concentration_ratio || 0;

            if (status === 'BIG_ACCUMULATION') { bandarScore += 30; signals.push({ name: 'Big Accumulation', value: `BCR ${bcr.toFixed(2)}`, bullish: true }); }
            else if (status === 'ACCUMULATION') { bandarScore += 15; signals.push({ name: 'Accumulation', value: `BCR ${bcr.toFixed(2)}`, bullish: true }); }
            else if (status === 'BIG_DISTRIBUTION') { bandarScore -= 30; signals.push({ name: 'Big Distribution', value: `BCR ${bcr.toFixed(2)}`, bullish: false }); }
            else if (status === 'DISTRIBUTION') { bandarScore -= 15; signals.push({ name: 'Distribution', value: `BCR ${bcr.toFixed(2)}`, bullish: false }); }

            if (bandarmologyData.dominant_player === 'INSTITUTION') {
                bandarScore += 5;
            } else if (bandarmologyData.dominant_player === 'RETAIL') {
                bandarScore -= 5;
                if (status.includes('ACCUMULATION')) {
                    signals.push({ name: 'Retail Disguise?', value: 'Suspicious', bullish: false });
                }
            }

            subscores.bandarmology = Math.max(0, Math.min(100, bandarScore));
        }

        // 4. ML Insight (Bonus)
        if (indicatorData?.ml_analysis && indicatorData.ml_analysis.is_anomaly) {
            signals.push({
                name: 'ML Anomaly',
                value: indicatorData.ml_analysis.description,
                bullish: subscores.bandarmology > 50 // Consider bullish if whales are accumulating
            });
        }

        // Final Weighted Score
        // 40% Technical, 60% Bandarmology
        score = (subscores.technical * 0.4) + (subscores.bandarmology * 0.6);
        score = Math.round(score);

        // Determine signal
        let signalType = 'HOLD';
        if (score >= 70) signalType = 'BUY';
        if (score >= 80) signalType = 'STRONG BUY';
        if (score <= 30) signalType = 'SELL';
        if (score <= 20) signalType = 'STRONG SELL';

        return {
            score,
            signal: signalType,
            signals,
            breakdown: subscores,
            ml_analysis: indicatorData?.ml_analysis
        };
    }, [orderFlow, indicatorData, bandarmologyData]);

    useEffect(() => {
        setConfluenceData(calculateConfluence());
    }, [calculateConfluence]);

    return (
        <div className="conviction-panel panel">
            <div className="panel-header">
                <h3>🎯 Trading Conviction</h3>
                <div className="conviction-tabs">
                    <button
                        className={`tab-btn ${activeTab === 'alpha-v' ? 'active' : ''}`}
                        onClick={() => setActiveTab('alpha-v')}
                    >Alpha-V</button>
                    <button
                        className={`tab-btn ${activeTab === 'confluence' ? 'active' : ''}`}
                        onClick={() => setActiveTab('confluence')}
                    >Score</button>
                    <button
                        className={`tab-btn ${activeTab === 'deep-ai' ? 'active' : ''}`}
                        onClick={() => setActiveTab('deep-ai')}
                        title="AI Swarm & ML Forecast"
                    >🧠 Deep AI</button>
                    <button
                        className={`tab-btn ${activeTab === 'looping' ? 'active' : ''}`}
                        onClick={() => setActiveTab('looping')}
                    >Looping</button>
                    <button
                        className={`tab-btn ${activeTab === 'risk' ? 'active' : ''}`}
                        onClick={() => setActiveTab('risk')}
                    >Risk</button>
                </div>
            </div>

            <div className="panel-content">
                {activeTab === 'alpha-v' && (
                    <AlphaVScoringPanel symbol={symbol} />
                )}
                {activeTab === 'confluence' && (
                    <ConfluenceScore data={confluenceData} symbol={symbol} />
                )}
                {activeTab === 'deep-ai' && (
                    <DeepAnalysisView symbol={symbol} />
                )}
                {activeTab === 'looping' && (
                    <LoopingPhase data={confluenceData} symbol={symbol} />
                )}
                {activeTab === 'risk' && (
                    <PositionSizing symbol={symbol} confluenceScore={confluenceData?.score || 50} />
                )}
            </div>
        </div>
    );
}

// ============================================================================
// CONFLUENCE SCORE
// ============================================================================

function ConfluenceScore({ data, symbol }) {
    if (!data) {
        return (
            <div className="confluence-empty">
                <p>📊 Load data for {symbol} to see confluence score</p>
            </div>
        );
    }

    const scoreColor = data.score >= 70 ? '#22c55e' : data.score <= 30 ? '#ef4444' : '#eab308';
    const signalEmoji = {
        'STRONG BUY': '🟢🟢',
        'BUY': '🟢',
        'HOLD': '🟡',
        'SELL': '🔴',
        'STRONG SELL': '🔴🔴'
    }[data.signal] || '🟡';

    return (
        <div className="confluence-score">
            <div className="score-circle-container">
                <div className="score-circle" style={{ '--score': data.score, '--color': scoreColor }}>
                    <div className="score-inner">
                        <span className="score-value">{Math.round(data.score)}</span>
                        <span className="score-label">/ 100</span>
                    </div>
                </div>
                <div className="score-signal">
                    <span className="signal-emoji">{signalEmoji}</span>
                    <span className="signal-text">{data.signal}</span>
                </div>
            </div>

            {/* ML Insight Alert */}
            {data.ml_analysis?.is_anomaly && (
                <div className="ml-alert">
                    <div className="ml-badge">🤖 ML Insight</div>
                    <div className="ml-desc">{data.ml_analysis.description}</div>
                </div>
            )}

            <div className="score-breakdown">
                <h4>Score Breakdown</h4>

                <div className="breakdown-item">
                    <div className="breakdown-label">
                        <span>📈 Technical</span>
                        <span className="breakdown-weight">40%</span>
                    </div>
                    <div className="breakdown-bar">
                        <div className="breakdown-fill technical" style={{ width: `${data.breakdown.technical}%` }} />
                    </div>
                    <span className="breakdown-value">{data.breakdown.technical}</span>
                </div>
                <div className="breakdown-item">
                    <div className="breakdown-label">
                        <span>🔍 Bandarmology</span>
                        <span className="breakdown-weight">60%</span>
                    </div>
                    <div className="breakdown-bar">
                        <div className="breakdown-fill bandarmology" style={{ width: `${data.breakdown.bandarmology}%` }} />
                    </div>
                    <span className="breakdown-value">{data.breakdown.bandarmology}</span>
                </div>
            </div>

            {data.signals?.length > 0 && (
                <div className="signal-list">
                    <h4>Active Signals</h4>
                    {data.signals.map((s, i) => (
                        <div key={i} className={`signal-item ${s.bullish ? 'bullish' : 'bearish'}`}>
                            <span>{s.bullish ? '🟢' : '🔴'} {s.name}</span>
                            <span>{s.value}</span>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}

// ============================================================================
// LOOPING PHASE (Hengky Methodology)
// ============================================================================

function LoopingPhase({ data, symbol }) {
    // Determine phase based on confluence score
    let phase = 'WAIT';
    let phaseDescription = '';
    let allocation = { scout: 0, confirm: 0, attack: 0 };

    if (data?.score >= 70) {
        phase = 'SCOUT';
        phaseDescription = 'Initial position - 30% allocation. Wait for confirmation.';
        allocation = { scout: 30, confirm: 0, attack: 0 };
    }
    if (data?.score >= 80) {
        phase = 'CONFIRM';
        phaseDescription = 'Add 30% more. Total 60% invested.';
        allocation = { scout: 30, confirm: 30, attack: 0 };
    }
    if (data?.score >= 90) {
        phase = 'ATTACK';
        phaseDescription = 'All in! Add final 40%. Total 100% invested.';
        allocation = { scout: 30, confirm: 30, attack: 40 };
    }
    if (data?.score < 70) {
        phase = 'WAIT';
        phaseDescription = 'Confluence too low. Wait for better setup.';
    }

    const phaseColors = {
        'WAIT': '#6b7280',
        'SCOUT': '#eab308',
        'CONFIRM': '#3b82f6',
        'ATTACK': '#22c55e'
    };

    return (
        <div className="looping-phase">
            <div className="phase-current" style={{ borderColor: phaseColors[phase] }}>
                <span className="phase-icon">
                    {phase === 'WAIT' ? '⏸️' : phase === 'SCOUT' ? '🔭' : phase === 'CONFIRM' ? '✅' : '⚔️'}
                </span>
                <div className="phase-info">
                    <span className="phase-name">{phase}</span>
                    <span className="phase-score">Score: {data?.score || '-'}/100</span>
                </div>
            </div>

            <div className="phase-description">
                <p>{phaseDescription}</p>
            </div>

            <div className="pyramid-visual">
                <h4>Piramida 30-30-40</h4>
                <div className="pyramid-bars">
                    <div className="pyramid-bar scout" style={{ width: `${allocation.scout}%` }}>
                        {allocation.scout > 0 && <span>Scout 30%</span>}
                    </div>
                    <div className="pyramid-bar confirm" style={{ width: `${allocation.confirm}%` }}>
                        {allocation.confirm > 0 && <span>Confirm 30%</span>}
                    </div>
                    <div className="pyramid-bar attack" style={{ width: `${allocation.attack}%` }}>
                        {allocation.attack > 0 && <span>Attack 40%</span>}
                    </div>
                </div>
                <div className="pyramid-total">
                    Total Allocation: {allocation.scout + allocation.confirm + allocation.attack}%
                </div>
            </div>

            <div className="looping-rules">
                <h4>📜 Looping Rules</h4>
                <ul>
                    <li>🔭 <strong>Scout (30%)</strong> - Confluence ≥ 70</li>
                    <li>✅ <strong>Confirm (30%)</strong> - Confluence ≥ 80</li>
                    <li>⚔️ <strong>Attack (40%)</strong> - Confluence ≥ 90</li>
                    <li>🛡️ Minimal R:R = 1:2</li>
                    <li>⚠️ NO TRADE jika confluence &lt; 70</li>
                </ul>
            </div>
        </div>
    );
}

// ============================================================================
// POSITION SIZING (30-30-40 Rule + Risk Management)
// ============================================================================

function PositionSizing({ symbol, confluenceScore }) {
    const [accountBalance, setAccountBalance] = useState(100000000); // 100 juta Rupiah
    const [entryPrice, setEntryPrice] = useState('');
    const [stopLoss, setStopLoss] = useState('');
    const [takeProfit, setTakeProfit] = useState('');
    const [maxRisk, setMaxRisk] = useState(1.0);

    // Fee Config
    const [feeBuy, setFeeBuy] = useState(0.15);
    const [feeSell, setFeeSell] = useState(0.25);
    const [useConfluence, setUseConfluence] = useState(true);

    const [result, setResult] = useState(null);

    const calculate = () => {
        if (!entryPrice || !stopLoss) return;

        const entry = parseFloat(entryPrice);
        const sl = parseFloat(stopLoss);
        const tp = takeProfit ? parseFloat(takeProfit) : null;
        const balance = parseFloat(accountBalance);
        const riskPercent = parseFloat(maxRisk) / 100;

        // 1. Basic Risk per trade
        const riskAmount = balance * riskPercent;

        // 2. Stop Distance & Position Sizing
        const stopDistance = Math.abs(entry - sl);
        const stopDistancePercent = (stopDistance / entry) * 100;

        // Lots calculation (Standard Risk)
        const sharesCanBuy = Math.floor(riskAmount / stopDistance);
        let lotsCanBuy = Math.floor(sharesCanBuy / 100);

        // 3. Pyramiding Logic (30-30-40) or Manual Override
        let pyramidPhase = 'WAIT';
        let pyramidAllocation = 0;

        if (useConfluence) {
            if (confluenceScore >= 90) { pyramidPhase = 'ATTACK'; pyramidAllocation = 100; }
            else if (confluenceScore >= 80) { pyramidPhase = 'CONFIRM'; pyramidAllocation = 60; }
            else if (confluenceScore >= 70) { pyramidPhase = 'SCOUT'; pyramidAllocation = 30; }
        } else {
            pyramidPhase = 'MANUAL';
            pyramidAllocation = 100;
        }

        // Adjust lots based on phase (for display only)
        const adjustedLots = Math.floor(lotsCanBuy * (pyramidAllocation / 100));
        const adjustedShares = adjustedLots * 100;
        const adjustedValue = adjustedShares * entry;

        // For Scenario Analysis, ALWAYS use MAX LOTS (lotsCanBuy) regardless of phase
        // This ensures users always see meaningful P/L calculations
        const maxShares = lotsCanBuy * 100;
        const grossValue = maxShares * entry;

        // 4. Broker Fee Calculation (based on max position)
        const buyCost = grossValue * (feeBuy / 100);
        const sellCostBase = grossValue * (feeSell / 100);

        // Break Even Point (Price where Net P/L = 0)
        const breakEvenPrice = (entry * (1 + feeBuy / 100)) / (1 - feeSell / 100);

        // 5. Scenario Analysis (ALWAYS uses MAX LOTS for clarity)
        let scenario = {
            tp_net: 0,
            sl_net: 0,
            tp_percent: 0,
            sl_percent: 0
        };

        if (grossValue > 0) {
            if (tp) {
                const sellValueTP = maxShares * tp;
                const feeSellTP = sellValueTP * (feeSell / 100);
                scenario.tp_net = sellValueTP - grossValue - buyCost - feeSellTP;
                scenario.tp_percent = (scenario.tp_net / grossValue) * 100;
            }

            // SL Scenario
            const sellValueSL = maxShares * sl;
            const feeSellSL = sellValueSL * (feeSell / 100);
            scenario.sl_net = sellValueSL - grossValue - buyCost - feeSellSL;
            scenario.sl_percent = (scenario.sl_net / grossValue) * 100;
        }

        // R:R Ratio (Gross)
        let rrRatio = null;
        if (tp) {
            const profitDistance = Math.abs(tp - entry);
            rrRatio = profitDistance / stopDistance;
        }

        setResult({
            riskAmount,
            stopDistancePercent,
            lotsCanBuy, // Max possible lots for this risk
            adjustedLots, // AI-recommended lots based on phase
            positionValue: grossValue, // Max position value for scenario
            adjustedValue, // AI-recommended position value
            breakEvenPrice,
            fees: { buy: buyCost, est_sell: sellCostBase },
            scenario,
            rrRatio,
            pyramidPhase,
            pyramidAllocation,
            warnings: rrRatio && rrRatio < 2 ? ['R:R ratio below 2:1 minimum'] : []
        });
    };

    return (
        <div className="position-sizing">
            <div className="sizing-header">
                <span className="sizing-icon">📐</span>
                <span>Advanced Calculator (Risk & Fees)</span>
            </div>

            <div className="sizing-form">
                {/* Account & Fee Settings Row */}
                <div className="form-row-group">
                    <div className="form-group">
                        <label>Balance (Rp)</label>
                        <input
                            type="number"
                            value={accountBalance}
                            onChange={(e) => setAccountBalance(e.target.value)}
                        />
                    </div>
                    <div className="form-group small">
                        <label>Fee Buy (%)</label>
                        <input
                            type="number"
                            step="0.01"
                            value={feeBuy}
                            onChange={(e) => setFeeBuy(e.target.value)}
                        />
                    </div>
                    <div className="form-group small">
                        <label>Fee Sell (%)</label>
                        <input
                            type="number"
                            step="0.01"
                            value={feeSell}
                            onChange={(e) => setFeeSell(e.target.value)}
                        />
                    </div>
                </div>

                {/* Price Inputs Row */}
                <div className="form-row-group">
                    <div className="form-group">
                        <label>Entry (Rp)</label>
                        <input
                            type="number"
                            value={entryPrice}
                            onChange={(e) => setEntryPrice(e.target.value)}
                            className="input-entry"
                        />
                    </div>
                    <div className="form-group">
                        <label>Stop Loss (Rp)</label>
                        <input
                            type="number"
                            value={stopLoss}
                            onChange={(e) => setStopLoss(e.target.value)}
                            className="input-sl"
                        />
                    </div>
                    <div className="form-group">
                        <label>Take Profit</label>
                        <input
                            type="number"
                            value={takeProfit}
                            onChange={(e) => setTakeProfit(e.target.value)}
                            className="input-tp"
                        />
                    </div>
                </div>

                <div className="form-row">
                    <label>Max Risk per Trade</label>
                    <select value={maxRisk} onChange={(e) => setMaxRisk(e.target.value)}>
                        <option value="0.5">0.5% (Conservative)</option>
                        <option value="1.0">1.0% (Standard)</option>
                        <option value="1.5">1.5% (Aggressive)</option>
                        <option value="2.0">2.0% (High Risk)</option>
                        <option value="5.0">5.0% (Degen)</option>
                    </select>
                </div>

                <div className="conviction-badge">
                    <span>Phase: {result?.pyramidPhase || 'WAIT'} ({result?.pyramidAllocation || 0}%)</span>
                </div>

                <div className="form-row checkbox-row" style={{ flexDirection: 'row', alignItems: 'center', gap: '8px' }}>
                    <input
                        type="checkbox"
                        id="useConfluence"
                        checked={useConfluence}
                        onChange={(e) => setUseConfluence(e.target.checked)}
                        style={{ width: 'auto' }}
                    />
                    <label htmlFor="useConfluence" style={{ cursor: 'pointer' }}>
                        Follow AI Recommendation
                    </label>
                </div>

                <button className="calculate-btn" onClick={calculate}>
                    📊 Calculate Risk & Reward (Updated)
                </button>
            </div>

            {result && (
                <div className="sizing-result">
                    <div className="result-grid">
                        <div className="result-card main">
                            <span className="card-label">Quantity (Lots)</span>
                            <span className="card-value">{result.adjustedLots} <small>lots</small></span>
                            <span className="card-sub">{result.pyramidAllocation}% of Max</span>
                        </div>
                        <div className="result-card">
                            <span className="card-label">Position Value</span>
                            <span className="card-value">{(result.positionValue / 1000000).toFixed(1)} <small>Jt</small></span>
                        </div>
                        <div className="result-card">
                            <span className="card-label">Break Even</span>
                            <span className="card-value text-yellow-400">{Math.ceil(result.breakEvenPrice)}</span>
                            <span className="card-sub">Fees: {(result.fees.buy + result.fees.est_sell).toLocaleString('id-ID', { maximumFractionDigits: 0 })}</span>
                        </div>
                    </div>

                    <div className="scenario-analysis">
                        <h4>Scenario Analysis (Net P/L)</h4>
                        <div className="scenario-row win">
                            <span className="scenario-label">✅ TP Hit ({takeProfit})</span>
                            <span className="scenario-val text-green-400">
                                +{Math.round(result.scenario.tp_net).toLocaleString('id-ID')}
                            </span>
                            <span className="scenario-pct text-green-400">
                                ({result.scenario.tp_percent.toFixed(2)}%)
                            </span>
                        </div>
                        <div className="scenario-row loss">
                            <span className="scenario-label">❌ SL Hit ({stopLoss})</span>
                            <span className="scenario-val text-red-400">
                                {Math.round(result.scenario.sl_net).toLocaleString('id-ID')}
                            </span>
                            <span className="scenario-pct text-red-400">
                                ({result.scenario.sl_percent.toFixed(2)}%)
                            </span>
                        </div>
                        {result.rrRatio && (
                            <div className="scenario-row rr">
                                <span className="scenario-label">⚖️ Risk:Reward</span>
                                <span className={`scenario-val ${result.rrRatio >= 2 ? 'text-green-400' : 'text-yellow-400'}`}>
                                    1 : {result.rrRatio.toFixed(2)}
                                </span>
                            </div>
                        )}
                    </div>

                    {result.warnings?.length > 0 && (
                        <div className="warnings">
                            {result.warnings.map((w, i) => (
                                <div key={i} className="warning-item">⚠️ {w}</div>
                            ))}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}

// ============================================================================
// SETUP INPUT (Support/Resistance & Bias)
// ============================================================================


// ============================================================================
// DEEP ANALYSIS VIEW (Swarm + ML) - Phase 18 Integration
// ============================================================================

// DEEP ANALYSIS VIEW (ADK Integration)
// ============================================================================

function DeepAnalysisView({ symbol }) {
    return (
        <div className="deep-analysis-container p-3 bg-gray-900/50 rounded-lg border border-white/5">
            <div className="mb-3 flex items-center gap-2">
                <span className="text-xl">🧠</span>
                <div>
                    <h3 className="font-bold text-sm">Remora Deep AI</h3>
                    <p className="text-xs text-gray-400">Context-Aware Swarm Intelligence</p>
                </div>
            </div>

            <ADKChatPanel
                symbol={symbol}
                height="400px"
                onStatusChange={(s) => console.log("AI Status:", s)}
            />
        </div>
    );
}
// End of DeepAnalysisView
