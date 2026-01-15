import { useState, useEffect, useCallback } from 'react';
import './SettingsPanel.css';

const API_BASE = 'http://localhost:8000';

export function SettingsPanel({ isOpen, onClose }) {
    const [stockbitStatus, setStockbitStatus] = useState(null);
    const [newToken, setNewToken] = useState('');
    const [adminKey, setAdminKey] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [isTesting, setIsTesting] = useState(false);
    const [message, setMessage] = useState(null);

    // Fetch Stockbit status on open
    const fetchStatus = useCallback(async () => {
        try {
            const res = await fetch(`${API_BASE}/api/stockbit/status`);
            const data = await res.json();
            setStockbitStatus(data);
        } catch (err) {
            setStockbitStatus({ success: false, error: err.message });
        }
    }, []);

    useEffect(() => {
        if (isOpen) {
            fetchStatus();
            // Load saved admin key from localStorage
            const savedKey = localStorage.getItem('admin_secret_key');
            if (savedKey) setAdminKey(savedKey);
        }
    }, [isOpen, fetchStatus]);

    // Update token
    const handleUpdateToken = async () => {
        if (!newToken.trim()) {
            setMessage({ type: 'error', text: 'Token tidak boleh kosong' });
            return;
        }

        setIsLoading(true);
        setMessage(null);

        try {
            const res = await fetch(`${API_BASE}/api/stockbit/token`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Admin-Key': adminKey
                },
                body: JSON.stringify({ token: newToken })
            });

            if (res.status === 401) {
                setMessage({ type: 'error', text: 'Admin Key salah! Periksa ADMIN_SECRET_KEY di .env' });
                setIsLoading(false);
                return;
            }

            if (res.status === 429) {
                setMessage({ type: 'error', text: 'Terlalu banyak percobaan. Tunggu 1 menit.' });
                setIsLoading(false);
                return;
            }

            const data = await res.json();

            if (data.success) {
                setMessage({ type: 'success', text: 'Token berhasil diupdate!' });
                setNewToken('');
                // Save admin key for convenience
                localStorage.setItem('admin_secret_key', adminKey);
                // Refresh status
                setTimeout(fetchStatus, 500);
            } else {
                setMessage({ type: 'error', text: data.error || 'Gagal update token' });
            }
        } catch (err) {
            setMessage({ type: 'error', text: err.message });
        }

        setIsLoading(false);
    };

    // Test connection
    const handleTestConnection = async () => {
        setIsTesting(true);
        setMessage(null);

        try {
            const res = await fetch(`${API_BASE}/api/stockbit/test`);
            const data = await res.json();

            if (data.success) {
                setMessage({
                    type: 'success',
                    text: `✅ Token valid! BBCA: Rp ${data.sample_data?.lastprice?.toLocaleString() || 'N/A'}`
                });
            } else {
                setMessage({ type: 'error', text: data.message || 'Token tidak valid' });
            }
            // Refresh status
            fetchStatus();
        } catch (err) {
            setMessage({ type: 'error', text: err.message });
        }

        setIsTesting(false);
    };

    if (!isOpen) return null;

    return (
        <div className="settings-overlay" onClick={onClose}>
            <div className="settings-panel" onClick={e => e.stopPropagation()}>
                <div className="settings-header">
                    <h2>⚙️ Settings</h2>
                    <button className="close-btn" onClick={onClose}>×</button>
                </div>

                <div className="settings-content">
                    {/* Stockbit Token Section */}
                    <div className="settings-section">
                        <h3>🔑 Stockbit Token</h3>

                        {/* Status Indicator */}
                        <div className={`status-card ${stockbitStatus?.token_valid ? 'valid' : 'invalid'}`}>
                            <div className="status-icon">
                                {stockbitStatus?.token_valid ? '✅' : '❌'}
                            </div>
                            <div className="status-info">
                                <span className="status-label">
                                    {stockbitStatus?.token_valid ? 'Token Valid' : 'Token Expired'}
                                </span>
                                <span className="status-detail">
                                    {stockbitStatus?.needs_refresh
                                        ? 'Perlu refresh token dari Stockbit'
                                        : `${stockbitStatus?.request_count || 0} requests made`
                                    }
                                </span>
                            </div>
                            <button
                                className="test-btn"
                                onClick={handleTestConnection}
                                disabled={isTesting}
                            >
                                {isTesting ? '⏳' : '🔄'} Test
                            </button>
                        </div>

                        {/* Message */}
                        {message && (
                            <div className={`message ${message.type}`}>
                                {message.text}
                            </div>
                        )}

                        {/* Update Token Form */}
                        <div className="token-form">
                            <label>Admin Key (dari .env)</label>
                            <input
                                type="password"
                                placeholder="ADMIN_SECRET_KEY"
                                value={adminKey}
                                onChange={e => setAdminKey(e.target.value)}
                            />

                            <label>Stockbit Token Baru</label>
                            <textarea
                                placeholder="Paste token dari Browser DevTools → Network → Headers → Authorization"
                                value={newToken}
                                onChange={e => setNewToken(e.target.value)}
                                rows={3}
                            />

                            <button
                                className="update-btn"
                                onClick={handleUpdateToken}
                                disabled={isLoading || !newToken.trim()}
                            >
                                {isLoading ? '⏳ Updating...' : '🔄 Update Token'}
                            </button>
                        </div>

                        {/* Help Section */}
                        <div className="help-section">
                            <h4>📖 Cara Mendapatkan Token:</h4>
                            <ol>
                                <li>Login ke <a href="https://stockbit.com" target="_blank" rel="noreferrer">stockbit.com</a></li>
                                <li>Buka DevTools (F12) → Network tab</li>
                                <li>Refresh halaman atau klik saham</li>
                                <li>Cari request ke "exodus.stockbit.com"</li>
                                <li>Copy value dari header "Authorization"</li>
                                <li>Paste di field di atas (tanpa "Bearer ")</li>
                            </ol>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}

export default SettingsPanel;
