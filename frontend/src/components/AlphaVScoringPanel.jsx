import { useState, useEffect } from 'react';
import { TrendingUp, TrendingDown, AlertTriangle, Target, Activity, DollarSign, BarChart3, RefreshCw } from 'lucide-react';
import { API_BASE_URL } from '../config';
import FileUploadPanel from './FileUploadPanel';
import './AlphaVScoringPanel.css';

/**
 * AlphaVScoringPanel - Alpha-V Hybrid Scoring System visualization
 * 
 * Displays:
 * - Circular score gauge (0-100)
 * - Grade indicator (A-E)
 * - Component breakdown (F, Q, S)
 * - Strategy recommendation
 * - Data availability status
 */
const AlphaVScoringPanel = ({ symbol, onScoreChange }) => {
    const [score, setScore] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [showUpload, setShowUpload] = useState(false);

    // Reset state when symbol changes to prevent stale data
    useEffect(() => {
        setScore(null);
        setError(null);
        // Do NOT reset loading here, it's handled in fetchScore
    }, [symbol]);

    const fetchScore = async () => {
        if (!symbol) return;

        setLoading(true);
        setError(null);

        try {
            const response = await fetch(`${API_BASE_URL}/api/v1/alpha-v/${symbol}`);
            const data = await response.json();

            if (response.ok) {
                setScore(data);
                if (onScoreChange) {
                    onScoreChange(data);
                }
            } else {
                setError(data.detail || 'Failed to fetch score');
            }
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        setScore(null);
        setError(null);
        fetchScore();
    }, [symbol]);

    const handleUploadComplete = () => {
        setShowUpload(false);
        fetchScore(); // Refresh score with new data
    };

    const getGaugeColor = (grade) => {
        const colors = {
            A: '#00FF88',
            B: '#88FF00',
            C: '#FFCC00',
            D: '#FF8800',
            E: '#FF0044'
        };
        return colors[grade] || '#888888';
    };

    const renderGauge = () => {
        if (!score) return null;

        const totalScore = score.total_score;
        const grade = score.grade;
        const color = getGaugeColor(grade);
        const circumference = 2 * Math.PI * 45;
        const progress = (totalScore / 100) * circumference;

        return (
            <div className="score-gauge">
                <svg viewBox="0 0 100 100" className="gauge-svg">
                    {/* Background circle */}
                    <circle
                        cx="50"
                        cy="50"
                        r="45"
                        fill="none"
                        stroke="rgba(255,255,255,0.1)"
                        strokeWidth="8"
                    />
                    {/* Progress circle */}
                    <circle
                        cx="50"
                        cy="50"
                        r="45"
                        fill="none"
                        stroke={color}
                        strokeWidth="8"
                        strokeDasharray={circumference}
                        strokeDashoffset={circumference - progress}
                        strokeLinecap="round"
                        transform="rotate(-90 50 50)"
                        className="gauge-progress"
                    />
                </svg>
                <div className="gauge-center">
                    <span className="gauge-score">{Math.round(totalScore)}</span>
                    <span className="gauge-grade" style={{ color }}>{grade}</span>
                </div>
            </div>
        );
    };

    const renderSubScores = () => {
        if (!score) return null;

        const scores = [
            {
                label: 'Fundamental',
                key: 'F',
                value: score.fundamental_score,
                weight: '30%',
                icon: DollarSign,
                description: 'PER, PBV, EV/EBITDA, PCF',
                breakdown: [
                    { label: 'PER', value: score.fundamental_breakdown?.per_component || 0, max: 30 },
                    { label: 'PBV', value: score.fundamental_breakdown?.pbv_component || 0, max: 20 },
                    { label: 'EV/EBITDA', value: score.fundamental_breakdown?.ev_ebitda_component || 0, max: 20 },
                    { label: 'PCF', value: score.fundamental_breakdown?.pcf_component || 0, max: 15 },
                    { label: 'Sector Rank', value: score.fundamental_breakdown?.sectoral_component || 0, max: 15 }
                ]
            },
            {
                label: 'Quality',
                key: 'Q',
                value: score.quality_score,
                weight: '20%',
                icon: Target,
                description: 'OCF/NI ratio, DER',
                breakdown: [
                    { label: 'Cash Flow', value: score.quality_breakdown?.ocf_component || 0, max: 60 },
                    { label: 'Solvency', value: score.quality_breakdown?.der_component || 0, min: -20, max: 20 }
                ]
            },
            {
                label: 'Smart Money',
                key: 'S',
                value: score.smart_money_score,
                weight: '50%',
                icon: Activity,
                description: 'BCR, Foreign Flow',
                breakdown: [
                    { label: 'Bandar (BCR)', value: score.smart_money_breakdown?.bcr_component || 0, max: 50 },
                    { label: 'Foreign Flow', value: score.smart_money_breakdown?.foreign_flow_component || 0, max: 30 },
                    { label: 'Divergence', value: score.smart_money_breakdown?.divergence_component || 0, max: 20 }
                ]
            }
        ];

        return (
            <div className="sub-scores">
                {scores.map(({ label, key, value, weight, icon: Icon, description, breakdown }) => (
                    <div key={key} className="sub-score-item">
                        <div className="sub-score-header">
                            <Icon size={14} />
                            <span className="sub-score-label">{label}</span>
                            <span className="sub-score-weight">({weight})</span>
                        </div>
                        <div className="sub-score-bar-container">
                            <div
                                className="sub-score-bar"
                                style={{
                                    width: `${value}%`,
                                    background: value >= 60 ? 'linear-gradient(90deg, #00ff88, #88ff00)'
                                        : value >= 40 ? 'linear-gradient(90deg, #ffcc00, #ff8800)'
                                            : 'linear-gradient(90deg, #ff8800, #ff0044)'
                                }}
                            />
                        </div>
                        <div className="sub-score-value">{Math.round(value)}</div>

                        {/* Breakdown Section */}
                        <div className="sub-score-breakdown mt-2 pl-6 space-y-1">
                            {breakdown.map((item, i) => (
                                <div key={i} className="breakdown-item flex justify-between text-[10px] text-gray-500">
                                    <span className="breakdown-label">{item.label}</span>
                                    <span className={`breakdown-value font-mono ${item.value < 0 ? 'text-red-400' : 'text-gray-400'}`}>
                                        {item.value > 0 ? '+' : ''}{Math.round(item.value)}
                                        {item.max && <span className="text-gray-600">/{item.max}</span>}
                                    </span>
                                </div>
                            ))}
                        </div>
                    </div>
                ))}
            </div>
        );
    };

    const renderStrategy = () => {
        if (!score) return null;

        return (
            <div className="strategy-section">
                <div className="strategy-label">Strategy</div>
                <div className={`strategy-text grade-${score.grade?.toLowerCase()}`}>
                    {score.strategy}
                </div>
            </div>
        );
    };

    const renderDataStatus = () => {
        if (!score?.data_availability) return null;

        const { broker_data, financial_data, price_data } = score.data_availability;

        return (
            <div className="data-status">
                <div className="status-title">Data Sources</div>
                <div className="status-items">
                    <div className={`status-item ${broker_data ? 'available' : 'missing'}`}>
                        <span className="status-dot" />
                        Broker Summary
                    </div>
                    <div className={`status-item ${financial_data ? 'available' : 'missing'}`}>
                        <span className="status-dot" />
                        Financial Report
                    </div>
                    <div className={`status-item ${price_data ? 'available' : 'missing'}`}>
                        <span className="status-dot" />
                        Price Data
                    </div>
                </div>

                <div className="mt-4 flex justify-center">
                    <button
                        className="upload-data-btn w-full"
                        onClick={() => setShowUpload(!showUpload)}
                    >
                        {showUpload ? 'Hide Upload' : (!broker_data || !financial_data) ? 'Upload Missing Data' : 'Change / Update Data'}
                    </button>
                </div>
            </div >
        );
    };

    const renderConfidenceNotes = () => {
        if (!score?.confidence_notes || score.confidence_notes.length === 0) return null;

        return (
            <div className="confidence-notes">
                <div className="notes-title">Analysis Notes</div>
                <div className="notes-list">
                    {score.confidence_notes.slice(0, 5).map((note, i) => (
                        <div key={i} className="note-item">{note}</div>
                    ))}
                </div>
            </div>
        );
    };

    if (loading) {
        return (
            <div className="alpha-v-panel loading">
                <div className="loading-spinner" />
                <span>Calculating Alpha-V Score...</span>
            </div>
        );
    }

    if (error) {
        return (
            <div className="alpha-v-panel error">
                <AlertTriangle size={24} />
                <span>{error}</span>
                <button onClick={fetchScore}>Retry</button>
            </div>
        );
    }

    return (
        <div className="alpha-v-panel">
            <div className="panel-header">
                <div className="header-title">
                    <BarChart3 size={18} />
                    <span>Alpha-V Score</span>
                </div>
                <button className="refresh-btn" onClick={fetchScore} disabled={loading}>
                    <RefreshCw size={16} className={loading ? 'spinning' : ''} />
                </button>
            </div>

            <div className="panel-content">
                <div className="main-score-section">
                    {renderGauge()}
                    <div className="grade-label" style={{ color: getGaugeColor(score?.grade) }}>
                        {score?.grade_label}
                    </div>
                </div>

                {renderSubScores()}
                {renderStrategy()}
                {renderDataStatus()}

                {showUpload && (
                    <div className="upload-section">
                        {/* Only show Broker Summary upload if missing or partial */}
                        {(!score?.data_availability?.broker_data) && (
                            <FileUploadPanel
                                ticker={symbol}
                                mode="broker_summary"
                                onUploadComplete={handleUploadComplete}
                                showAsInline
                            />
                        )}

                        {/* Only show Financial Report upload if missing or partial */}
                        {(!score?.data_availability?.financial_data) && (
                            <FileUploadPanel
                                ticker={symbol}
                                mode="financial_report"
                                onUploadComplete={handleUploadComplete}
                                showAsInline
                            />
                        )}
                    </div>
                )}

                {renderConfidenceNotes()}
            </div>
        </div>
    );
};

export default AlphaVScoringPanel;
