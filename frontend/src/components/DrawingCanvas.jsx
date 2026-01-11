import { useRef, useEffect, useCallback, memo, useState } from 'react';
import {
    calculateFibLevels,
    calculateLongPosition,
    calculateShortPosition,
    calculateFibFanLines,
    calculateXABCDPattern,
    DRAWING_COLORS,
    FIB_COLORS,
    formatPrice,
    applyMagnet,
    binarySearchCandleIndex,
} from '../utils/drawingUtils';
import {
    INTERACTION_STATES,
    HANDLE_TYPES,
    getCursor,
    getNextState,
    isNearHandle as isNearHandleUtil,
} from '../utils/interactionManager';
import './DrawingCanvas.css';

const DRAG_TOOLS = ['rectangle', 'fibonacci', 'fibFan'];
const CLICK_TOOLS = ['longPosition', 'shortPosition', 'xabcd'];

function DrawingCanvas({
    chartRef,
    candleSeriesRef,
    drawings,
    currentDrawing,
    selectedDrawing,
    activeTool,
    isDrawing,
    onStartDrawing,
    onUpdateDrawing,
    onCompleteDrawing,
    onAddPoint,
    onSelectDrawing,
    containerRef,
    // Drag props for adjustable positions
    dragState,
    onStartDrag,
    onUpdateDraggedPoint,
    onEndDrag,
    // Magnet mode props
    magnetMode = true,
    magnetThreshold = 20,
    hoveredHandle,
    onSetHoveredHandle,
    candleData = [],
    onDeleteDrawing,
}) {
    const canvasRef = useRef(null);

    const contextRef = useRef(null);
    const animationRef = useRef(null);
    const isDraggingRef = useRef(false);

    // Track hovered close button
    const [hoveredCloseButton, setHoveredCloseButton] = useState(null); // drawingId or null

    // FSM State
    const [interactionState, setInteractionState] = useState(INTERACTION_STATES.IDLE);
    const [cursor, setCursor] = useState('default');
    const lastMousePosition = useRef({ x: 0, y: 0 });

    // Helper: Convert price to pixel Y
    const priceToCoordinate = useCallback((price) => {
        if (!candleSeriesRef?.current) return null;
        return candleSeriesRef.current.priceToCoordinate(price);
    }, [candleSeriesRef]);

    // Helper: Convert time to pixel X
    const timeToCoordinate = useCallback((time) => {
        if (!chartRef?.current) return null;
        return chartRef.current.timeScale().timeToCoordinate(time);
    }, [chartRef]);

    // Helper: Convert pixel X to time
    const coordinateToTime = useCallback((x) => {
        if (!chartRef?.current) return null;
        return chartRef.current.timeScale().coordinateToTime(x);
    }, [chartRef]);

    // Helper: Convert pixel X to candle index (approximate via time)
    const pixelToIndex = useCallback((x) => {
        const time = coordinateToTime(x);
        if (!time || !candleData.length) return -1;
        return binarySearchCandleIndex(candleData, time);
    }, [coordinateToTime, candleData]);

    // Helper: Convert candle index to pixel X
    const indexToPixel = useCallback((index) => {
        if (index < 0 || index >= candleData.length) return null;
        return timeToCoordinate(candleData[index].time);
    }, [candleData, timeToCoordinate]);

    // Initialize canvas
    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas || !containerRef?.current) return;

        const container = containerRef.current;
        canvas.width = container.clientWidth;
        canvas.height = container.clientHeight;

        const ctx = canvas.getContext('2d');
        ctx.lineCap = 'round';
        ctx.lineJoin = 'round';
        contextRef.current = ctx;

        // Handle resize
        const handleResize = () => {
            canvas.width = container.clientWidth;
            canvas.height = container.clientHeight;
            renderDrawings();
        };

        window.addEventListener('resize', handleResize);
        return () => window.removeEventListener('resize', handleResize);
    }, [containerRef]);

    // Convert price/time to pixel coordinates
    const priceTimeToPixel = useCallback((price, time) => {
        if (!chartRef?.current || !candleSeriesRef?.current) return null;

        try {
            const chart = chartRef.current;
            const series = candleSeriesRef.current;

            const timeScale = chart.timeScale();
            const priceScale = series.priceScale();

            const x = timeScale.timeToCoordinate(time);
            const y = series.priceToCoordinate(price);

            if (x === null || y === null) return null;
            return { x, y };
        } catch (e) {
            return null;
        }
    }, [chartRef, candleSeriesRef]);

    // Convert pixel coordinates to price/time
    const pixelToPriceTime = useCallback((x, y) => {
        if (!chartRef?.current || !candleSeriesRef?.current) return null;

        try {
            const chart = chartRef.current;
            const series = candleSeriesRef.current;

            const timeScale = chart.timeScale();
            const time = timeScale.coordinateToTime(x);
            const price = series.coordinateToPrice(y);

            if (time === null || price === null) return null;
            return { time, price, x, y };
        } catch (e) {
            return null;
        }
    }, [chartRef, candleSeriesRef]);

    // Helper: Get Close Button Position based on drawing type and points
    const getCloseButtonPosition = useCallback((drawing, pixelPoints) => {
        if (!pixelPoints || pixelPoints.length === 0) return null;

        // Default position: top-right of the bounding box
        let x = pixelPoints[0].x;
        let y = pixelPoints[0].y;

        if (drawing.type === 'rectangle' || drawing.type === 'fibonacci' || drawing.type === 'fibFan') {
            const xs = pixelPoints.map(p => p.x);
            const ys = pixelPoints.map(p => p.y);
            x = Math.max(...xs);
            y = Math.min(...ys);
        } else if (drawing.type === 'longPosition' || drawing.type === 'shortPosition') {
            // Position at top-right of the position tool
            const xs = pixelPoints.map(p => p.x);
            const ys = pixelPoints.map(p => p.y);
            const minX = Math.min(...xs);

            // Calculate width dynamically
            // Default 50 hours (in seconds) if width not saved
            const widthSeconds = drawing.width || (50 * 60 * 60);
            const endTime = drawing.startTime + widthSeconds;

            const endX = timeToCoordinate(endTime);

            let maxX;
            if (endX !== null) {
                maxX = endX;
            } else {
                // Fallback to legacy behavior if time conversion fails
                maxX = Math.max(...xs) + 180;
            }

            // Place close button at top-right corner of bounding box
            x = maxX;
            y = Math.min(...ys);
        } else if (drawing.type === 'xabcd') {
            // Position at top-right of the pattern
            const xs = pixelPoints.map(p => p.x);
            const ys = pixelPoints.map(p => p.y);
            x = Math.max(...xs);
            y = Math.min(...ys);
        }

        // Adjust for padding - move button slightly outside the drawing
        return { x: x + 10, y: y - 10 };
    }, [priceTimeToPixel]);

    // Helper: Draw Close Button
    const drawCloseButton = useCallback((ctx, x, y, isHovered) => {
        const size = 16;
        const half = size / 2;

        ctx.save();
        ctx.translate(x, y);

        // Background
        ctx.fillStyle = isHovered ? '#ef4444' : 'rgba(100, 116, 139, 0.2)'; // Red on hover, gray default
        ctx.beginPath();
        ctx.arc(0, 0, half, 0, Math.PI * 2);
        ctx.fill();

        // X icon
        ctx.strokeStyle = '#ffffff';
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.moveTo(-3, -3);
        ctx.lineTo(3, 3);
        ctx.moveTo(3, -3);
        ctx.lineTo(-3, 3);
        ctx.stroke();

        ctx.restore();
    }, []);

    // Helper: Draw Magnet Indicator
    const drawMagnetIndicator = useCallback((ctx) => {
        const { x, y } = lastMousePosition.current;
        if (!x || !y) return;

        // Check if we are snapping
        const result = applyMagnet(
            x, y,
            candleData,
            pixelToIndex,
            priceToCoordinate,
            indexToPixel,
            magnetThreshold
        );

        if (result.snapped) {
            ctx.save();
            ctx.strokeStyle = '#3b82f6'; // Blue
            ctx.fillStyle = 'rgba(59, 130, 246, 0.2)';
            ctx.lineWidth = 2;

            ctx.beginPath();
            ctx.arc(result.x, result.y, 5, 0, Math.PI * 2);
            ctx.fill();
            ctx.stroke();

            // Optional: Draw line to cursor ?? No, simpler is better.
            ctx.restore();
        }
    }, [candleData, pixelToIndex, priceToCoordinate, indexToPixel, magnetThreshold]);

    // Render all drawings
    const renderDrawings = useCallback(() => {
        const ctx = contextRef.current;
        const canvas = canvasRef.current;
        if (!ctx || !canvas) return;

        // Clear canvas
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        // Render saved drawings
        drawings.forEach(drawing => {
            renderDrawing(ctx, drawing, drawing.id === selectedDrawing);
        });

        // Hit detection for close buttons happens in event handlers, but we need to render them
        // We do this inside renderDrawing to ensure correct layering


        // Render current drawing in progress
        if (currentDrawing && currentDrawing.points.length > 0) {
            renderDrawing(ctx, currentDrawing, false, true);
        }

        // Render Magnet Indicator if active (show during tool selection, drawing, or idle with magnet on)
        if (magnetMode && hoveredHandle === null && !hoveredCloseButton && (activeTool || isDrawing)) {
            drawMagnetIndicator(ctx);
        }
    }, [drawings, currentDrawing, selectedDrawing, priceTimeToPixel, magnetMode, hoveredHandle, hoveredCloseButton, activeTool, isDrawing]);

    // Render a single drawing
    const renderDrawing = useCallback((ctx, drawing, isSelected, isPreview = false) => {
        try {
            const { type, points } = drawing;

            if (!points || !Array.isArray(points)) return;

            // Convert points to pixel coordinates
            const pixelPoints = points.map(p => {
                if (p.x !== undefined && p.y !== undefined) {
                    return p; // Already in pixels (during drawing)
                }
                return priceTimeToPixel(p.price, p.time);
            }).filter(p => p !== null);

            if (pixelPoints.length === 0) return;

            ctx.save();

            // Selection highlight
            if (isSelected) {
                ctx.strokeStyle = DRAWING_COLORS.selected;
                ctx.lineWidth = 3;
                ctx.setLineDash([5, 5]);
            }

            // Preview style
            if (isPreview) {
                ctx.globalAlpha = 0.8;
            }

            switch (type) {
                case 'rectangle':
                    renderRectangle(ctx, pixelPoints, isSelected);
                    break;
                case 'fibonacci':
                    renderFibonacci(ctx, pixelPoints, points, isSelected);
                    break;
                case 'longPosition':
                    renderLongPosition(ctx, pixelPoints, points, isSelected, drawing);
                    break;
                case 'shortPosition':
                    renderShortPosition(ctx, pixelPoints, points, isSelected, drawing);
                    break;
                case 'fibFan':
                    renderFibFan(ctx, pixelPoints, isSelected);
                    break;
                case 'xabcd':
                    renderXABCD(ctx, pixelPoints, points, isSelected);
                    break;
            }

            // Render Close Button for saved drawings (not preview)
            if (!isPreview && drawing.id) {
                const buttonPos = getCloseButtonPosition(drawing, pixelPoints);

                if (buttonPos && Number.isFinite(buttonPos.x) && Number.isFinite(buttonPos.y)) {
                    // Draw slightly outside top-right (helper already adds padding)
                    drawCloseButton(ctx, buttonPos.x, buttonPos.y, hoveredCloseButton === drawing.id);
                }
            }

            ctx.restore();
        } catch (error) {
            console.error(`Failed to render drawing ${drawing.id} (${drawing.type}):`, error);
            ctx.restore(); // Ensure context is restored even on error
        }
    }, [priceTimeToPixel, hoveredCloseButton, drawCloseButton, getCloseButtonPosition]);

    // Rectangle renderer
    const renderRectangle = (ctx, points, isSelected) => {
        if (points.length < 2) return;

        const [start, end] = points;
        const width = end.x - start.x;
        const height = end.y - start.y;

        // Fill
        ctx.fillStyle = DRAWING_COLORS.rectangle;
        ctx.fillRect(start.x, start.y, width, height);

        // Border
        ctx.strokeStyle = isSelected ? DRAWING_COLORS.selected : DRAWING_COLORS.rectangleBorder;
        ctx.lineWidth = isSelected ? 2 : 1;
        ctx.setLineDash([]);
        ctx.strokeRect(start.x, start.y, width, height);
    };

    // Fibonacci retracement renderer
    const renderFibonacci = (ctx, pixelPoints, pricePoints, isSelected) => {
        if (pixelPoints.length < 2 || pricePoints.length < 2) return;

        const [start, end] = pixelPoints;
        const startPrice = pricePoints[0].price;
        const endPrice = pricePoints[1].price;

        // Calculate actual prices from points
        const actualStartPrice = typeof startPrice === 'number' ? startPrice : start.y;
        const actualEndPrice = typeof endPrice === 'number' ? endPrice : end.y;

        const levels = calculateFibLevels(actualStartPrice, actualEndPrice);

        // Use bounded width based on drawn points (like rectangle)
        const startX = Math.min(start.x, end.x);
        const endX = Math.max(start.x, end.x);
        const labelOffset = 85; // Space for labels on the right

        levels.forEach((level, index) => {
            const y = start.y + (end.y - start.y) * level.level;

            // Zone fill
            if (index < levels.length - 1) {
                const nextY = start.y + (end.y - start.y) * levels[index + 1].level;
                ctx.fillStyle = FIB_COLORS[index];
                ctx.fillRect(startX, Math.min(y, nextY), endX - startX + labelOffset, Math.abs(nextY - y));
            }

            // Level line
            ctx.strokeStyle = isSelected ? DRAWING_COLORS.selected : DRAWING_COLORS.fibonacci;
            ctx.lineWidth = level.level === 0 || level.level === 1 ? 2 : 1;
            ctx.setLineDash(level.level === 0 || level.level === 1 ? [] : [4, 4]);
            ctx.beginPath();
            ctx.moveTo(startX, y);
            ctx.lineTo(endX + labelOffset, y);
            ctx.stroke();

            // Label with background for better readability
            const labelText = `${level.label} ($${formatPrice(level.price)})`;
            ctx.font = '11px Inter, sans-serif';
            const textWidth = ctx.measureText(labelText).width;

            // Label background
            ctx.fillStyle = 'rgba(22, 22, 31, 0.9)';
            ctx.fillRect(endX + 5, y - 8, textWidth + 8, 16);

            // Label text
            ctx.fillStyle = '#fff';
            ctx.textAlign = 'left';
            ctx.fillText(labelText, endX + 9, y + 4);
        });

        // Price range info box at top
        const priceRange = Math.abs(actualEndPrice - actualStartPrice);
        const pricePercent = ((priceRange / Math.min(actualStartPrice, actualEndPrice)) * 100).toFixed(2);

        ctx.fillStyle = 'rgba(245, 158, 11, 0.9)';
        ctx.fillRect(startX, Math.min(start.y, end.y) - 28, 140, 22);
        ctx.fillStyle = '#fff';
        ctx.font = 'bold 11px Inter, sans-serif';
        ctx.textAlign = 'left';
        ctx.fillText(`Range: $${formatPrice(priceRange)} (${pricePercent}%)`, startX + 6, Math.min(start.y, end.y) - 12);

        // Draw vertical lines at start and end points
        ctx.strokeStyle = DRAWING_COLORS.fibonacci;
        ctx.lineWidth = 1;
        ctx.setLineDash([2, 2]);
        ctx.beginPath();
        ctx.moveTo(start.x, start.y);
        ctx.lineTo(start.x, end.y);
        ctx.stroke();

        // End vertical line
        ctx.beginPath();
        ctx.moveTo(end.x, start.y);
        ctx.lineTo(end.x, end.y);
        ctx.stroke();
    };

    // Long Position renderer - TradingView Style
    const renderLongPosition = (ctx, pixelPoints, pricePoints, isSelected, drawing = {}) => {
        if (pixelPoints.length < 2) return;

        // FIX: Use drawing.width for correct right edge calculation involves time
        const allX = pixelPoints.map(p => p.x);
        const minX = Math.min(...allX);

        // Calculate max X from time width (Seconds)
        let maxX;
        const widthSeconds = drawing.width || (50 * 60 * 60);
        const endTime = drawing.startTime + widthSeconds;
        const endX = timeToCoordinate(endTime);

        if (endX !== null) {
            maxX = endX;
        } else {
            maxX = Math.max(...allX) + 180; // Fallback
        }

        const width = maxX - minX;

        const entryY = pixelPoints[0].y;
        const slY = pixelPoints[1]?.y || pixelPoints[0].y;
        const tpY = pixelPoints[2]?.y || pixelPoints[0].y;

        const entryPrice = pricePoints[0].price;
        const slPrice = pricePoints[1]?.price || entryPrice;
        const tpPrice = pricePoints[2]?.price || entryPrice;

        const position = calculateLongPosition(entryPrice, slPrice, tpPrice);

        // Loss zone (below entry) - Red with gradient effect
        ctx.fillStyle = 'rgba(239, 68, 68, 0.15)';
        ctx.fillRect(minX, entryY, width, slY - entryY);

        // Profit zone (above entry) - Green with gradient effect
        if (pixelPoints.length >= 3) {
            ctx.fillStyle = 'rgba(16, 185, 129, 0.15)';
            ctx.fillRect(minX, tpY, width, entryY - tpY);
        }

        // Entry line - solid green
        ctx.strokeStyle = '#10b981';
        ctx.lineWidth = 2;
        ctx.setLineDash([]);
        ctx.beginPath();
        ctx.moveTo(minX, entryY);
        ctx.lineTo(maxX, entryY);
        ctx.stroke();

        // SL line - dashed red
        ctx.strokeStyle = '#ef4444';
        ctx.lineWidth = 1.5;
        ctx.setLineDash([6, 4]);
        ctx.beginPath();
        ctx.moveTo(minX, slY);
        ctx.lineTo(maxX, slY);
        ctx.stroke();

        // TP line - dashed green
        if (pixelPoints.length >= 3) {
            ctx.strokeStyle = '#10b981';
            ctx.lineWidth = 1.5;
            ctx.setLineDash([6, 4]);
            ctx.beginPath();
            ctx.moveTo(minX, tpY);
            ctx.lineTo(maxX, tpY);
            ctx.stroke();
        }

        // Right-side price labels (TradingView style)
        // Position: Far left of the handle to prevent overlap
        ctx.setLineDash([]);
        ctx.font = 'bold 10px Inter, sans-serif';

        // Label position: to the LEFT of circle handles (handles are at maxX-40)
        const labelX = maxX - 130; // Moved further left

        // Entry price label
        ctx.fillStyle = '#10b981';
        ctx.fillRect(labelX - 35, entryY - 8, 70, 16);
        ctx.fillStyle = '#fff';
        ctx.textAlign = 'center';
        ctx.fillText(`${formatPrice(entryPrice)}`, labelX, entryY + 4);

        // SL price label
        ctx.fillStyle = '#ef4444';
        ctx.fillRect(labelX - 35, slY - 8, 70, 16);
        ctx.fillStyle = '#fff';
        ctx.fillText(`${formatPrice(slPrice)}`, labelX, slY + 4);

        // TP price label
        if (pixelPoints.length >= 3) {
            ctx.fillStyle = '#10b981';
            ctx.fillRect(labelX - 35, tpY - 8, 70, 16);
            ctx.fillStyle = '#fff';
            ctx.fillText(`${formatPrice(tpPrice)}`, labelX, tpY + 4);
        }

        // === PROJECTION LINES - extend to right edge of canvas ===
        const canvasWidth = ctx.canvas.width;
        const projectionStartX = maxX + 5;

        if (projectionStartX < canvasWidth - 80) {
            ctx.save();
            ctx.globalAlpha = 0.4;

            // Entry projection line
            ctx.strokeStyle = '#10b981';
            ctx.lineWidth = 1;
            ctx.setLineDash([4, 4]);
            ctx.beginPath();
            ctx.moveTo(projectionStartX, entryY);
            ctx.lineTo(canvasWidth - 80, entryY);
            ctx.stroke();

            // SL projection line
            ctx.strokeStyle = '#ef4444';
            ctx.beginPath();
            ctx.moveTo(projectionStartX, slY);
            ctx.lineTo(canvasWidth - 80, slY);
            ctx.stroke();

            // TP projection line
            if (pixelPoints.length >= 3) {
                ctx.strokeStyle = '#10b981';
                ctx.beginPath();
                ctx.moveTo(projectionStartX, tpY);
                ctx.lineTo(canvasWidth - 80, tpY);
                ctx.stroke();
            }

            // Right margin price labels for projection
            ctx.globalAlpha = 0.6;
            ctx.setLineDash([]);
            ctx.font = '9px Inter, sans-serif';
            ctx.textAlign = 'right';

            // Entry projection label
            ctx.fillStyle = '#10b981';
            ctx.fillText(`▸ ${formatPrice(entryPrice)}`, canvasWidth - 85, entryY + 3);

            // SL projection label
            ctx.fillStyle = '#ef4444';
            ctx.fillText(`▸ ${formatPrice(slPrice)}`, canvasWidth - 85, slY + 3);

            // TP projection label
            if (pixelPoints.length >= 3) {
                ctx.fillStyle = '#10b981';
                ctx.fillText(`▸ ${formatPrice(tpPrice)}`, canvasWidth - 85, tpY + 3);
            }

            ctx.restore();
        }

        // Info Panel REMOVED as per user request (was blocking interactions)

        // Draw drag handles when selected
        if (isSelected && pixelPoints.length >= 3) {
            const handleRadius = 12; // INCREASED from 6 for easier clicking
            const handleX = maxX - 40;

            // Entry handle - larger and more visible
            ctx.beginPath();
            ctx.arc(handleX, entryY, handleRadius, 0, Math.PI * 2);
            ctx.fillStyle = '#10b981';
            ctx.fill();
            ctx.strokeStyle = '#fff';
            ctx.lineWidth = 3; // Thicker border
            ctx.stroke();

            // SL handle - larger and more visible
            ctx.beginPath();
            ctx.arc(handleX, slY, handleRadius, 0, Math.PI * 2);
            ctx.fillStyle = '#ef4444';
            ctx.fill();
            ctx.strokeStyle = '#fff';
            ctx.stroke();

            // TP handle - larger and more visible
            ctx.beginPath();
            ctx.arc(handleX, tpY, handleRadius, 0, Math.PI * 2);
            ctx.fillStyle = '#10b981';
            ctx.fill();
            ctx.strokeStyle = '#fff';
            ctx.stroke();

            // Add resize cursor hint text
            ctx.font = '9px Inter, sans-serif';
            ctx.fillStyle = 'rgba(255,255,255,0.7)';
            ctx.textAlign = 'right';
            ctx.fillText('⇅ Drag to adjust', maxX - 50, entryY - 20);

            // Left edge resize handle (vertical bar)
            const centerY = (Math.min(entryY, slY, tpY) + Math.max(entryY, slY, tpY)) / 2;
            ctx.fillStyle = '#3b82f6';
            ctx.fillRect(minX - 4, centerY - 15, 8, 30);
            ctx.strokeStyle = '#fff';
            ctx.lineWidth = 1;
            ctx.strokeRect(minX - 4, centerY - 15, 8, 30);

            // Right edge resize handle (vertical bar)
            ctx.fillStyle = '#3b82f6';
            ctx.fillRect(maxX - 4, centerY - 15, 8, 30);
            ctx.strokeStyle = '#fff';
            ctx.strokeRect(maxX - 4, centerY - 15, 8, 30);

            // Resize hints
            ctx.font = '8px Inter, sans-serif';
            ctx.fillStyle = 'rgba(255,255,255,0.6)';
            ctx.textAlign = 'center';
            ctx.fillText('◀▶', minX, centerY + 30);
            ctx.fillText('◀▶', maxX, centerY + 30);
        }
    };

    // Short Position renderer - TradingView Style
    const renderShortPosition = (ctx, pixelPoints, pricePoints, isSelected, drawing = {}) => {
        if (pixelPoints.length < 2) return;

        // FIX: Use drawing.width for correct right edge calculation involves time
        const allX = pixelPoints.map(p => p.x);
        const minX = Math.min(...allX);

        // Calculate max X from time width
        let maxX;
        const widthSeconds = drawing.width || (50 * 60 * 60); // Default 50h
        const endTime = drawing.startTime + widthSeconds;
        const endX = timeToCoordinate(endTime);

        if (endX !== null) {
            maxX = endX;
        } else {
            maxX = Math.max(...allX) + 180; // Fallback
        }

        const width = maxX - minX;

        const entryY = pixelPoints[0].y;
        const slY = pixelPoints[1]?.y || pixelPoints[0].y;
        const tpY = pixelPoints[2]?.y || pixelPoints[0].y;

        const entryPrice = pricePoints[0].price;
        const slPrice = pricePoints[1]?.price || entryPrice;
        const tpPrice = pricePoints[2]?.price || entryPrice;

        const position = calculateShortPosition(entryPrice, slPrice, tpPrice);

        // Loss zone (above entry for short) - Red with gradient effect
        ctx.fillStyle = 'rgba(239, 68, 68, 0.15)';
        ctx.fillRect(minX, slY, width, entryY - slY);

        // Profit zone (below entry for short) - Green with gradient effect
        if (pixelPoints.length >= 3) {
            ctx.fillStyle = 'rgba(16, 185, 129, 0.15)';
            ctx.fillRect(minX, entryY, width, tpY - entryY);
        }

        // Entry line - solid red
        ctx.strokeStyle = '#ef4444';
        ctx.lineWidth = 2;
        ctx.setLineDash([]);
        ctx.beginPath();
        ctx.moveTo(minX, entryY);
        ctx.lineTo(maxX, entryY);
        ctx.stroke();

        // SL line - dashed red
        ctx.strokeStyle = '#ef4444';
        ctx.lineWidth = 1.5;
        ctx.setLineDash([6, 4]);
        ctx.beginPath();
        ctx.moveTo(minX, slY);
        ctx.lineTo(maxX, slY);
        ctx.stroke();

        // TP line - dashed green
        if (pixelPoints.length >= 3) {
            ctx.strokeStyle = '#10b981';
            ctx.lineWidth = 1.5;
            ctx.setLineDash([6, 4]);
            ctx.beginPath();
            ctx.moveTo(minX, tpY);
            ctx.lineTo(maxX, tpY);
            ctx.stroke();
        }

        // Right-side price labels (TradingView style)
        // Position: Far left of the handle to prevent overlap
        ctx.setLineDash([]);
        ctx.font = 'bold 10px Inter, sans-serif';

        // Label position: to the LEFT of circle handles (handles are at maxX-40)
        const labelX = maxX - 130; // Moved further left

        // Entry price label
        ctx.fillStyle = '#ef4444';
        ctx.fillRect(labelX - 35, entryY - 8, 70, 16);
        ctx.fillStyle = '#fff';
        ctx.textAlign = 'center';
        ctx.fillText(`${formatPrice(entryPrice)}`, labelX, entryY + 4);

        // SL price label (above entry for short)
        ctx.fillStyle = '#ef4444';
        ctx.fillRect(labelX - 35, slY - 8, 70, 16);
        ctx.fillStyle = '#fff';
        ctx.fillText(`${formatPrice(slPrice)}`, labelX, slY + 4);

        // TP price label (below entry for short)
        if (pixelPoints.length >= 3) {
            ctx.fillStyle = '#10b981';
            ctx.fillRect(labelX - 35, tpY - 8, 70, 16);
            ctx.fillStyle = '#fff';
            ctx.fillText(`${formatPrice(tpPrice)}`, labelX, tpY + 4);
        }

        // === PROJECTION LINES - extend to right edge of canvas ===
        const canvasWidth = ctx.canvas.width;
        const projectionStartX = maxX + 5;

        if (projectionStartX < canvasWidth - 80) {
            ctx.save();
            ctx.globalAlpha = 0.4;

            // Entry projection line
            ctx.strokeStyle = '#ef4444';
            ctx.lineWidth = 1;
            ctx.setLineDash([4, 4]);
            ctx.beginPath();
            ctx.moveTo(projectionStartX, entryY);
            ctx.lineTo(canvasWidth - 80, entryY);
            ctx.stroke();

            // SL projection line
            ctx.strokeStyle = '#ef4444';
            ctx.beginPath();
            ctx.moveTo(projectionStartX, slY);
            ctx.lineTo(canvasWidth - 80, slY);
            ctx.stroke();

            // TP projection line
            if (pixelPoints.length >= 3) {
                ctx.strokeStyle = '#10b981';
                ctx.beginPath();
                ctx.moveTo(projectionStartX, tpY);
                ctx.lineTo(canvasWidth - 80, tpY);
                ctx.stroke();
            }

            // Right margin price labels for projection
            ctx.globalAlpha = 0.6;
            ctx.setLineDash([]);
            ctx.font = '9px Inter, sans-serif';
            ctx.textAlign = 'right';

            // Entry projection label
            ctx.fillStyle = '#ef4444';
            ctx.fillText(`▸ ${formatPrice(entryPrice)}`, canvasWidth - 85, entryY + 3);

            // SL projection label
            ctx.fillStyle = '#ef4444';
            ctx.fillText(`▸ ${formatPrice(slPrice)}`, canvasWidth - 85, slY + 3);

            // TP projection label
            if (pixelPoints.length >= 3) {
                ctx.fillStyle = '#10b981';
                ctx.fillText(`▸ ${formatPrice(tpPrice)}`, canvasWidth - 85, tpY + 3);
            }

            ctx.restore();
        }

        // Info Panel REMOVED as per user request (was blocking interactions)

        // Draw drag handles when selected
        if (isSelected && pixelPoints.length >= 3) {
            const handleRadius = 12; // INCREASED from 6 for easier clicking
            const handleX = maxX - 40;

            // Entry handle - larger and more visible
            ctx.beginPath();
            ctx.arc(handleX, entryY, handleRadius, 0, Math.PI * 2);
            ctx.fillStyle = '#ef4444';
            ctx.fill();
            ctx.strokeStyle = '#fff';
            ctx.lineWidth = 3; // Thicker border
            ctx.stroke();

            // SL handle - larger and more visible
            ctx.beginPath();
            ctx.arc(handleX, slY, handleRadius, 0, Math.PI * 2);
            ctx.fillStyle = '#ef4444';
            ctx.fill();
            ctx.strokeStyle = '#fff';
            ctx.stroke();

            // TP handle - larger and more visible
            ctx.beginPath();
            ctx.arc(handleX, tpY, handleRadius, 0, Math.PI * 2);
            ctx.fillStyle = '#10b981';
            ctx.fill();
            ctx.strokeStyle = '#fff';
            ctx.stroke();

            // Add resize cursor hint text
            ctx.font = '9px Inter, sans-serif';
            ctx.fillStyle = 'rgba(255,255,255,0.7)';
            ctx.textAlign = 'right';
            ctx.fillText('⇅ Drag to adjust', maxX - 50, entryY - 20);

            // Left edge resize handle (vertical bar)
            const centerY = (Math.min(entryY, slY, tpY) + Math.max(entryY, slY, tpY)) / 2;
            ctx.fillStyle = '#3b82f6';
            ctx.fillRect(minX - 4, centerY - 15, 8, 30);
            ctx.strokeStyle = '#fff';
            ctx.lineWidth = 1;
            ctx.strokeRect(minX - 4, centerY - 15, 8, 30);

            // Right edge resize handle (vertical bar)
            ctx.fillStyle = '#3b82f6';
            ctx.fillRect(maxX - 4, centerY - 15, 8, 30);
            ctx.strokeStyle = '#fff';
            ctx.strokeRect(maxX - 4, centerY - 15, 8, 30);

            // Resize hints
            ctx.font = '8px Inter, sans-serif';
            ctx.fillStyle = 'rgba(255,255,255,0.6)';
            ctx.textAlign = 'center';
            ctx.fillText('◀▶', minX, centerY + 30);
            ctx.fillText('◀▶', maxX, centerY + 30);
        }
    };

    // Fibonacci Fan renderer
    const renderFibFan = (ctx, pixelPoints, isSelected) => {
        if (pixelPoints.length < 2) return;

        const canvas = canvasRef.current;
        const [origin, target] = pixelPoints;
        const fanLines = calculateFibFanLines(origin, target, canvas.width);

        fanLines.forEach((line, index) => {
            ctx.strokeStyle = isSelected ? DRAWING_COLORS.selected : DRAWING_COLORS.fibFan;
            ctx.lineWidth = 1;
            ctx.setLineDash([4, 4]);
            ctx.globalAlpha = 0.5 + (index * 0.1);

            ctx.beginPath();
            ctx.moveTo(line.start.x, line.start.y);
            ctx.lineTo(line.end.x, line.end.y);
            ctx.stroke();

            // Label
            ctx.globalAlpha = 1;
            ctx.fillStyle = DRAWING_COLORS.fibFan;
            ctx.font = '10px Inter, sans-serif';
            ctx.fillText(line.label, line.end.x - 40, line.end.y - 5);
        });

        // Draw origin-target line
        ctx.strokeStyle = DRAWING_COLORS.fibFan;
        ctx.lineWidth = 2;
        ctx.setLineDash([]);
        ctx.globalAlpha = 1;
        ctx.beginPath();
        ctx.moveTo(origin.x, origin.y);
        ctx.lineTo(target.x, target.y);
        ctx.stroke();
    };

    // XABCD Pattern renderer
    const renderXABCD = (ctx, pixelPoints, pricePoints, isSelected) => {
        if (pixelPoints.length < 2) return;

        const labels = ['X', 'A', 'B', 'C', 'D'];

        // Draw lines connecting points
        ctx.strokeStyle = isSelected ? DRAWING_COLORS.selected : DRAWING_COLORS.xabcd;
        ctx.lineWidth = 2;
        ctx.setLineDash([]);

        ctx.beginPath();
        ctx.moveTo(pixelPoints[0].x, pixelPoints[0].y);
        for (let i = 1; i < pixelPoints.length; i++) {
            ctx.lineTo(pixelPoints[i].x, pixelPoints[i].y);
        }
        ctx.stroke();

        // Fill pattern area
        if (pixelPoints.length >= 4) {
            ctx.fillStyle = DRAWING_COLORS.xabcdFill;
            ctx.beginPath();
            ctx.moveTo(pixelPoints[0].x, pixelPoints[0].y);
            for (let i = 1; i < pixelPoints.length; i++) {
                ctx.lineTo(pixelPoints[i].x, pixelPoints[i].y);
            }
            ctx.closePath();
            ctx.fill();
        }

        // Draw points with labels
        pixelPoints.forEach((point, index) => {
            // Point circle
            ctx.fillStyle = DRAWING_COLORS.xabcd;
            ctx.beginPath();
            ctx.arc(point.x, point.y, 6, 0, Math.PI * 2);
            ctx.fill();

            // Inner circle
            ctx.fillStyle = '#16161f';
            ctx.beginPath();
            ctx.arc(point.x, point.y, 3, 0, Math.PI * 2);
            ctx.fill();

            // Label
            const label = labels[index] || '';
            ctx.fillStyle = '#fff';
            ctx.font = 'bold 12px Inter, sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText(label, point.x, point.y - 12);
        });

        // Pattern type and ratios
        if (pricePoints.length >= 5) {
            const pattern = calculateXABCDPattern(pricePoints);
            if (pattern) {
                ctx.fillStyle = DRAWING_COLORS.xabcd;
                ctx.font = 'bold 14px Inter, sans-serif';
                ctx.textAlign = 'left';
                ctx.fillText(pattern.patternType, pixelPoints[0].x, pixelPoints[0].y - 30);

                // Show ratios
                ctx.font = '10px Inter, sans-serif';
                ctx.fillText(`AB/XA: ${pattern.ratios.AB_XA}`, pixelPoints[1].x + 10, pixelPoints[1].y);
                ctx.fillText(`BC/AB: ${pattern.ratios.BC_AB}`, pixelPoints[2].x + 10, pixelPoints[2].y);
            }
        }
    };

    // Determine tool type
    const dragTools = ['rectangle', 'fibonacci', 'fibFan'];
    const clickTools = ['longPosition', 'shortPosition', 'xabcd'];

    // Update cursor style on canvas
    useEffect(() => {
        if (canvasRef.current) {
            canvasRef.current.style.cursor = cursor;
        }
    }, [cursor]);

    // Helper: Find if mouse is on any position handle, body (move), or edge (resize)
    const findDragHandle = useCallback((mouseX, mouseY) => {
        // Iterate REVERSE so we hit the topmost drawing first
        for (let i = drawings.length - 1; i >= 0; i--) {
            const drawing = drawings[i];
            const isSelected = drawing.id === selectedDrawing;

            // Get pixel positions
            const pixelPoints = drawing.points.map(p => priceTimeToPixel(p.price, p.time)).filter(Boolean);
            if (pixelPoints.length < 2) continue;

            const allX = pixelPoints.map(p => p.x);
            const allY = pixelPoints.map(p => p.y);
            const minX = Math.min(...allX);
            const maxX = Math.max(...allX);
            const minY = Math.min(...allY);
            const maxY = Math.max(...allY);

            // --- TYPE SPECIFIC HANDLES ---

            if (['longPosition', 'shortPosition'].includes(drawing.type)) {
                if (drawing.points.length < 3) continue;

                // Position tool bounds

                // Calculate max X from time width (Seconds)
                let posMaxX;
                const widthSeconds = drawing.width || (50 * 60 * 60);
                const endTime = drawing.startTime + widthSeconds;
                const endX = timeToCoordinate(endTime);

                if (endX !== null) {
                    posMaxX = endX;
                } else {
                    posMaxX = maxX + 180; // Fallback
                }

                let posMinX = minX - 20;  // Add some padding to left

                if (isSelected) {
                    // Logic to find the Right-Side handle X position (Robust)
                    // Must match render/mousemove logic: startTime + width
                    const startTime = drawing.startTime || drawing.points[0].time;
                    const widthSeconds = drawing.width || (50 * 60 * 60);
                    const endTime = startTime + widthSeconds;

                    // Calculate the right edge of the position box
                    let rightEdgeX;
                    const endPix = priceTimeToPixel(drawing.points[0].price, endTime);
                    if (endPix) {
                        rightEdgeX = endPix.x;
                    } else {
                        rightEdgeX = posMaxX; // Fallback
                    }

                    // Visual handles are drawn at (rightEdgeX - 40)
                    const handleX = rightEdgeX - 40;

                    const entryY = pixelPoints[0].y;
                    const slY = pixelPoints[1].y;
                    const tpY = pixelPoints[2].y;

                    // NEW APPROACH: Make ENTIRE horizontal line clickable for SL/TP
                    // This gives a MUCH larger click target than just the circle handle
                    const lineHitHeight = 20; // 20px above and below the line
                    const leftBound = minX - 10;
                    const rightBound = rightEdgeX + 10;

                    console.log('[DEBUG findDragHandle] Position Tool Line Detection:', {
                        drawingId: drawing.id,
                        mouseX, mouseY,
                        leftBound, rightBound,
                        entryY, slY, tpY,
                        lineHitHeight,
                    });

                    // 1. Check if mouse is on SL line (ENTIRE width)
                    if (mouseX >= leftBound && mouseX <= rightBound &&
                        mouseY >= slY - lineHitHeight && mouseY <= slY + lineHitHeight) {
                        console.log('[DEBUG findDragHandle] HIT: SL Line (full width)');
                        return { drawingId: drawing.id, pointIndex: 1, pointType: HANDLE_TYPES.STOP_LOSS };
                    }

                    // 2. Check if mouse is on TP line (ENTIRE width)
                    if (mouseX >= leftBound && mouseX <= rightBound &&
                        mouseY >= tpY - lineHitHeight && mouseY <= tpY + lineHitHeight) {
                        console.log('[DEBUG findDragHandle] HIT: TP Line (full width)');
                        return { drawingId: drawing.id, pointIndex: 2, pointType: HANDLE_TYPES.TAKE_PROFIT };
                    }

                    // 3. Check if mouse is on Entry line (ENTIRE width)
                    if (mouseX >= leftBound && mouseX <= rightBound &&
                        mouseY >= entryY - lineHitHeight && mouseY <= entryY + lineHitHeight) {
                        console.log('[DEBUG findDragHandle] HIT: Entry Line (full width)');
                        return { drawingId: drawing.id, pointIndex: 0, pointType: HANDLE_TYPES.ENTRY };
                    }

                    // 4. Check edges for resize (only when selected)
                    if (isNearHandleUtil(mouseX, mouseY, posMinX, (minY + maxY) / 2, 20)) {
                        return { drawingId: drawing.id, pointIndex: -1, pointType: HANDLE_TYPES.RESIZE_LEFT };
                    }
                    if (isNearHandleUtil(mouseX, mouseY, rightEdgeX, (minY + maxY) / 2, 20)) {
                        return { drawingId: drawing.id, pointIndex: -1, pointType: HANDLE_TYPES.RESIZE_RIGHT };
                    }
                }

                // ALWAYS check for line hits (SL/TP/Entry) - NO selection required
                // This allows direct manipulation without needing to select first
                const startTime = drawing.startTime || drawing.points[0].time;
                const widthSecondsAlt = drawing.width || (50 * 60 * 60);
                const endTimeAlt = startTime + widthSecondsAlt;
                const endPixAlt = priceTimeToPixel(drawing.points[0].price, endTimeAlt);
                const rightEdgeXAlt = endPixAlt ? endPixAlt.x : posMaxX;

                const entryYAlt = pixelPoints[0].y;
                const slYAlt = pixelPoints[1].y;
                const tpYAlt = pixelPoints[2].y;

                const lineHitHeightAlt = 25; // 25px above and below the line
                const leftBoundAlt = minX - 10;
                const rightBoundAlt = rightEdgeXAlt + 10;

                // Check SL line (ENTIRE width) - PRIORITY because typically at edge
                if (mouseX >= leftBoundAlt && mouseX <= rightBoundAlt &&
                    mouseY >= slYAlt - lineHitHeightAlt && mouseY <= slYAlt + lineHitHeightAlt) {
                    console.log('[DEBUG findDragHandle] HIT: SL Line (no selection needed)');
                    return { drawingId: drawing.id, pointIndex: 1, pointType: HANDLE_TYPES.STOP_LOSS };
                }

                // Check TP line (ENTIRE width)
                if (mouseX >= leftBoundAlt && mouseX <= rightBoundAlt &&
                    mouseY >= tpYAlt - lineHitHeightAlt && mouseY <= tpYAlt + lineHitHeightAlt) {
                    console.log('[DEBUG findDragHandle] HIT: TP Line (no selection needed)');
                    return { drawingId: drawing.id, pointIndex: 2, pointType: HANDLE_TYPES.TAKE_PROFIT };
                }

                // Check Entry line (ENTIRE width)
                if (mouseX >= leftBoundAlt && mouseX <= rightBoundAlt &&
                    mouseY >= entryYAlt - lineHitHeightAlt && mouseY <= entryYAlt + lineHitHeightAlt) {
                    console.log('[DEBUG findDragHandle] HIT: Entry Line (no selection needed)');
                    return { drawingId: drawing.id, pointIndex: 0, pointType: HANDLE_TYPES.ENTRY };
                }

                // Check body for move
                if (mouseX >= posMinX && mouseX <= posMaxX && mouseY >= minY && mouseY <= maxY) {
                    return { drawingId: drawing.id, pointIndex: -1, pointType: HANDLE_TYPES.MOVE };
                }
            } else if (drawing.type === 'xabcd') {
                // --- XABCD Pattern Handles ---

                // Check individual point handles when selected
                if (isSelected) {
                    for (let i = 0; i < pixelPoints.length; i++) {
                        if (isNearHandleUtil(mouseX, mouseY, pixelPoints[i].x, pixelPoints[i].y)) {
                            const pointLabels = ['POINT_X', 'POINT_A', 'POINT_B', 'POINT_C', 'POINT_D'];
                            return { drawingId: drawing.id, pointIndex: i, pointType: pointLabels[i] || HANDLE_TYPES.MOVE };
                        }
                    }
                }

                // Check body for selection/move
                const buffer = 10;
                if (mouseX >= minX - buffer && mouseX <= maxX + buffer && mouseY >= minY - buffer && mouseY <= maxY + buffer) {
                    return { drawingId: drawing.id, pointIndex: -1, pointType: HANDLE_TYPES.MOVE };
                }
            } else {
                // --- GENERIC HANDLES (Rectangle, Fibonacci, etc.) ---

                // If selected, check specific handles if we add them later (currently just Move)

                // Check bounds for selection/move
                // Add a small buffer for thin lines
                const buffer = 5;
                if (mouseX >= minX - buffer && mouseX <= maxX + buffer && mouseY >= minY - buffer && mouseY <= maxY + buffer) {
                    return { drawingId: drawing.id, pointIndex: -1, pointType: HANDLE_TYPES.MOVE };
                }
            }
        }

        return null;
    }, [drawings, selectedDrawing, priceTimeToPixel]);

    // Handle mouse move - Magnet Mode + FSM + Hover
    const handleMouseMove = useCallback((e) => {
        const rect = canvasRef.current.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;
        lastMousePosition.current = { x: mouseX, y: mouseY };

        let finalX = mouseX;
        let finalY = mouseY;
        let snappedPriceTime = null;

        // Apply Magnet Mode if enabled and drawing/dragging
        if (magnetMode && (isDrawing || (isDraggingRef.current && dragState))) {
            const result = applyMagnet(
                mouseX,
                mouseY,
                candleData,
                pixelToIndex,
                priceToCoordinate,
                indexToPixel,
                magnetThreshold
            );

            if (result.snapped) {
                finalX = result.x;
                finalY = result.y;
                snappedPriceTime = { price: result.price, time: result.time };
            }
        }

        // Convert to Price/Time if not snapped
        if (!snappedPriceTime) {
            snappedPriceTime = pixelToPriceTime(finalX, finalY);
        }

        // 1. Handle Dragging (Priority)
        // DEBUG: Log drag state during move
        if (isDraggingRef.current || dragState) {
            console.log('DRAG CHECK in handleMouseMove:', {
                isDraggingRef: isDraggingRef.current,
                dragState: dragState,
                hasOnUpdateDraggedPoint: !!onUpdateDraggedPoint,
                conditionMet: !!(isDraggingRef.current && dragState && onUpdateDraggedPoint)
            });
        }
        if (isDraggingRef.current && dragState && onUpdateDraggedPoint) {
            if (snappedPriceTime) {
                onUpdateDraggedPoint(snappedPriceTime);
            }
            return;
        }

        // 2. Handle Drawing (Preview)
        if (isDrawing && onUpdateDrawing) {
            if (snappedPriceTime) {
                onUpdateDrawing(snappedPriceTime);
            }
            setInteractionState(INTERACTION_STATES.DRAWING);
            setCursor(getCursor(INTERACTION_STATES.DRAWING));
            return;
        }

        // 3. Handle Hover over Close Button
        let foundCloseButton = null;
        for (let i = drawings.length - 1; i >= 0; i--) {
            const drawing = drawings[i];
            const pixelPoints = drawing.points.map(p => priceTimeToPixel(p.price, p.time)).filter(Boolean);
            const btnPos = getCloseButtonPosition(drawing, pixelPoints);
            if (btnPos) {
                // Check distance to button center
                const dx = mouseX - btnPos.x;
                const dy = mouseY - btnPos.y;
                if (dx * dx + dy * dy <= 225) { // 15px radius squared (was 10px)
                    foundCloseButton = drawing.id;
                    break;
                }
            }
        }

        if (foundCloseButton) {
            setHoveredCloseButton(foundCloseButton);
            setCursor('pointer');
            return; // Prioritize close button
        } else {
            if (hoveredCloseButton) setHoveredCloseButton(null);
        }

        // 4. Handle Hover (Idle/Selected)
        const handle = findDragHandle(mouseX, mouseY);
        if (handle) {
            if (onSetHoveredHandle) onSetHoveredHandle({ drawingId: handle.drawingId, handleType: handle.pointType });
            setCursor(getCursor(INTERACTION_STATES.SELECTED, handle.pointType));
        } else {
            if (onSetHoveredHandle) onSetHoveredHandle(null);

            if (activeTool) {
                setInteractionState(INTERACTION_STATES.PREPARE_DRAW);
                setCursor(getCursor(INTERACTION_STATES.PREPARE_DRAW));
            } else if (selectedDrawing) {
                setInteractionState(INTERACTION_STATES.SELECTED);
                setCursor(getCursor(INTERACTION_STATES.SELECTED));
            } else {
                setInteractionState(INTERACTION_STATES.IDLE);
                setCursor(getCursor(INTERACTION_STATES.IDLE));
            }
        }

    }, [magnetMode, isDrawing, dragState, onUpdateDraggedPoint, onUpdateDrawing, findDragHandle, activeTool, selectedDrawing, candleData, pixelToIndex, priceToCoordinate, indexToPixel, magnetThreshold, onSetHoveredHandle, pixelToPriceTime]);

    // Refs for stable access in event listeners
    const drawingsRef = useRef(drawings);
    const activeToolRef = useRef(activeTool);

    useEffect(() => {
        drawingsRef.current = drawings;
    }, [drawings]);

    useEffect(() => {
        activeToolRef.current = activeTool;
    }, [activeTool]);

    // Track if an action was handled in MouseDown to prevent Click conflicts
    const isActionHandledRef = useRef(false);

    const handleMouseDown = useCallback((e) => {
        console.log('[DEBUG] handleMouseDown triggered, activeTool:', activeTool);
        const rect = canvasRef.current.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;

        // Check for close button click - perform real-time hit detection
        // instead of relying only on hoveredCloseButton state which may be stale
        for (let i = drawings.length - 1; i >= 0; i--) {
            const drawing = drawings[i];
            const pixelPoints = drawing.points.map(p => priceTimeToPixel(p.price, p.time)).filter(Boolean);
            const btnPos = getCloseButtonPosition(drawing, pixelPoints);

            if (btnPos && Number.isFinite(btnPos.x) && Number.isFinite(btnPos.y)) {
                const dx = mouseX - btnPos.x;
                const dy = mouseY - btnPos.y;
                const distSq = dx * dx + dy * dy;

                if (distSq <= 225) { // 15px radius squared
                    if (onDeleteDrawing) {
                        isActionHandledRef.current = true; // Mark action as handled
                        onDeleteDrawing(drawing.id);
                        setHoveredCloseButton(null);
                        e.preventDefault();
                        e.stopPropagation();
                        return;
                    } else {
                        // onDeleteDrawing is missing!
                    }
                }
            }
        }

        // Apply Magnet for start point
        let finalX = mouseX;
        let finalY = mouseY;
        let snappedPriceTime = null;

        if (magnetMode) {
            const result = applyMagnet(
                mouseX,
                mouseY,
                candleData,
                pixelToIndex,
                priceToCoordinate,
                indexToPixel,
                magnetThreshold
            );
            if (result.snapped) {
                finalX = result.x;
                finalY = result.y;
                snappedPriceTime = { price: result.price, time: result.time };
            }
        }

        if (!snappedPriceTime) {
            snappedPriceTime = pixelToPriceTime(finalX, finalY);
        }

        // 1. Check for Drag Handle click
        const handle = findDragHandle(mouseX, mouseY);
        if (handle) {
            // Select the drawing if not already selected
            if (handle.drawingId !== selectedDrawing && onSelectDrawing) {
                onSelectDrawing(handle.drawingId);
            }

            if (onStartDrag) {
                isDraggingRef.current = true;
                isActionHandledRef.current = true; // Mark action as handled (drag start)
                onStartDrag(handle.drawingId, handle.pointIndex, handle.pointType);

                const nextState = getNextState(INTERACTION_STATES.SELECTED, 'HANDLE_MOUSEDOWN', { handleType: handle.pointType });
                setInteractionState(nextState);
                setCursor(getCursor(nextState, handle.pointType, true));

                e.preventDefault();
                return;
            }
        }

        // 2. Drawing Tools - Only start drag tools on mousedown
        if (activeTool && onStartDrawing && DRAG_TOOLS.includes(activeTool)) {
            if (snappedPriceTime) {
                onStartDrawing(snappedPriceTime);
                setInteractionState(INTERACTION_STATES.DRAWING);
            }
        }
    }, [magnetMode, candleData, pixelToIndex, priceToCoordinate, indexToPixel, magnetThreshold, pixelToPriceTime, findDragHandle, onStartDrag, activeTool, onStartDrawing, onDeleteDrawing, selectedDrawing, onSelectDrawing, drawings, priceTimeToPixel, getCloseButtonPosition]);


    const handleMouseUp = useCallback((e) => {
        // End drag if dragging
        if (isDraggingRef.current && onEndDrag) {
            isDraggingRef.current = false;
            // Note: Don't set isActionHandledRef to false here, wait for Click event to consume it
            onEndDrag();

            // FSM Update
            setInteractionState(INTERACTION_STATES.SELECTED);
            setCursor(getCursor(INTERACTION_STATES.SELECTED));
            return;
        }

        if (!activeTool) return;

        if (DRAG_TOOLS.includes(activeTool) && isDrawing && currentDrawing) {
            onCompleteDrawing(null); // Points are already in currentDrawing
            setInteractionState(INTERACTION_STATES.SELECTED);
            setCursor(getCursor(INTERACTION_STATES.SELECTED));
        }
    }, [activeTool, isDrawing, currentDrawing, onCompleteDrawing, onEndDrag]);

    // Click handler for multi-point tools and close buttons
    const handleClick = useCallback((e) => {
        console.log('[DEBUG] handleClick triggered, activeTool:', activeTool);
        // If an action was handled in MouseDown (like Delete or Drag Start), ignore this click
        if (isActionHandledRef.current) {
            console.log('[DEBUG] handleClick - action already handled, skipping');
            isActionHandledRef.current = false; // Reset
            return;
        }

        const rect = canvasRef.current.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;

        if (hoveredCloseButton && onDeleteDrawing) {
            onDeleteDrawing(hoveredCloseButton);
            setHoveredCloseButton(null); // Reset
            return;
        }

        // Check if we are clicking on an existing handle/drawing
        // If so, prioritize selection/interaction over creating a new drawing point
        if (findDragHandle(mouseX, mouseY)) {
            return;
        }

        if (!activeTool) return;

        // Only handle click for click-based tools
        if (!CLICK_TOOLS.includes(activeTool)) return;

        // Apply Magnet
        let finalX = mouseX;
        let finalY = mouseY;
        let snappedPriceTime = null;

        if (magnetMode) {
            const result = applyMagnet(
                mouseX,
                mouseY,
                candleData,
                pixelToIndex,
                priceToCoordinate,
                indexToPixel,
                magnetThreshold
            );

            if (result.snapped) {
                finalX = result.x;
                finalY = result.y;
                snappedPriceTime = { price: result.price, time: result.time };
            }
        }

        if (!snappedPriceTime) {
            snappedPriceTime = pixelToPriceTime(finalX, finalY);
        }

        if (!snappedPriceTime) return;

        const requiredPoints = { longPosition: 3, shortPosition: 3, xabcd: 5 };

        if (!currentDrawing) {
            // Start new drawing with first point
            onStartDrawing(snappedPriceTime);
            setInteractionState(INTERACTION_STATES.DRAWING);
        } else {
            // Use confirmedCount to track actual clicks (excluding preview point)
            const confirmedClicks = currentDrawing.confirmedCount || currentDrawing.points.length;

            if (confirmedClicks < requiredPoints[activeTool] - 1) {
                // Add intermediate point (not final yet)
                onAddPoint(snappedPriceTime);
            } else {
                // Complete the drawing with final point
                onCompleteDrawing(snappedPriceTime);
                setInteractionState(INTERACTION_STATES.SELECTED);
            }
        }
    }, [activeTool, currentDrawing, pixelToPriceTime, onStartDrawing, onAddPoint, onCompleteDrawing, magnetMode, candleData, pixelToIndex, priceToCoordinate, indexToPixel, magnetThreshold, hoveredCloseButton, onDeleteDrawing, findDragHandle]);

    // Animation loop for smooth rendering
    useEffect(() => {
        const animate = () => {
            renderDrawings();
            animationRef.current = requestAnimationFrame(animate);
        };

        animate();

        return () => {
            if (animationRef.current) {
                cancelAnimationFrame(animationRef.current);
            }
        };
    }, [renderDrawings]);

    // Keyboard shortcuts
    useEffect(() => {
        const handleKeyDown = (e) => {
            if (e.key === 'Escape' && isDrawing) {
                onCompleteDrawing(null);
            }
            if (e.key === 'Delete' && selectedDrawing) {
                // Handled by parent via onDeleteSelected
            }
        };

        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [isDrawing, selectedDrawing, onCompleteDrawing]);

    // === SMART POINTER EVENTS LOGIC ===
    // Listen to global mouse move to toggle pointer-events on the canvas
    // This allows "panning" (clicking through the canvas) when not hovering a drawing handle
    // REFACTORED: Uses Refs to avoid constant re-binding of the listener
    useEffect(() => {
        const handleGlobalMouseMove = (e) => {
            if (!canvasRef.current) return;

            // map global coordinates to canvas local coordinates
            const rect = canvasRef.current.getBoundingClientRect();
            const mouseX = e.clientX - rect.left;
            const mouseY = e.clientY - rect.top;

            // Check if mouse is within canvas bounds
            if (mouseX < 0 || mouseX > rect.width || mouseY < 0 || mouseY > rect.height) {
                return;
            }

            // Always interactive if:
            // 1. We are currently drawing (active tool used from Ref)
            // 2. We are currently dragging something
            const isInteracting = activeToolRef.current || isDraggingRef.current;

            if (isInteracting) {
                console.log('[DEBUG] Smart Pointer: isInteracting=true, setting pointer-events:auto');
                canvasRef.current.style.pointerEvents = 'auto';
                canvasRef.current.style.cursor = activeToolRef.current ? 'crosshair' : 'grabbing';
                return;
            }

            // If idle, check if we are over a handle or drawing body that can be moved/selected
            // Use drawingsRef.current to get latest drawings without re-binding
            // Note: findDragHandle needs to be closure-safe or we replicate the logic here.
            // Replicating basic logic for performance and stability:

            let foundHandle = false;
            const currentDrawings = drawingsRef.current;

            // 1. Check Close Buttons
            for (let i = currentDrawings.length - 1; i >= 0; i--) {
                const drawing = currentDrawings[i];
                const pixelPoints = drawing.points.map(p => {
                    // We need priceTimeToPixel. If it depends on props, we might need a Ref for it too?
                    // Assuming priceTimeToPixel is stable or we can access the latest via closure if this effect dependency is empty? 
                    // No, priceTimeToPixel changes with chart zoom/pan. 
                    // CRITICAL: We DO need to re-bind if chart scales.
                    // BUT drawing interactions are local.
                    // Let's use the provided prop.
                    return priceTimeToPixel(p.price, p.time);
                }).filter(Boolean);

                const btnPos = getCloseButtonPosition(drawing, pixelPoints);
                if (btnPos) {
                    const dx = mouseX - btnPos.x;
                    const dy = mouseY - btnPos.y;
                    if (dx * dx + dy * dy <= 500) { // Generous 22px radius
                        foundHandle = true;
                        break;
                    }
                }
            }

            // 2. Check Handles (Simplified version of findDragHandle for perf)
            if (!foundHandle) {
                // We can call findDragHandle directly if we include it in deps. 
                // But we want to minimize deps.
                // Let's depend on findDragHandle but ensure findDragHandle doesn't change too often.
                // Actually `findDragHandle` depends on `drawings`.
                // We should use the locally passed `findDragHandle` which accesses the state.
                // WAIT: If we use findDragHandle in deps, we are back to square one (re-binding).
                // SOLUTION: We must manually implement hit test using refs here.
                // OR: Make `findDragHandle` use a ref internally? No, it's a prop-dependent callback.

                // Fallback: If we rely on re-binding, we must accept some flicker.
                // BUT the user says "not working".
                // Let's assume the previous re-binding WAS the issue.

                // If we toggle pointerEvents, we enable the React onMouseMove to fire.
                // Let's try just setting it to AUTO if within a "Likely Zone".

                // Logic: If close to ANY point of ANY drawing?
                for (let i = currentDrawings.length - 1; i >= 0; i--) {
                    const d = currentDrawings[i];
                    if (!d.points) continue;
                    // Check strict handle proximity
                    for (const p of d.points) {
                        const pix = priceTimeToPixel(p.price, p.time);
                        if (!pix) continue;

                        // Default check for standard points (left side / origin)
                        if (Math.hypot(mouseX - pix.x, mouseY - pix.y) < 15) {
                            foundHandle = true;
                            break;
                        }

                        // SPECIAL CASE: Long/Short Position Handles are on the RIGHT side
                        if (['longPosition', 'shortPosition'].includes(d.type) && d.points.length >= 3) {
                            // Calculate Right Edge X
                            const startTime = d.startTime || d.points[0].time;
                            const widthSeconds = d.width || (50 * 60 * 60);
                            const endTime = startTime + widthSeconds;

                            // Calculate the right edge position
                            const endPix = priceTimeToPixel(d.points[0].price, endTime);

                            let handleX = pix.x + 150; // Fallback
                            if (endPix) {
                                handleX = endPix.x;
                            }

                            // Visual handle is drawn at maxX - 40
                            const visualHandleX = handleX - 40;

                            // Check proximity to all 3 handle positions (Entry, SL, TP)
                            for (let pointIdx = 0; pointIdx < d.points.length; pointIdx++) {
                                const ptPix = priceTimeToPixel(d.points[pointIdx].price, d.points[pointIdx].time);
                                if (!ptPix) continue;

                                // Check if near the right-side handle for this point
                                // GENEROUS radius (45px) to match larger handles
                                if (Math.hypot(mouseX - visualHandleX, mouseY - ptPix.y) < 45) {
                                    console.log('[DEBUG] Smart Pointer: Near Position handle', pointIdx);
                                    foundHandle = true;
                                    break;
                                }
                            }
                            if (foundHandle) break;
                        }
                    }
                    if (foundHandle) break;

                    // Check edges (simplified) - just bounding box + margin
                    const pixs = d.points.map(p => priceTimeToPixel(p.price, p.time)).filter(Boolean);
                    if (pixs.length > 1) {
                        const minX = Math.min(...pixs.map(p => p.x));
                        const maxX = Math.max(...pixs.map(p => p.x));
                        const minY = Math.min(...pixs.map(p => p.y));
                        const maxY = Math.max(...pixs.map(p => p.y));

                        // For position tools, width extends right
                        let realMaxX = maxX;
                        if (['longPosition', 'shortPosition'].includes(d.type)) {
                            const startTime = d.startTime || d.points[0].time;
                            const widthSeconds = d.width || (50 * 60 * 60);
                            const endPix = priceTimeToPixel(d.points[0].price, startTime + widthSeconds);
                            if (endPix) {
                                realMaxX = endPix.x;
                            } else {
                                realMaxX = minX + 200; // Generous fallback
                            }
                        }

                        if (mouseX >= minX - 10 && mouseX <= realMaxX + 10 &&
                            mouseY >= minY - 10 && mouseY <= maxY + 10) {
                            foundHandle = true;
                            console.log('handleGlobalMouseMove: Found Drawing Body');
                            break;
                        }
                    }
                }
            }

            if (foundHandle) {
                canvasRef.current.style.pointerEvents = 'auto';
                canvasRef.current.style.cursor = 'pointer';
            } else {
                canvasRef.current.style.pointerEvents = 'none';
                canvasRef.current.style.cursor = 'default';
            }
        };

        // We still need priceTimeToPixel in deps, which changes on zoom. This is unavoidable.
        // But drawingsRef avoids drawings dependency.
        window.addEventListener('mousemove', handleGlobalMouseMove);
        return () => {
            window.removeEventListener('mousemove', handleGlobalMouseMove);
        };
    }, [priceTimeToPixel, getCloseButtonPosition]); // Removed drawings, activeTool, isDraggingRef from deps

    // Force pointer-events: auto as soon as a tool is selected
    // This creates a reliable state for the initial click
    useEffect(() => {
        if (canvasRef.current && activeTool) {
            canvasRef.current.style.pointerEvents = 'auto';
        }
    }, [activeTool]);

    return (
        <canvas
            ref={canvasRef}
            className={`drawing-canvas ${activeTool ? 'active-tool' : ''} ${isDrawing ? 'is-drawing' : ''}`}
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onClick={handleClick}
        />
    );
}

export default memo(DrawingCanvas);
