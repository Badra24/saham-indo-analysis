import { useState, useRef, useCallback } from 'react';
import { Upload, FileText, AlertCircle, CheckCircle, X, Loader2, FileSpreadsheet } from 'lucide-react';
import { API_BASE_URL } from '../config';
import './FileUploadPanel.css';

/**
 * FileUploadPanel - Upload broker summary and financial reports
 * 
 * Features:
 * - Drag and drop file upload
 * - PDF, CSV, Excel support
 * - Parsed data preview
 * - Integration with Alpha-V scoring
 */
const FileUploadPanel = ({
    ticker,
    mode = 'broker_summary', // 'broker_summary' or 'financial_report'
    onUploadComplete,
    showAsInline = false,
    apiLimitReached = false
}) => {
    const [isDragging, setIsDragging] = useState(false);
    const [uploadState, setUploadState] = useState('idle'); // idle, uploading, success, error
    const [uploadResult, setUploadResult] = useState(null);
    const [errorMessage, setErrorMessage] = useState('');
    const fileInputRef = useRef(null);

    const acceptedTypes = mode === 'broker_summary'
        ? '.pdf,.csv,.xlsx,.xls,.png,.jpg,.jpeg'
        : '.csv,.xlsx,.xls,.pdf';

    const handleDragOver = useCallback((e) => {
        e.preventDefault();
        setIsDragging(true);
    }, []);

    const handleDragLeave = useCallback((e) => {
        e.preventDefault();
        setIsDragging(false);
    }, []);

    const handleDrop = useCallback((e) => {
        e.preventDefault();
        setIsDragging(false);

        const files = e.dataTransfer.files;
        if (files.length > 0) {
            handleFileUpload(files[0]);
        }
    }, [ticker, mode]);

    const handleFileSelect = (e) => {
        const files = e.target.files;
        if (files.length > 0) {
            handleFileUpload(files[0]);
        }
    };

    const handleFileUpload = async (file) => {
        if (!ticker) {
            setErrorMessage('Please select a stock first');
            setUploadState('error');
            return;
        }

        // STRICT VALIDATION: Reject if filename doesn't contain the current ticker
        const fileName = file.name.toUpperCase();
        const currentTicker = ticker.toUpperCase();

        if (!fileName.includes(currentTicker)) {
            setErrorMessage(`Upload Rejected: File must be named with "${currentTicker}"`);
            setUploadState('error');
            alert(
                `⛔ Upload Rejected\n\n` +
                `System Security: The file "${file.name}" does NOT match the current ticker "${currentTicker}".\n\n` +
                `Please rename your file to include "${currentTicker}" before uploading.`
            );
            return;
        }

        const formData = new FormData();
        formData.append('file', file);
        formData.append('ticker', ticker);

        setUploadState('uploading');
        setErrorMessage('');

        try {
            // Detect if file is an image for OCR processing
            const ext = file.name.split('.').pop().toLowerCase();
            const isImage = ['png', 'jpg', 'jpeg'].includes(ext);

            let endpoint;
            if (mode === 'broker_summary') {
                endpoint = isImage
                    ? `${API_BASE_URL}/api/v1/upload/broker-summary-image`
                    : `${API_BASE_URL}/api/v1/upload/broker-summary`;
            } else {
                endpoint = `${API_BASE_URL}/api/v1/upload/financial-report`;
            }

            const response = await fetch(endpoint, {
                method: 'POST',
                body: formData
            });

            const result = await response.json();

            if (result.success) {
                setUploadState('success');
                setUploadResult(result);
                if (onUploadComplete) {
                    onUploadComplete(result);
                }
            } else {
                setUploadState('error');
                setErrorMessage(result.message || 'Upload failed');
            }
        } catch (error) {
            setUploadState('error');
            setErrorMessage(error.message || 'Network error');
        }
    };

    const resetUpload = () => {
        setUploadState('idle');
        setUploadResult(null);
        setErrorMessage('');
        if (fileInputRef.current) {
            fileInputRef.current.value = '';
        }
    };

    const renderUploadArea = () => (
        <div
            className={`file-upload-dropzone ${isDragging ? 'dragging' : ''} ${apiLimitReached ? 'api-limited' : ''}`}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
        >
            <input
                type="file"
                ref={fileInputRef}
                accept={acceptedTypes}
                onChange={handleFileSelect}
                style={{ display: 'none' }}
            />

            {apiLimitReached && (
                <div className="api-limit-warning">
                    <AlertCircle size={16} />
                    <span>API Limit Reached - Please upload file</span>
                </div>
            )}

            <div className="dropzone-content">
                <Upload size={32} className="upload-icon" />
                <p className="dropzone-title">
                    {mode === 'broker_summary' ? 'Upload Broker Summary' : 'Upload Financial Report'}
                </p>
                <p className="dropzone-subtitle">
                    Drag & drop or click to browse
                </p>
                <div className="file-types">
                    {mode === 'broker_summary' ? (
                        <>
                            <span className="file-type">PNG</span>
                            <span className="file-type">JPG</span>
                            <span className="file-type">PDF</span>
                            <span className="file-type">CSV</span>
                        </>
                    ) : (
                        <>
                            <span className="file-type">CSV</span>
                            <span className="file-type">Excel</span>
                        </>
                    )}
                </div>
            </div>
        </div>
    );

    const renderUploading = () => (
        <div className="upload-status uploading">
            <Loader2 size={32} className="spinner" />
            <p>Processing file...</p>
        </div>
    );

    const renderSuccess = () => {
        const data = uploadResult?.parsed_data;

        return (
            <div className="upload-status success">
                <div className="status-header">
                    <CheckCircle size={24} className="success-icon" />
                    <span>Upload Successful</span>
                    <button className="reset-btn" onClick={resetUpload}>
                        <X size={16} />
                    </button>
                </div>

                {data && mode === 'broker_summary' && (
                    <div className="parsed-preview">
                        <div className="preview-row">
                            <span className="label">BCR:</span>
                            <span className={`value ${data.bcr > 1.2 ? 'bullish' : data.bcr < 0.8 ? 'bearish' : ''}`}>
                                {data.bcr?.toFixed(2)}
                            </span>
                        </div>
                        <div className="preview-row">
                            <span className="label">Phase:</span>
                            <span className={`value phase-${data.phase?.toLowerCase()}`}>
                                {data.phase}
                            </span>
                        </div>
                        <div className="preview-row">
                            <span className="label">Top Buyers:</span>
                            <span className="value">
                                {data.top_buyers?.slice(0, 3).map(b => b.broker_code).join(', ')}
                            </span>
                        </div>
                        {data.retail_disguise_detected && (
                            <div className="disguise-alert">
                                🕵️ Retail disguise detected
                            </div>
                        )}
                    </div>
                )}

                {data && mode === 'financial_report' && (
                    <div className="parsed-preview">
                        <div className="preview-row">
                            <span className="label">PER:</span>
                            <span className="value">{data.per?.toFixed(1) || 'N/A'}</span>
                        </div>
                        <div className="preview-row">
                            <span className="label">PBV:</span>
                            <span className="value">{data.pbv?.toFixed(2) || 'N/A'}</span>
                        </div>
                        <div className="preview-row">
                            <span className="label">ROE:</span>
                            <span className="value">{data.roe ? `${data.roe.toFixed(1)}%` : 'N/A'}</span>
                        </div>
                    </div>
                )}

                {uploadResult?.warnings?.length > 0 && (
                    <div className="warnings">
                        {uploadResult.warnings.map((w, i) => (
                            <div key={i} className="warning-item">⚠️ {w}</div>
                        ))}
                    </div>
                )}
            </div>
        );
    };

    const renderError = () => (
        <div className="upload-status error">
            <div className="status-header">
                <AlertCircle size={24} className="error-icon" />
                <span>Upload Failed</span>
                <button className="reset-btn" onClick={resetUpload}>
                    <X size={16} />
                </button>
            </div>
            <p className="error-message">{errorMessage}</p>
        </div>
    );

    return (
        <div className={`file-upload-panel ${showAsInline ? 'inline' : ''}`}>
            {uploadState === 'idle' && renderUploadArea()}
            {uploadState === 'uploading' && renderUploading()}
            {uploadState === 'success' && renderSuccess()}
            {uploadState === 'error' && renderError()}
        </div>
    );
};

export default FileUploadPanel;
