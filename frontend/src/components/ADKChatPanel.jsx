import { useState, useEffect, useRef, useCallback } from 'react';
import './ADKChatPanel.css';

const API_BASE = 'http://localhost:8000/api';

/**
 * ADKChatPanel - AI Trading Assistant Chat Interface
 * Powered by Google ADK with Remora Commander agent
 * Supports multi-model selection (Gemini, OpenRouter)
 */
export default function ADKChatPanel({ symbol = 'BBCA', onStatusChange }) {
    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState('');
    const [loading, setLoading] = useState(false);
    const [adkStatus, setAdkStatus] = useState(null);
    const [sessionId, setSessionId] = useState(null);

    // Model selection state
    const [availableModels, setAvailableModels] = useState([]);
    const [selectedModel, setSelectedModel] = useState(null);
    const [showModelSelector, setShowModelSelector] = useState(false);

    const messagesEndRef = useRef(null);
    const inputRef = useRef(null);

    // Check ADK status and fetch models on mount
    useEffect(() => {
        checkAdkStatus();
        fetchAvailableModels();
    }, []);

    // Scroll to bottom when messages change
    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages]);

    const checkAdkStatus = async () => {
        try {
            const res = await fetch(`${API_BASE}/adk/status`);
            if (res.ok) {
                const data = await res.json();
                setAdkStatus(data);
                if (data.enabled) {
                    setMessages([{
                        role: 'assistant',
                        content: `👋 Halo! Saya Remora Commander, AI assistant untuk analisa saham Indonesia.\n\n🎯 Yang bisa saya bantu:\n• Analisa Order Flow (OBI, HAKA/HAKI, Iceberg)\n• Deteksi Smart Money (Bandarmologi)\n• Sinyal Looping Strategy\n• Kalkulasi position size (30-30-40)\n\nCoba tanya: "Analisa ${symbol} sekarang" atau "Hitung position size BBCA"`
                    }]);
                }
            } else {
                setAdkStatus({ enabled: false });
            }
        } catch (err) {
            setAdkStatus({ enabled: false, error: err.message });
        }
    };

    const fetchAvailableModels = async () => {
        try {
            const res = await fetch(`${API_BASE}/adk/models`);
            if (res.ok) {
                const data = await res.json();
                setAvailableModels(data.available || []);
                setSelectedModel(data.current || data.default);
            }
        } catch (err) {
            console.warn('Failed to fetch models:', err);
        }
    };

    const processMessage = async (messageText) => {
        setLoading(true);
        onStatusChange?.('loading');

        try {
            const res = await fetch(`${API_BASE}/adk/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: messageText,
                    session_id: sessionId,
                    model: selectedModel
                })
            });

            const data = await res.json();

            if (data.success) {
                setMessages(prev => [...prev, {
                    role: 'assistant',
                    content: data.response,
                    model: data.model
                }]);
                if (data.session_id) {
                    setSessionId(data.session_id);
                }
                if (data.model && data.model !== selectedModel) {
                    setSelectedModel(data.model);
                }
            } else {
                let errorMessage = data.message || 'Unknown error occurred';

                if (data.error === 'rate_limit') {
                    errorMessage = '⚠️ API rate limit tercapai. Coba model lain atau tunggu sebentar.';
                } else if (data.error === 'timeout') {
                    errorMessage = '⏱️ Request timeout. Coba pertanyaan lebih sederhana.';
                } else if (data.error === 'not_enabled') {
                    errorMessage = '🔌 ADK tidak aktif. Set ADK_ENABLED=true di backend.';
                }

                setMessages(prev => [...prev, {
                    role: 'error',
                    content: errorMessage
                }]);
            }
        } catch (err) {
            setMessages(prev => [...prev, {
                role: 'error',
                content: `❌ Gagal menghubungi AI: ${err.message}`
            }]);
        } finally {
            setLoading(false);
            onStatusChange?.('done');
            inputRef.current?.focus();
        }
    };

    const sendMessage = useCallback(async () => {
        if (!input.trim() || loading) return;

        const userMessage = input.trim();
        setInput('');

        // Special handling for Full Analysis trigger
        if (userMessage.startsWith('FULL_ANALYSIS:')) {
            const ticker = userMessage.split(':')[1];
            // 1. Show the "clean" user message in UI
            setMessages(prev => [...prev, { role: 'user', content: `Analisa lengkap ${ticker}` }]);

            // 2. Construct the mapped prompt
            const fullPrompt = `Berikan analisa lengkap 360 derajat untuk saham ${ticker}. Sertakan tinjauan Order Flow, Bandarmology, Teknikal, dan Fundamental (Alpha-V).`;

            // 3. Process directly (avoid state round-trip loop)
            await processMessage(fullPrompt);
            return;
        }

        // Normal message
        setMessages(prev => [...prev, { role: 'user', content: userMessage }]);
        await processMessage(userMessage);

    }, [input, loading, sessionId, selectedModel, onStatusChange]);

    const handleKeyPress = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    };

    // Quick action buttons
    const quickActions = [
        { label: '📊 Analisa', action: `Analisa ${symbol} sekarang` },
        { label: '🧠 Full AI Analysis', action: `FULL_ANALYSIS:${symbol}` }, // Trigger full analysis
        { label: '💹 Order Flow', action: `Berikan analisa Order Flow untuk ${symbol}` },
        { label: '🔍 Smart Money', action: `Apakah ada Smart Money di ${symbol}?` },
        { label: '💰 Position', action: 'Bagaimana cara hitung position size dengan piramida 30-30-40?' },
    ];

    const handleQuickAction = (action) => {
        setInput(action);
        inputRef.current?.focus();
    };

    const getModelDisplayName = (modelId) => {
        if (!modelId) return 'Model';
        const found = availableModels.find(m => m.id === modelId);
        if (found) return found.name;
        const parts = modelId.split('/');
        return parts[parts.length - 1].split(':')[0];
    };

    // If ADK is not enabled
    if (adkStatus && !adkStatus.enabled) {
        return (
            <div className="adk-chat-panel panel">
                <div className="panel-header">
                    <h3>🤖 AI Trading Assistant</h3>
                    <span className="status-badge offline">Offline</span>
                </div>
                <div className="panel-content disabled-state">
                    <div className="disabled-icon">🔌</div>
                    <h4>ADK Tidak Aktif</h4>
                    <p>AI Trading Assistant belum diaktifkan.</p>
                    <div className="setup-steps">
                        <p>Untuk mengaktifkan:</p>
                        <ol>
                            <li>Set <code>ADK_ENABLED=true</code> di .env</li>
                            <li>Set <code>GEMINI_API_KEY=your_key</code></li>
                            <li>Install: <code>pip install google-adk</code></li>
                            <li>Restart backend server</li>
                        </ol>
                    </div>
                    <button className="retry-btn" onClick={checkAdkStatus}>
                        🔄 Check Again
                    </button>
                </div>
            </div>
        );
    }

    return (
        <div className="adk-chat-panel panel">
            <div className="panel-header">
                <h3>🤖 AI Trading Assistant</h3>
                <div className="header-controls">
                    {/* Model Selector */}
                    <div className="model-selector-wrapper">
                        <button
                            className="model-selector-btn"
                            onClick={() => setShowModelSelector(!showModelSelector)}
                            disabled={loading}
                            title="Select AI Model"
                        >
                            🧠 {selectedModel ? getModelDisplayName(selectedModel) : 'Model'}
                        </button>
                        {showModelSelector && (
                            <div className="model-dropdown">
                                <div className="model-dropdown-header">
                                    <span>🔄 Pilih Model AI</span>
                                    <button
                                        className="close-btn"
                                        onClick={() => setShowModelSelector(false)}
                                    >×</button>
                                </div>
                                {availableModels.length === 0 ? (
                                    <div className="model-loading">Loading models...</div>
                                ) : (
                                    availableModels.map(model => (
                                        <button
                                            key={model.id}
                                            className={`model-option ${selectedModel === model.id ? 'active' : ''}`}
                                            onClick={() => {
                                                setSelectedModel(model.id);
                                                setShowModelSelector(false);
                                            }}
                                        >
                                            <div className="model-name">
                                                {model.name}
                                                {model.is_free && <span className="free-badge">FREE</span>}
                                            </div>
                                            <div className="model-meta">
                                                <span className="model-provider">{model.provider}</span>
                                                <span className="model-rate">{model.rate_limit}</span>
                                            </div>
                                        </button>
                                    ))
                                )}
                            </div>
                        )}
                    </div>
                    <span className="status-badge online">
                        {loading ? '⏳' : '●'} {loading ? 'Thinking...' : 'Online'}
                    </span>
                </div>
            </div>

            <div className="panel-content">
                {/* Current Model Badge */}
                {selectedModel && (
                    <div className="current-model-badge">
                        <span className="model-icon">🧠</span>
                        <span className="model-label">{getModelDisplayName(selectedModel)}</span>
                    </div>
                )}

                {/* Quick Actions */}
                <div className="quick-actions">
                    {quickActions.map((qa, idx) => (
                        <button
                            key={idx}
                            className="quick-action-btn"
                            onClick={() => handleQuickAction(qa.action)}
                            disabled={loading}
                        >
                            {qa.label}
                        </button>
                    ))}
                </div>

                {/* Messages */}
                <div className="messages-container">
                    {messages.map((msg, idx) => (
                        <div key={idx} className={`message ${msg.role}`}>
                            <div className="message-avatar">
                                {msg.role === 'user' ? '👤' :
                                    msg.role === 'error' ? '⚠️' : '🤖'}
                            </div>
                            <div className="message-content">
                                <pre>{msg.content}</pre>
                            </div>
                        </div>
                    ))}
                    {loading && (
                        <div className="message assistant loading">
                            <div className="message-avatar">🤖</div>
                            <div className="message-content">
                                <div className="typing-indicator">
                                    <span></span>
                                    <span></span>
                                    <span></span>
                                </div>
                            </div>
                        </div>
                    )}
                    <div ref={messagesEndRef} />
                </div>

                {/* Input Area */}
                <div className="input-area">
                    <textarea
                        ref={inputRef}
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyPress={handleKeyPress}
                        placeholder="Tanya Remora Commander..."
                        disabled={loading}
                        rows={2}
                    />
                    <button
                        className="send-btn"
                        onClick={sendMessage}
                        disabled={loading || !input.trim()}
                    >
                        {loading ? '⏳' : '📤'}
                    </button>
                </div>
            </div>
        </div>
    );
}
