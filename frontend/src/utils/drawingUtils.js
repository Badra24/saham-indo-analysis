/**
 * Drawing Tools Utilities
 * Provides calculation and rendering functions for TradingView-style drawing tools
 */

// Fibonacci levels for retracement
export const FIB_LEVELS = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1];
export const FIB_COLORS = [
    'rgba(255, 82, 82, 0.3)',   // 0%
    'rgba(255, 152, 0, 0.2)',   // 23.6%
    'rgba(255, 235, 59, 0.2)',  // 38.2%
    'rgba(76, 175, 80, 0.2)',   // 50%
    'rgba(33, 150, 243, 0.2)',  // 61.8%
    'rgba(156, 39, 176, 0.2)',  // 78.6%
    'rgba(233, 30, 99, 0.3)',   // 100%
];

// Fibonacci Fan angles
export const FIB_FAN_LEVELS = [0.382, 0.5, 0.618, 0.786];

// Drawing colors
export const DRAWING_COLORS = {
    rectangle: 'rgba(99, 102, 241, 0.3)',
    rectangleBorder: '#6366f1',
    fibonacci: '#f59e0b',
    longEntry: '#10b981',
    longProfit: 'rgba(16, 185, 129, 0.2)',
    longLoss: 'rgba(239, 68, 68, 0.2)',
    shortEntry: '#ef4444',
    shortProfit: 'rgba(16, 185, 129, 0.2)',
    shortLoss: 'rgba(239, 68, 68, 0.2)',
    fibFan: '#8b5cf6',
    xabcd: '#f97316',
    xabcdFill: 'rgba(249, 115, 22, 0.15)',
    selected: '#00bcd4',
};

/**
 * Calculate Fibonacci retracement levels between two price points
 */
export function calculateFibLevels(startPrice, endPrice) {
    const diff = endPrice - startPrice;
    return FIB_LEVELS.map(level => ({
        level,
        price: startPrice + diff * level,
        label: `${(level * 100).toFixed(1)}%`,
    }));
}

/**
 * Calculate Long Position zones and R:R ratio
 */
export function calculateLongPosition(entry, stopLoss, takeProfit) {
    const risk = entry - stopLoss;
    const reward = takeProfit - entry;
    const riskReward = (risk > 0.00000001) ? (reward / risk).toFixed(2) : '0.00';
    const riskPercent = (entry > 0) ? ((risk / entry) * 100).toFixed(2) : '0.00';
    const rewardPercent = (entry > 0) ? ((reward / entry) * 100).toFixed(2) : '0.00';

    return {
        entry,
        stopLoss,
        takeProfit,
        risk,
        reward,
        riskReward,
        riskPercent,
        rewardPercent,
    };
}

/**
 * Calculate Short Position zones and R:R ratio
 */
export function calculateShortPosition(entry, stopLoss, takeProfit) {
    const risk = stopLoss - entry;
    const reward = entry - takeProfit;
    const riskReward = (risk > 0.00000001) ? (reward / risk).toFixed(2) : '0.00';
    const riskPercent = (entry > 0) ? ((risk / entry) * 100).toFixed(2) : '0.00';
    const rewardPercent = (entry > 0) ? ((reward / entry) * 100).toFixed(2) : '0.00';

    return {
        entry,
        stopLoss,
        takeProfit,
        risk,
        reward,
        riskReward,
        riskPercent,
        rewardPercent,
    };
}

/**
 * Calculate Fibonacci Fan lines from origin point
 * Extended distance is limited to keep labels visible
 */
export function calculateFibFanLines(origin, target, chartWidth) {
    const dx = target.x - origin.x;
    const dy = target.y - origin.y;

    // Limit max extension to 400px from origin (or chartWidth if smaller)
    const maxExtension = Math.min(400, chartWidth - origin.x - 60); // Leave 60px for labels

    return FIB_FAN_LEVELS.map(level => {
        const angle = Math.atan2(dy * level, dx);
        const extendedX = origin.x + maxExtension;
        const extendedY = origin.y + Math.tan(angle) * maxExtension;

        return {
            level,
            label: `${(level * 100).toFixed(1)}%`,
            start: origin,
            end: { x: extendedX, y: extendedY },
        };
    });
}

/**
 * Calculate XABCD pattern points and validate ratios
 */
export function calculateXABCDPattern(points) {
    if (points.length < 5) return null;

    const [X, A, B, C, D] = points;

    // Calculate leg lengths
    const XA = Math.abs(A.price - X.price);
    const AB = Math.abs(B.price - A.price);
    const BC = Math.abs(C.price - B.price);
    const CD = Math.abs(D.price - C.price);

    // Calculate ratios
    const AB_XA = AB / XA;
    const BC_AB = BC / AB;
    const CD_BC = CD / BC;

    // Determine pattern type
    let patternType = 'Custom';
    if (AB_XA >= 0.55 && AB_XA <= 0.68) {
        if (CD_BC >= 1.2 && CD_BC <= 1.41) patternType = 'Gartley';
    } else if (AB_XA >= 0.76 && AB_XA <= 0.88) {
        if (CD_BC >= 1.6 && CD_BC <= 2.24) patternType = 'Butterfly';
    } else if (AB_XA >= 0.32 && AB_XA <= 0.5) {
        if (CD_BC >= 2.2 && CD_BC <= 3.5) patternType = 'Crab';
    } else if (AB_XA >= 0.38 && AB_XA <= 0.5) {
        if (CD_BC >= 1.6 && CD_BC <= 2.0) patternType = 'Bat';
    }

    return {
        points,
        ratios: {
            AB_XA: AB_XA.toFixed(3),
            BC_AB: BC_AB.toFixed(3),
            CD_BC: CD_BC.toFixed(3),
        },
        patternType,
    };
}

/**
 * Generate unique ID for drawings
 */
export function generateDrawingId() {
    return `drawing_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

/**
 * Check if a point is inside a rectangle
 */
export function isPointInRect(point, rect) {
    const minX = Math.min(rect.start.x, rect.end.x);
    const maxX = Math.max(rect.start.x, rect.end.x);
    const minY = Math.min(rect.start.y, rect.end.y);
    const maxY = Math.max(rect.start.y, rect.end.y);

    return point.x >= minX && point.x <= maxX && point.y >= minY && point.y <= maxY;
}

/**
 * Check if a point is near a line (within threshold)
 */
export function isPointNearLine(point, lineStart, lineEnd, threshold = 5) {
    const A = point.x - lineStart.x;
    const B = point.y - lineStart.y;
    const C = lineEnd.x - lineStart.x;
    const D = lineEnd.y - lineStart.y;

    const dot = A * C + B * D;
    const lenSq = C * C + D * D;
    let param = -1;

    if (lenSq !== 0) param = dot / lenSq;

    let xx, yy;

    if (param < 0) {
        xx = lineStart.x;
        yy = lineStart.y;
    } else if (param > 1) {
        xx = lineEnd.x;
        yy = lineEnd.y;
    } else {
        xx = lineStart.x + param * C;
        yy = lineStart.y + param * D;
    }

    const dx = point.x - xx;
    const dy = point.y - yy;
    const distance = Math.sqrt(dx * dx + dy * dy);

    return distance <= threshold;
}

/**
 * Format price for display
 */
export function formatPrice(price, decimals = 2) {
    if (price >= 1000) {
        return price.toFixed(2);
    } else if (price >= 1) {
        return price.toFixed(4);
    } else {
        return price.toFixed(6);
    }
}

/**
 * Apply Magnet Mode - Snap to nearest OHLC price
 * Uses binary search to efficiently find nearest candle, then checks OHLC values
 * 
 * @param {number} mouseX - Mouse X position in pixels
 * @param {number} mouseY - Mouse Y position in pixels
 * @param {Array} candleData - Array of candle data [{time, open, high, low, close}, ...]
 * @param {Function} pixelToIndex - Convert pixel X to candle index
 * @param {Function} priceToPixel - Convert price to pixel Y
 * @param {Function} indexToPixel - Convert candle index to pixel X
 * @param {number} threshold - Maximum distance for snapping (default 20px)
 * @returns {object} Snapped position { x, y, price, time, snapType } or original if no snap
 */
export function applyMagnet(mouseX, mouseY, candleData, pixelToIndex, priceToPixel, indexToPixel, threshold = 20) {
    if (!candleData || candleData.length === 0) {
        return { x: mouseX, y: mouseY, snapped: false };
    }

    // 1. Binary search to find candle index from X position
    const index = Math.round(pixelToIndex(mouseX));

    // Bounds check
    if (index < 0 || index >= candleData.length) {
        return { x: mouseX, y: mouseY, snapped: false };
    }

    const candle = candleData[index];
    if (!candle) {
        return { x: mouseX, y: mouseY, snapped: false };
    }

    // 2. Get OHLC candidate points
    const ohlcPoints = [
        { type: 'open', price: candle.open },
        { type: 'high', price: candle.high },
        { type: 'low', price: candle.low },
        { type: 'close', price: candle.close },
    ];

    const candleX = indexToPixel(index);

    // 3. Find closest OHLC point
    let bestMatch = null;
    let minDistance = Infinity;

    for (const pt of ohlcPoints) {
        const py = priceToPixel(pt.price);
        if (py === null || py === undefined) continue;

        const dist = Math.hypot(mouseX - candleX, mouseY - py);

        if (dist < minDistance && dist <= threshold) {
            minDistance = dist;
            bestMatch = {
                x: candleX,
                y: py,
                price: pt.price,
                time: candle.time,
                snapType: pt.type,
                snapped: true,
            };
        }
    }

    // Return best match or original position
    return bestMatch || { x: mouseX, y: mouseY, snapped: false };
}

/**
 * Binary search to find candle index from time
 * @param {Array} candleData - Sorted candle data array
 * @param {number} targetTime - Time to search for
 * @returns {number} Index of nearest candle
 */
export function binarySearchCandleIndex(candleData, targetTime) {
    if (!candleData || candleData.length === 0) return -1;

    let left = 0;
    let right = candleData.length - 1;

    while (left <= right) {
        const mid = Math.floor((left + right) / 2);
        const midTime = candleData[mid].time;

        if (midTime === targetTime) {
            return mid;
        } else if (midTime < targetTime) {
            left = mid + 1;
        } else {
            right = mid - 1;
        }
    }

    // Return closest index
    if (left >= candleData.length) return candleData.length - 1;
    if (right < 0) return 0;

    // Return the closer one
    const leftDiff = Math.abs(candleData[left].time - targetTime);
    const rightDiff = Math.abs(candleData[right].time - targetTime);
    return leftDiff < rightDiff ? left : right;
}
