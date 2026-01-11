import { memo, useState } from 'react';
import './DrawingToolbar.css';

const DRAWING_TOOLS = [
    { id: 'rectangle', icon: '▭', label: 'Rectangle', shortcut: 'R' },
    { id: 'fibonacci', icon: '📐', label: 'Fibonacci', shortcut: 'F' },
    { id: 'longPosition', icon: '📈', label: 'Long', shortcut: 'L' },
    { id: 'shortPosition', icon: '📉', label: 'Short', shortcut: 'S' },
    { id: 'fibFan', icon: '🌀', label: 'Fib Fan', shortcut: 'A' },
    { id: 'xabcd', icon: '✦', label: 'XABCD', shortcut: 'X' },
];

function DrawingToolbar({
    activeTool,
    onToolSelect,
    onDeleteSelected,
    onClearAll,
    onClearByType,
    drawingsByType = {},
    hasSelection,
    drawingsCount,
    magnetMode = true,
    onMagnetToggle,
}) {
    const [isCollapsed, setIsCollapsed] = useState(false);

    // Check if there are any drawings to show per-type clear section
    const hasAnyDrawings = Object.values(drawingsByType).some(count => count > 0);

    // Collapsed view - compact icon-only toolbar
    if (isCollapsed) {
        return (
            <div className="drawing-toolbar collapsed">
                <button
                    className="toolbar-btn expand-btn"
                    onClick={() => setIsCollapsed(false)}
                    title="Expand toolbar"
                >
                    <span className="tool-icon">◀</span>
                </button>
                <div className="toolbar-divider" />
                <div className="toolbar-tools-collapsed">
                    {DRAWING_TOOLS.map((tool) => (
                        <button
                            key={tool.id}
                            className={`toolbar-btn-mini ${activeTool === tool.id ? 'active' : ''}`}
                            onClick={() => onToolSelect(activeTool === tool.id ? null : tool.id)}
                            title={`${tool.label} (${tool.shortcut})`}
                        >
                            <span className="tool-icon">{tool.icon}</span>
                        </button>
                    ))}
                </div>
                {drawingsCount > 0 && (
                    <>
                        <div className="toolbar-divider" />
                        <button
                            className="toolbar-btn-mini clear-mini"
                            onClick={onClearAll}
                            title={`Clear All (${drawingsCount})`}
                        >
                            <span className="tool-icon">✖️</span>
                            <span className="mini-count">{drawingsCount}</span>
                        </button>
                    </>
                )}
            </div>
        );
    }

    // Full expanded view
    return (
        <div className="drawing-toolbar">
            {/* Collapse button */}
            <button
                className="toolbar-btn collapse-btn"
                onClick={() => setIsCollapsed(true)}
                title="Minimize toolbar"
            >
                <span className="tool-icon">▶</span>
                <span className="tool-label">Minimize</span>
            </button>

            <div className="toolbar-divider" />

            <div className="toolbar-section">
                <div className="toolbar-title">Drawing Tools</div>
                <div className="toolbar-tools">
                    {DRAWING_TOOLS.map((tool) => (
                        <button
                            key={tool.id}
                            className={`toolbar-btn ${activeTool === tool.id ? 'active' : ''}`}
                            onClick={() => onToolSelect(activeTool === tool.id ? null : tool.id)}
                            title={`${tool.label} (${tool.shortcut})`}
                        >
                            <span className="tool-icon">{tool.icon}</span>
                            <span className="tool-label">{tool.label}</span>
                        </button>
                    ))}
                </div>
            </div>

            {/* Magnet Mode Toggle */}
            <div className="toolbar-section magnet-section">
                <button
                    className={`toolbar-btn magnet-btn ${magnetMode ? 'active' : ''}`}
                    onClick={onMagnetToggle}
                    title={`Magnet Mode: ${magnetMode ? 'ON' : 'OFF'} - Snap to OHLC prices`}
                >
                    <span className="tool-icon">🧲</span>
                    <span className="tool-label">Magnet</span>
                    <span className={`magnet-status ${magnetMode ? 'on' : 'off'}`}>
                        {magnetMode ? 'ON' : 'OFF'}
                    </span>
                </button>
            </div>

            <div className="toolbar-divider" />

            {/* Per-Type Clear Buttons - only show when there are drawings */}
            {hasAnyDrawings && (
                <div className="toolbar-section">
                    <div className="toolbar-title">Clear by Type</div>
                    <div className="toolbar-tools type-clear-list">
                        {DRAWING_TOOLS.map((tool) => {
                            const count = drawingsByType[tool.id] || 0;
                            if (count === 0) return null;
                            return (
                                <button
                                    key={`clear-${tool.id}`}
                                    className="toolbar-btn type-clear-btn"
                                    onClick={() => onClearByType(tool.id)}
                                    title={`Clear all ${tool.label} drawings`}
                                >
                                    <span className="tool-icon">🗑️</span>
                                    <span className="tool-label">{tool.label}</span>
                                    <span className="type-count">{count}</span>
                                </button>
                            );
                        })}
                    </div>
                </div>
            )}

            {hasAnyDrawings && <div className="toolbar-divider" />}

            <div className="toolbar-section toolbar-actions">
                <button
                    className="toolbar-btn action-btn delete-btn"
                    onClick={onDeleteSelected}
                    disabled={!hasSelection}
                    title="Delete Selected (Del)"
                >
                    <span className="tool-icon">🗑️</span>
                    <span className="tool-label">Delete</span>
                </button>
                <button
                    className="toolbar-btn action-btn clear-btn"
                    onClick={onClearAll}
                    disabled={drawingsCount === 0}
                    title="Clear All"
                >
                    <span className="tool-icon">✖️</span>
                    <span className="tool-label">Clear All</span>
                </button>
            </div>

            {activeTool && (
                <div className="toolbar-hint">
                    {getToolHint(activeTool)}
                </div>
            )}
        </div>
    );
}

function getToolHint(toolId) {
    const hints = {
        rectangle: 'Click and drag to draw rectangle',
        fibonacci: 'Click and drag: High → Low (or vice versa)',
        longPosition: 'Click: Entry → Stop Loss → Take Profit',
        shortPosition: 'Click: Entry → Stop Loss → Take Profit',
        fibFan: 'Click origin, then click target direction',
        xabcd: 'Click 5 points: X → A → B → C → D',
    };
    return hints[toolId] || '';
}

export default memo(DrawingToolbar);
