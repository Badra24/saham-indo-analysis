import { useState, useEffect, useCallback } from 'react';
import './ConvictionPanel.css';
import { API_BASE_URL } from '../config';
import AlphaVScoringPanel from './AlphaVScoringPanel';

/**
 * ConvictionPanel - Remora-Quant Trading Dashboard for IDX
 * 
 * Tabs:
 * - Alpha-V: Hybrid scoring system (F: 30%, Q: 20%, S: 50%) - NEW
 * - Confluence: Combined score from Order Flow + Technical + Bandarmology
 * - Looping: Current phase (Scout/Confirm/Attack) based on Hengky methodology
 * - Risk: Position sizing with 30-30-40 pyramiding rule
 * - Setup: Manual S/R and bias input
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
                    <button
                        className={`tab-btn ${activeTab === 'setup' ? 'active' : ''}`}
                        onClick={() => setActiveTab('setup')}
                        title="Trading Journal & Thesis"
                    >Journal / Setup</button>
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
                {activeTab === 'setup' && (
                    <SetupInput symbol={symbol} />
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

function SetupInput({ symbol }) {
    const [bias, setBias] = useState('neutral');
    const [biasStrength, setBiasStrength] = useState(50);
    const [supportLevel, setSupportLevel] = useState('');
    const [resistanceLevel, setResistanceLevel] = useState('');
    const [notes, setNotes] = useState('');
    const [saved, setSaved] = useState(false);

    const saveSetup = () => {
        // In a real app, this would save to backend/localStorage
        console.log('Setup saved:', { symbol, bias, biasStrength, supportLevel, resistanceLevel, notes });
        setSaved(true);
        setTimeout(() => setSaved(false), 2000);
    };

    return (
        <div className="setup-input">
            <div className="setup-header">
                <span className="setup-icon">📝</span>
                <span>Trading Journal - {symbol}</span>
            </div>
            <p className="setup-desc">
                Plan your trade before execution. Define your thesis, levels, and bias.
            </p>

            <div className="setup-form">
                <div className="form-section">
                    <label>Market Bias (Thesis)</label>
                    <div className="bias-buttons">
                        {['bullish', 'neutral', 'bearish'].map(b => (
                            <button
                                key={b}
                                className={`bias-btn ${bias === b ? 'active ' + b : ''}`}
                                onClick={() => setBias(b)}
                            >
                                {b === 'bullish' ? '🟢' : b === 'bearish' ? '🔴' : '⚪'} {b}
                            </button>
                        ))}
                    </div>
                    <div className="strength-slider">
                        <label>Conviction: {biasStrength}%</label>
                        <input
                            type="range"
                            min="0"
                            max="100"
                            value={biasStrength}
                            onChange={(e) => setBiasStrength(parseInt(e.target.value))}
                        />
                    </div>
                </div>

                <div className="form-section levels">
                    <label>Key Levels</label>
                    <div className="levels-grid">
                        <div className="level-input">
                            <span className="level-label">Support</span>
                            <input
                                type="number"
                                placeholder="Rp"
                                value={supportLevel}
                                onChange={(e) => setSupportLevel(e.target.value)}
                            />
                        </div>
                        <div className="level-input">
                            <span className="level-label">Resistance</span>
                            <input
                                type="number"
                                placeholder="Rp"
                                value={resistanceLevel}
                                onChange={(e) => setResistanceLevel(e.target.value)}
                            />
                        </div>
                    </div>
                </div>

                <div className="form-section">
                    <label>Trading Plan / Notes</label>
                    <textarea
                        placeholder="Why are you taking this trade? What is your invalidation point?"
                        value={notes}
                        onChange={(e) => setNotes(e.target.value)}
                        rows={3}
                    />
                </div>

                <button className="save-setup-btn" onClick={saveSetup}>
                    {saved ? '✅ Saved!' : '💾 Save Journal'}
                </button>
            </div>
        </div>
    );
}

// ============================================================================
// DEEP ANALYSIS VIEW (Swarm + ML) - Phase 18 Integration
// ============================================================================

function DeepAnalysisView({ symbol }) {
    const [status, setStatus] = useState('IDLE'); // IDLE, LOADING, DONE, ERROR
    const [swarmResult, setSwarmResult] = useState(null);
    const [forecastResult, setForecastResult] = useState(null);

    const runScan = async () => {
        setStatus('LOADING');
        try {
            // Run parallel requests
            // FIXED: Added /api/v1 prefix because endpoints are mounted there
            const [swarmRes, forecastRes] = await Promise.all([
                fetch(`${API_BASE_URL}/api/v1/adk/swarm-analysis/${symbol}`, { method: 'POST' }),
                fetch(`${API_BASE_URL}/api/v1/ml/forecast/${symbol}`)
            ]);

            if (swarmRes.ok && forecastRes.ok) {
                const sData = await swarmRes.json();
                const fData = await forecastRes.json();
                setSwarmResult(sData);
                setForecastResult(fData);
                setStatus('DONE');
            } else {
                console.error("Swarm Status:", swarmRes.status, "Forecast Status:", forecastRes.status);
                setStatus('ERROR');
            }
        } catch (e) {
            console.error(e);
            setStatus('ERROR');
        }
    };

    if (status === 'IDLE') {
        return (
            <div className="flex flex-col items-center justify-center p-8 text-center space-y-4">
                <div className="p-4 bg-brand-accent/10 rounded-full animate-pulse">
                    <span className="text-4xl">🧠</span>
                </div>
                <div>
                    <h3 className="text-lg font-bold text-white mb-2">Deep AI Analysis</h3>
                    <p className="text-sm text-gray-400 max-w-xs mx-auto mb-6">
                        Trigger the Multi-Agent Swarm and Predictive ML Engine.
                        This takes 5-10 seconds.
                    </p>
                </div>
                <button
                    onClick={runScan}
                    className="px-6 py-3 bg-brand-accent hover:bg-brand-accent/80 text-white font-bold rounded-lg transition-all flex items-center gap-2"
                >
                    <span>🚀 Run Deep Scan</span>
                </button>
            </div>
        );
    }

    if (status === 'LOADING') {
        return (
            <div className="flex flex-col items-center justify-center p-12 text-center">
                <div className="w-12 h-12 border-4 border-brand-accent border-t-transparent rounded-full animate-spin mb-4"></div>
                <h3 className="text-white font-bold animate-pulse">Swarm Activated...</h3>
                <p className="text-xs text-gray-400 mt-2">Agents are debating: Quant, Risk, Bandar</p>
            </div>
        );
    }

    if (status === 'ERROR') {
        return (
            <div className="p-8 text-center">
                <h3 className="text-red-400 font-bold mb-2">Analysis Failed</h3>
                <button onClick={runScan} className="text-sm underline text-gray-400">Retry</button>
            </div>
        );
    }

    // DONE STATE
    const probability = forecastResult?.forecast?.probability * 100 || 50;
    const isBullish = forecastResult?.forecast?.prediction === 'UP';

    // Safety check for swarm output
    const verdict = swarmResult?.decision || "UNKNOWN";
    const verdictColor = verdict.includes('BUY') ? 'text-green-400' : verdict.includes('AVOID') || verdict.includes('NO TRADE') ? 'text-red-400' : 'text-yellow-400';

    return (
        <div className="space-y-4 p-2 animate-in fade-in slide-in-from-bottom-4 duration-500">
            {/* 1. ML Forecast Card */}
            {forecastResult?.forecast && (
                <div className="glass-card p-4 border border-white/10 rounded-lg bg-gradient-to-br from-white/5 to-transparent">
                    <div className="flex justify-between items-start mb-4">
                        <div className="flex items-center gap-2">
                            <span className="text-xl">🔮</span>
                            <div>
                                <h4 className="font-bold text-sm text-gray-200">AI Trend Forecast</h4>
                                <span className="text-[10px] text-gray-500 font-mono">Model: {forecastResult.forecast.model}</span>
                            </div>
                        </div>
                        <span className={`px-2 py-1 rounded text-[10px] font-bold border ${isBullish
                                ? 'bg-green-500/10 border-green-500/30 text-green-400'
                                : 'bg-red-500/10 border-red-500/30 text-red-400'
                            }`}>
                            {forecastResult.forecast.confidence}
                        </span>
                    </div>

                    <div className="flex items-center justify-between mb-2">
                        <span className={`text-3xl font-black tracking-tighter ${isBullish ? 'text-green-400' : 'text-red-400'}`}>
                            {forecastResult.forecast.prediction}
                        </span>
                        <span className="text-xs text-gray-400">{probability.toFixed(0)}% Probability</span>
                    </div>

                    {/* Probability Bar */}
                    <div className="h-2 bg-gray-700/50 rounded-full overflow-hidden mb-2">
                        <div
                            className={`h-full transition-all duration-1000 ${isBullish ? 'bg-green-500' : 'bg-red-500'}`}
                            style={{ width: `${probability}%` }}
                        ></div>
                    </div>
                    <div className="flex justify-between text-[10px] text-gray-500">
                        <span>Bearish</span>
                        <span>Neutral</span>
                        <span>Bullish</span>
                    </div>
                </div>
            )}

            {/* 2. Swarm Report */}
            {swarmResult && (
                <div className="glass-card border border-white/10 rounded-lg overflow-hidden">
                    {/* Header */}
                    <div className="p-4 border-b border-white/10 bg-white/5 flex justify-between items-center bg-grid-pattern">
                        <div>
                            <div className="text-[10px] text-brand-accent font-bold uppercase tracking-widest mb-1">Swarm Consensus</div>
                            <div className={`text-2xl font-black ${verdictColor}`}>
                                {verdict}
                            </div>
                        </div>
                        <div className="text-4xl opacity-20">🤖</div>
                    </div>

                    <div className="divide-y divide-white/5 bg-black/20">
                        {/* Quant Agent */}
                        <div className="p-3 hover:bg-white/5 transition-colors">
                            <div className="flex items-start gap-3">
                                <div className="p-2 bg-blue-500/10 rounded-lg text-blue-400">💰</div>
                                <div className="flex-1">
                                    <div className="flex justify-between mb-1">
                                        <span className="text-xs font-bold text-gray-300">Quant Analyst</span>
                                        <span className="text-[10px] px-1.5 py-0.5 bg-blue-500/20 text-blue-300 rounded">Fundamental</span>
                                    </div>
                                    <p className="text-sm text-gray-400 leading-snug">{swarmResult.details.quant.analysis}</p>
                                </div>
                            </div>
                        </div>

                        {/* Bandar Detective */}
                        <div className="p-3 hover:bg-white/5 transition-colors">
                            <div className="flex items-start gap-3">
                                <div className="p-2 bg-purple-500/10 rounded-lg text-purple-400">🕵️</div>
                                <div className="flex-1">
                                    <div className="flex justify-between mb-1">
                                        <span className="text-xs font-bold text-gray-300">Bandar Detective</span>
                                        <span className="text-[10px] px-1.5 py-0.5 bg-purple-500/20 text-purple-300 rounded">Flow</span>
                                    </div>
                                    <p className="text-sm text-gray-400 leading-snug">{swarmResult.details.bandar.analysis}</p>
                                </div>
                            </div>
                        </div>

                        {/* Risk Officer */}
                        <div className="p-3 hover:bg-white/5 transition-colors">
                            <div className="flex items-start gap-3">
                                <div className="p-2 bg-orange-500/10 rounded-lg text-orange-400">🛡️</div>
                                <div className="flex-1">
                                    <div className="flex justify-between mb-1">
                                        <span className="text-xs font-bold text-gray-300">Risk Officer</span>
                                        <span className="text-[10px] px-1.5 py-0.5 bg-orange-500/20 text-orange-300 rounded">Safety</span>
                                    </div>
                                    <p className="text-sm text-gray-400 leading-snug">
                                        {swarmResult.details.risk.warning ? (
                                            <span className="text-red-400 font-bold">{swarmResult.details.risk.warning}</span>
                                        ) : "Checks Passed. "}
                                        <span className="block mt-1 text-xs text-gray-500">
                                            Max Allocation Limit: <span className="text-white font-mono">{swarmResult.details.risk.max_allocation}</span>
                                        </span>
                                    </p>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
