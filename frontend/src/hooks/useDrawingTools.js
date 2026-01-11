import { useState, useEffect, useCallback, useRef } from 'react';
import { generateDrawingId } from '../utils/drawingUtils';

const STORAGE_KEY_PREFIX = 'saham_indo_drawings_';

/**
 * Hook for managing drawing tools state and localStorage persistence
 */
export default function useDrawingTools(symbol) {
    const [drawings, setDrawings] = useState([]);
    const [activeTool, setActiveTool] = useState(null);
    const [selectedDrawing, setSelectedDrawing] = useState(null);
    const [isDrawing, setIsDrawing] = useState(false);
    const [currentDrawing, setCurrentDrawing] = useState(null);

    // Drag state for adjustable position lines
    const [dragState, setDragState] = useState(null);
    // { drawingId, pointIndex, pointType: 'entry'|'sl'|'tp'|'move'|'resize-left'|'resize-right' }

    // Magnet Mode - snap to OHLC candle prices
    const [magnetMode, setMagnetMode] = useState(true);
    const MAGNET_THRESHOLD = 20; // pixels - snap if within this distance

    // Hovered handle for visual feedback
    const [hoveredHandle, setHoveredHandle] = useState(null);
    // { drawingId, handleType }

    // Position settings state
    const [positionSettings, setPositionSettings] = useState({
        accountSize: 10000,
        riskPercent: 2,
        leverage: 1,
    });

    // Load drawings from localStorage when symbol changes
    useEffect(() => {
        if (!symbol) return;

        const storageKey = `${STORAGE_KEY_PREFIX}${symbol}`;
        try {
            const saved = localStorage.getItem(storageKey);
            if (saved) {
                setDrawings(JSON.parse(saved));
            } else {
                setDrawings([]);
            }
        } catch (e) {
            console.error('Error loading drawings:', e);
            setDrawings([]);
        }

        // Clear selection when symbol changes
        setSelectedDrawing(null);
        setCurrentDrawing(null);
        setIsDrawing(false);
        setDragState(null);
    }, [symbol]);

    // Load position settings from localStorage
    useEffect(() => {
        try {
            const savedSettings = localStorage.getItem('position_settings');
            if (savedSettings) {
                setPositionSettings(JSON.parse(savedSettings));
            }
        } catch (e) {
            console.error('Error loading position settings:', e);
        }
    }, []);

    // Save drawings to localStorage
    const saveDrawings = useCallback((newDrawings) => {
        if (!symbol) return;

        const storageKey = `${STORAGE_KEY_PREFIX}${symbol}`;
        try {
            localStorage.setItem(storageKey, JSON.stringify(newDrawings));
        } catch (e) {
            console.error('Error saving drawings:', e);
        }
    }, [symbol]);

    // Save position settings
    const savePositionSettings = useCallback((newSettings) => {
        try {
            localStorage.setItem('position_settings', JSON.stringify(newSettings));
            setPositionSettings(newSettings);
        } catch (e) {
            console.error('Error saving position settings:', e);
        }
    }, []);

    // Default width for position drawings (in seconds) - 50 candles worth
    const DEFAULT_POSITION_WIDTH = 50 * 60 * 60; // 50 hours default

    // Add a new drawing
    const addDrawing = useCallback((drawing) => {
        let newDrawing = {
            ...drawing,
            id: generateDrawingId(),
            createdAt: Date.now(),
        };

        // For position drawings, add startTime and width properties
        if (['longPosition', 'shortPosition'].includes(drawing.type) && drawing.points?.length > 0) {
            const times = drawing.points.map(p => p.time);
            const minTime = Math.min(...times);
            const maxTime = Math.max(...times);
            // Calculate width from click points, or use default if all same time
            const clickWidth = maxTime - minTime;
            newDrawing = {
                ...newDrawing,
                startTime: minTime,
                width: clickWidth > 0 ? clickWidth + 3600 : DEFAULT_POSITION_WIDTH, // Add 1 hour buffer or use default
            };
        }

        setDrawings(prev => {
            const updated = [...prev, newDrawing];
            saveDrawings(updated);
            return updated;
        });

        setCurrentDrawing(null);
        setIsDrawing(false);

        return newDrawing;
    }, [saveDrawings]);

    // Update an existing drawing
    const updateDrawing = useCallback((id, updates) => {
        setDrawings(prev => {
            const updated = prev.map(d =>
                d.id === id ? { ...d, ...updates, updatedAt: Date.now() } : d
            );
            saveDrawings(updated);
            return updated;
        });
    }, [saveDrawings]);

    // Delete a drawing
    const deleteDrawing = useCallback((id) => {
        setDrawings(prev => {
            const updated = prev.filter(d => d.id !== id);
            saveDrawings(updated);
            return updated;
        });

        if (selectedDrawing === id) {
            setSelectedDrawing(null);
        }
    }, [saveDrawings, selectedDrawing]);

    // Clear all drawings for current symbol
    const clearAllDrawings = useCallback(() => {
        setDrawings([]);
        saveDrawings([]);
        setSelectedDrawing(null);
    }, [saveDrawings]);

    // Clear drawings by specific tool type
    const clearDrawingsByType = useCallback((type) => {
        setDrawings(prev => {
            const updated = prev.filter(d => d.type !== type);
            saveDrawings(updated);
            return updated;
        });
        setSelectedDrawing(prevSel => {
            // Clear selection if the selected drawing is of the removed type
            const selDraw = drawings.find(d => d.id === prevSel);
            if (selDraw?.type === type) {
                return null;
            }
            return prevSel;
        });
    }, [saveDrawings, drawings]);

    // Get count of drawings by type
    const getDrawingsCountByType = useCallback(() => {
        const counts = {};
        drawings.forEach(d => {
            counts[d.type] = (counts[d.type] || 0) + 1;
        });
        return counts;
    }, [drawings]);

    // Delete selected drawing
    const deleteSelected = useCallback(() => {
        if (selectedDrawing) {
            deleteDrawing(selectedDrawing);
        }
    }, [selectedDrawing, deleteDrawing]);

    // ========== DRAG FUNCTIONS FOR ADJUSTABLE POSITIONS ==========

    // Store original positions for delta calculations
    const originalPointsRef = useRef(null);
    const startPosRef = useRef(null);
    const originalDrawingRef = useRef(null); // Store full drawing for width/startTime

    // Start dragging a specific point on a position drawing
    const startDrag = useCallback((drawingId, pointIndex, pointType) => {
        const drawing = drawings.find(d => d.id === drawingId);
        if (drawing) {
            originalPointsRef.current = drawing.points.map(p => ({ ...p }));
            originalDrawingRef.current = { ...drawing }; // Store original drawing with width/startTime
            startPosRef.current = null; // Will be set on first move
        }
        setDragState({
            drawingId,
            pointIndex,
            pointType,
        });
    }, [drawings]);

    // Update the dragged point position in real-time
    const updateDraggedPoint = useCallback((newPoint) => {
        if (!dragState) {
            return;
        }

        const { drawingId, pointIndex, pointType } = dragState;

        // Record start position on first move
        if (!startPosRef.current) {
            startPosRef.current = { ...newPoint };
        }

        setDrawings(prev => {
            return prev.map(d => {
                if (d.id !== drawingId) return d;

                const newPoints = [...d.points];

                if (pointType === 'entry' || pointType === 'sl' || pointType === 'tp') {
                    // Refinements for Position Tools (Long/Short)
                    // Best Practice: Separation of Concerns
                    // - SL/TP Handles: Adjust PRICE only (Risk/Reward). Time is LOCKED to prevent accidental shifts.
                    // - Entry Handle: Adjusts ENTRY PRICE and MOVES the entire tool (Time shift).

                    const isPositionTool = ['longPosition', 'shortPosition'].includes(d.type);

                    if (isPositionTool) {
                        if (pointType === 'sl' || pointType === 'tp') {
                            // SL/TP Limit: Change PRICE only. Keep Time fixed.
                            newPoints[pointIndex] = {
                                ...newPoints[pointIndex],
                                price: newPoint.price,
                                // Strict Time Lock: Use existing time from point, ignore mouse X movement
                                time: newPoints[pointIndex].time
                            };
                            // Do NOT update other points or startTime
                        } else if (pointType === 'entry') {
                            // Entry Handle: Acts as a "Move Anchor"
                            // Moves the entire position (Price + Time) relative to the new Entry location

                            const oldEntry = d.points[0]; // Assuming index 0 is always entry
                            const deltaPrice = newPoint.price - oldEntry.price;
                            const deltaTime = newPoint.time - oldEntry.time;

                            // Shift ALL points
                            for (let i = 0; i < newPoints.length; i++) {
                                newPoints[i] = {
                                    ...newPoints[i],
                                    price: newPoints[i].price + deltaPrice,
                                    time: newPoints[i].time + deltaTime,
                                };
                            }

                            // Update startTime for the drawing container
                            return {
                                ...d,
                                points: newPoints,
                                startTime: (d.startTime || newPoints[0].time) + deltaTime,
                            };
                        }
                    } else {
                        // Standard logic for other multi-point tools (Line, etc.) - if any
                        const newTime = newPoint.time;
                        // ... existing logic for generic tools if needed ...
                        // For now, let's keep the original "vertical alignment" enforcement if it wasn't a position tool
                        // But we primarily use this for Position tools. 

                        // Fallback/Original behavior for non-position tools reusing this logic (unlikely but safe)
                        newPoints[pointIndex] = {
                            ...newPoints[pointIndex],
                            price: newPoint.price,
                            time: newPoints[pointIndex].time // Lock time by default for vertical alignment?
                        };

                        // Actually, for generic tools we might want flexibility. 
                        // But since this block specifically targeted entry/sl/tp which are Position concepts:
                        newPoints[pointIndex] = { ...newPoint };
                    }

                    // Also update startTime property for consistent rendering width calculation
                    // Only needed if we shifted time (Entry handle)
                    if (isPositionTool && pointType === 'entry') {
                        // Handled above in return
                    }

                } else if (pointType === 'move' && originalPointsRef.current && startPosRef.current) {
                    // Move entire position
                    const deltaTime = newPoint.time - startPosRef.current.time;
                    const deltaPrice = newPoint.price - startPosRef.current.price;

                    for (let i = 0; i < originalPointsRef.current.length; i++) {
                        newPoints[i] = {
                            ...originalPointsRef.current[i],
                            time: originalPointsRef.current[i].time + deltaTime,
                            price: originalPointsRef.current[i].price + deltaPrice,
                        };
                    }

                    // For position drawings, also update startTime to enable horizontal movement
                    if (['longPosition', 'shortPosition'].includes(d.type) && originalDrawingRef.current) {
                        const origStartTime = originalDrawingRef.current.startTime || Math.min(...originalPointsRef.current.map(p => p.time));
                        return {
                            ...d,
                            points: newPoints,
                            startTime: origStartTime + deltaTime,
                        };
                    }
                } else if ((pointType === 'resize-left' || pointType === 'resize-right') && originalDrawingRef.current) {
                    // Resize - properly expand/shrink width
                    const orig = originalDrawingRef.current;
                    const origStartTime = orig.startTime || Math.min(...orig.points.map(p => p.time));
                    const origWidth = orig.width || 50 * 60 * 60; // Default 50 hours if not set
                    const origEndTime = origStartTime + origWidth;

                    let newStartTime = origStartTime;
                    let newWidth = origWidth;

                    if (pointType === 'resize-left') {
                        // Resize from left: change startTime, adjust width accordingly
                        newStartTime = newPoint.time;
                        newWidth = origEndTime - newStartTime;
                        // Minimum width check (at least 5 minutes)
                        if (newWidth < 300) {
                            newStartTime = origEndTime - 300;
                            newWidth = 300;
                        }
                    } else if (pointType === 'resize-right') {
                        // Resize from right: keep startTime, adjust width
                        newWidth = newPoint.time - origStartTime;
                        // Minimum width check (at least 5 minutes)
                        if (newWidth < 300) {
                            newWidth = 300;
                        }
                    }

                    // Update all points to use new startTime (they keep relative positions)
                    for (let i = 0; i < newPoints.length; i++) {
                        newPoints[i] = {
                            ...newPoints[i],
                            time: newStartTime, // All points at startTime for consistent rendering
                        };
                    }

                    return { ...d, points: newPoints, startTime: newStartTime, width: newWidth };
                }

                return { ...d, points: newPoints };
            });
        });
    }, [dragState]);

    // End drag and persist the change
    const endDrag = useCallback(() => {
        if (!dragState) return;

        // Clear refs
        originalPointsRef.current = null;
        startPosRef.current = null;
        originalDrawingRef.current = null;

        // Save the updated drawings to localStorage
        saveDrawings(drawings);
        setDragState(null);
    }, [dragState, drawings, saveDrawings]);

    // Update a specific point on a position drawing (for R:R presets)
    const updatePositionPoint = useCallback((drawingId, pointIndex, newPrice) => {
        setDrawings(prev => {
            const updated = prev.map(d => {
                if (d.id !== drawingId) return d;

                const newPoints = [...d.points];
                newPoints[pointIndex] = {
                    ...newPoints[pointIndex],
                    price: newPrice,
                };

                return { ...d, points: newPoints, updatedAt: Date.now() };
            });
            saveDrawings(updated);
            return updated;
        });
    }, [saveDrawings]);

    // Apply R:R preset to a position drawing
    const applyRRPreset = useCallback((drawingId, ratio) => {
        const drawing = drawings.find(d => d.id === drawingId);
        if (!drawing || !['longPosition', 'shortPosition'].includes(drawing.type)) return;
        if (drawing.points.length < 3) return;

        const entryPrice = drawing.points[0].price;
        const slPrice = drawing.points[1].price;
        const riskAmount = Math.abs(entryPrice - slPrice);
        const targetMove = riskAmount * ratio;

        let newTpPrice;
        if (drawing.type === 'longPosition') {
            // For long: TP is above entry
            newTpPrice = entryPrice + targetMove;
        } else {
            // For short: TP is below entry
            newTpPrice = entryPrice - targetMove;
        }

        updatePositionPoint(drawingId, 2, newTpPrice);
    }, [drawings, updatePositionPoint]);

    // Start a new drawing
    const startDrawing = useCallback((point) => {
        if (!activeTool) return;

        // SINGLE-CLICK TOOLS: Long/Short Position
        // Immediately create the tool with default 1:2 R:R settings
        if (activeTool === 'longPosition' || activeTool === 'shortPosition') {
            const price = point.price;
            let sl, tp;

            // Default 1% Risk, 2% Reward
            if (activeTool === 'longPosition') {
                sl = price * 0.99;
                tp = price * 1.02;
            } else {
                sl = price * 1.01;
                tp = price * 0.98;
            }

            const points = [
                { ...point, price: price }, // Entry
                { ...point, price: sl },    // SL
                { ...point, price: tp }     // TP
            ];

            const newDrawing = addDrawing({
                type: activeTool,
                points: points,
            });

            // Auto-select the new drawing so handles are visible and it can be edited immediately
            selectDrawing(newDrawing.id);
            setActiveTool(null); // Reset tool after single-click creation
            return;
        }

        const clickTools = ['xabcd'];
        const isClickTool = clickTools.includes(activeTool);

        setIsDrawing(true);
        setCurrentDrawing({
            type: activeTool,
            points: [point],
            startTime: Date.now(),
            // For click tools, track confirmed points count for preview functionality
            confirmedCount: isClickTool ? 1 : undefined,
        });
    }, [activeTool, addDrawing]);

    // Update current drawing with new point (for drag operations and click tool preview)
    const updateCurrentDrawing = useCallback((point) => {
        if (!isDrawing || !currentDrawing) return;

        const dragTools = ['rectangle', 'fibonacci', 'fibFan'];
        const clickTools = ['xabcd'];
        const isDragTool = dragTools.includes(currentDrawing.type);
        const isClickTool = clickTools.includes(currentDrawing.type);

        setCurrentDrawing(prev => {
            if (isDragTool) {
                // For drag tools: keep first point and update second
                if (prev.points.length === 1) {
                    return { ...prev, points: [prev.points[0], point] };
                } else {
                    return { ...prev, points: [prev.points[0], point] };
                }
            } else if (isClickTool) {
                // For click tools: keep all confirmed points, update preview point
                // The preview point is always at the end and will be replaced on next move
                const confirmedPoints = prev.points.filter((_, i) => i < prev.confirmedCount || prev.confirmedCount === undefined);
                const confirmedCount = prev.confirmedCount || prev.points.length;
                return {
                    ...prev,
                    points: [...confirmedPoints, point],
                    confirmedCount: confirmedCount,
                    previewPoint: point, // Store preview separately for clarity
                };
            }
            return prev;
        });
    }, [isDrawing, currentDrawing]);

    // Add point to multi-point drawings (Long/Short/XABCD)
    const addPointToDrawing = useCallback((point) => {
        if (!currentDrawing) return;

        setCurrentDrawing(prev => {
            // Get confirmed points (filter out any preview point)
            const confirmedCount = prev.confirmedCount || prev.points.length;
            const confirmedPoints = prev.points.slice(0, confirmedCount);

            // Add the new confirmed point and update confirmedCount
            return {
                ...prev,
                points: [...confirmedPoints, point],
                confirmedCount: confirmedCount + 1,
                previewPoint: null,
            };
        });
    }, [currentDrawing]);

    // Complete the current drawing
    const completeDrawing = useCallback((finalPoint) => {
        if (!currentDrawing) return null;

        // For drag-based tools (rectangle, fibonacci, fibFan), points are already in currentDrawing
        // For click-based tools, we need to add the final point
        const dragTools = ['rectangle', 'fibonacci', 'fibFan'];
        const isDragTool = dragTools.includes(currentDrawing.type);

        let points = currentDrawing.points;

        // For click-based tools, use confirmed points and add the final point
        if (!isDragTool) {
            const confirmedCount = currentDrawing.confirmedCount || currentDrawing.points.length;
            const confirmedPoints = currentDrawing.points.slice(0, confirmedCount);

            // Add final point if provided and different from last confirmed
            if (finalPoint && confirmedPoints.length > 0) {
                const lastPoint = confirmedPoints[confirmedPoints.length - 1];
                if (lastPoint.time !== finalPoint.time || lastPoint.price !== finalPoint.price) {
                    points = [...confirmedPoints, finalPoint];
                } else {
                    points = confirmedPoints;
                }
            } else {
                points = confirmedPoints;
            }
        }

        // Check if drawing has minimum required points
        const minPoints = {
            rectangle: 2,
            fibonacci: 2,
            fibFan: 2,
            xabcd: 5,
        };

        if (points.length < minPoints[currentDrawing.type]) {
            setCurrentDrawing(null);
            setIsDrawing(false);
            return null;
        }

        return addDrawing({
            type: currentDrawing.type,
            points,
        });
    }, [currentDrawing, addDrawing]);

    // Cancel current drawing
    const cancelDrawing = useCallback(() => {
        setCurrentDrawing(null);
        setIsDrawing(false);
    }, []);

    // Select a drawing
    const selectDrawing = useCallback((id) => {
        setSelectedDrawing(id);
        // Deactivate tool when selecting existing drawing
        if (id) setActiveTool(null);
    }, []);

    return {
        // State
        drawings,
        activeTool,
        selectedDrawing,
        isDrawing,
        currentDrawing,
        dragState,
        positionSettings,
        magnetMode,
        hoveredHandle,
        MAGNET_THRESHOLD,

        // Tool management
        setActiveTool,

        // Drawing CRUD
        addDrawing,
        updateDrawing,
        deleteDrawing,
        clearAllDrawings,
        clearDrawingsByType,
        getDrawingsCountByType,
        deleteSelected,

        // Drawing flow
        startDrawing,
        updateCurrentDrawing,
        addPointToDrawing,
        completeDrawing,
        cancelDrawing,

        // Selection
        selectDrawing,

        // Drag functionality
        startDrag,
        updateDraggedPoint,
        endDrag,

        // Magnet Mode
        setMagnetMode,
        setHoveredHandle,

        // Position settings
        savePositionSettings,
        updatePositionPoint,
        applyRRPreset,
    };
}
