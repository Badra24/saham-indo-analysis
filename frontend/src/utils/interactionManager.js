/**
 * InteractionManager - Finite State Machine for Drawing Tools
 * Based on TradingView research document
 * 
 * States:
 * - IDLE: User just moving mouse (hover), crosshair visible
 * - PREPARE_DRAW: Tool selected, waiting for first click
 * - DRAWING: Placing points for a drawing
 * - SELECTED: A drawing is selected, handles visible
 * - EDITING_HANDLE: Dragging a specific handle
 * - MOVING_TOOL: Moving entire drawing
 * - RESIZING: Resizing drawing width
 */

export const INTERACTION_STATES = {
    IDLE: 'IDLE',
    PREPARE_DRAW: 'PREPARE_DRAW',
    DRAWING: 'DRAWING',
    SELECTED: 'SELECTED',
    EDITING_HANDLE: 'EDITING_HANDLE',
    MOVING_TOOL: 'MOVING_TOOL',
    RESIZING: 'RESIZING',
};

export const HANDLE_TYPES = {
    ENTRY: 'entry',
    STOP_LOSS: 'sl',
    TAKE_PROFIT: 'tp',
    MOVE: 'move',
    RESIZE_LEFT: 'resize-left',
    RESIZE_RIGHT: 'resize-right',
};

export const CURSOR_TYPES = {
    DEFAULT: 'default',
    CROSSHAIR: 'crosshair',
    POINTER: 'pointer',
    MOVE: 'move',
    NS_RESIZE: 'ns-resize',
    EW_RESIZE: 'ew-resize',
    GRAB: 'grab',
    GRABBING: 'grabbing',
};

/**
 * Get appropriate cursor based on current state and handle type
 * @param {string} state - Current interaction state
 * @param {string} handleType - Type of handle being hovered/dragged
 * @param {boolean} isDragging - Whether currently dragging
 * @returns {string} CSS cursor value
 */
export function getCursor(state, handleType = null, isDragging = false) {
    // During active drag operations
    if (isDragging) {
        switch (handleType) {
            case HANDLE_TYPES.ENTRY:
            case HANDLE_TYPES.STOP_LOSS:
            case HANDLE_TYPES.TAKE_PROFIT:
                return CURSOR_TYPES.NS_RESIZE;
            case HANDLE_TYPES.RESIZE_LEFT:
            case HANDLE_TYPES.RESIZE_RIGHT:
                return CURSOR_TYPES.EW_RESIZE;
            case HANDLE_TYPES.MOVE:
                return CURSOR_TYPES.GRABBING;
            default:
                return CURSOR_TYPES.DEFAULT;
        }
    }

    // Based on state
    switch (state) {
        case INTERACTION_STATES.PREPARE_DRAW:
        case INTERACTION_STATES.DRAWING:
            return CURSOR_TYPES.CROSSHAIR;

        case INTERACTION_STATES.SELECTED:
            // Handle hover
            if (handleType) {
                switch (handleType) {
                    case HANDLE_TYPES.ENTRY:
                    case HANDLE_TYPES.STOP_LOSS:
                    case HANDLE_TYPES.TAKE_PROFIT:
                        return CURSOR_TYPES.NS_RESIZE;
                    case HANDLE_TYPES.RESIZE_LEFT:
                    case HANDLE_TYPES.RESIZE_RIGHT:
                        return CURSOR_TYPES.EW_RESIZE;
                    case HANDLE_TYPES.MOVE:
                        return CURSOR_TYPES.GRAB;
                    default:
                        return CURSOR_TYPES.POINTER;
                }
            }
            return CURSOR_TYPES.DEFAULT;

        case INTERACTION_STATES.EDITING_HANDLE:
            return CURSOR_TYPES.NS_RESIZE;

        case INTERACTION_STATES.MOVING_TOOL:
            return CURSOR_TYPES.GRABBING;

        case INTERACTION_STATES.RESIZING:
            return CURSOR_TYPES.EW_RESIZE;

        case INTERACTION_STATES.IDLE:
        default:
            return CURSOR_TYPES.DEFAULT;
    }
}

/**
 * Determine next state based on current state and event
 * @param {string} currentState - Current interaction state
 * @param {string} event - Event that occurred
 * @param {object} context - Additional context (selectedTool, selectedDrawing, etc)
 * @returns {string} Next state
 */
export function getNextState(currentState, event, context = {}) {
    const { activeTool, selectedDrawing, handleType } = context;

    switch (currentState) {
        case INTERACTION_STATES.IDLE:
            if (event === 'TOOL_SELECT') {
                return INTERACTION_STATES.PREPARE_DRAW;
            }
            if (event === 'DRAWING_CLICK' && selectedDrawing) {
                return INTERACTION_STATES.SELECTED;
            }
            return INTERACTION_STATES.IDLE;

        case INTERACTION_STATES.PREPARE_DRAW:
            if (event === 'CANVAS_CLICK') {
                return INTERACTION_STATES.DRAWING;
            }
            if (event === 'TOOL_DESELECT' || event === 'ESCAPE') {
                return INTERACTION_STATES.IDLE;
            }
            return INTERACTION_STATES.PREPARE_DRAW;

        case INTERACTION_STATES.DRAWING:
            if (event === 'DRAWING_COMPLETE') {
                return INTERACTION_STATES.SELECTED;
            }
            if (event === 'ESCAPE') {
                return activeTool ? INTERACTION_STATES.PREPARE_DRAW : INTERACTION_STATES.IDLE;
            }
            return INTERACTION_STATES.DRAWING;

        case INTERACTION_STATES.SELECTED:
            if (event === 'HANDLE_MOUSEDOWN') {
                if (handleType === HANDLE_TYPES.MOVE) {
                    return INTERACTION_STATES.MOVING_TOOL;
                }
                if (handleType === HANDLE_TYPES.RESIZE_LEFT || handleType === HANDLE_TYPES.RESIZE_RIGHT) {
                    return INTERACTION_STATES.RESIZING;
                }
                return INTERACTION_STATES.EDITING_HANDLE;
            }
            if (event === 'CANVAS_CLICK_EMPTY') {
                return INTERACTION_STATES.IDLE;
            }
            if (event === 'TOOL_SELECT') {
                return INTERACTION_STATES.PREPARE_DRAW;
            }
            if (event === 'DELETE') {
                return INTERACTION_STATES.IDLE;
            }
            return INTERACTION_STATES.SELECTED;

        case INTERACTION_STATES.EDITING_HANDLE:
        case INTERACTION_STATES.MOVING_TOOL:
        case INTERACTION_STATES.RESIZING:
            if (event === 'MOUSEUP') {
                return INTERACTION_STATES.SELECTED;
            }
            return currentState;

        default:
            return INTERACTION_STATES.IDLE;
    }
}

/**
 * Check if a point is near a handle (for hit detection)
 * @param {number} mouseX - Mouse X coordinate
 * @param {number} mouseY - Mouse Y coordinate
 * @param {number} handleX - Handle X coordinate
 * @param {number} handleY - Handle Y coordinate
 * @param {number} radius - Hit detection radius (default 12px)
 * @returns {boolean} Whether mouse is near handle
 */
export function isNearHandle(mouseX, mouseY, handleX, handleY, radius = 12) {
    const dx = mouseX - handleX;
    const dy = mouseY - handleY;
    return Math.sqrt(dx * dx + dy * dy) <= radius;
}

/**
 * Check if a point is near a vertical edge (for resize detection)
 * @param {number} mouseX - Mouse X coordinate
 * @param {number} mouseY - Mouse Y coordinate
 * @param {number} edgeX - Edge X coordinate
 * @param {number} yMin - Minimum Y of the edge
 * @param {number} yMax - Maximum Y of the edge
 * @param {number} tolerance - Hit detection tolerance (default 10px)
 * @returns {boolean} Whether mouse is near edge
 */
export function isNearEdge(mouseX, mouseY, edgeX, yMin, yMax, tolerance = 10) {
    return mouseX >= edgeX - tolerance &&
        mouseX <= edgeX + tolerance &&
        mouseY >= yMin - tolerance &&
        mouseY <= yMax + tolerance;
}

/**
 * Check if a point is inside a rectangle (for move detection)
 * @param {number} mouseX - Mouse X coordinate
 * @param {number} mouseY - Mouse Y coordinate
 * @param {number} minX - Rectangle left edge
 * @param {number} maxX - Rectangle right edge
 * @param {number} minY - Rectangle top edge
 * @param {number} maxY - Rectangle bottom edge
 * @returns {boolean} Whether mouse is inside rectangle
 */
export function isInsideRect(mouseX, mouseY, minX, maxX, minY, maxY) {
    return mouseX >= minX && mouseX <= maxX && mouseY >= minY && mouseY <= maxY;
}

export default {
    INTERACTION_STATES,
    HANDLE_TYPES,
    CURSOR_TYPES,
    getCursor,
    getNextState,
    isNearHandle,
    isNearEdge,
    isInsideRect,
};
