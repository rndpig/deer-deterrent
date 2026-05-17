import { useCallback, useRef } from 'react'

/**
 * Idiomatic pointer-drag hook (pattern used by dnd-kit, react-konva, react-rnd).
 *
 * Why not use `e.currentTarget.setPointerCapture()` + element-level
 * `addEventListener`? React (even after v17 removed pooling) nullifies
 * SyntheticEvent.currentTarget after the synchronous handler returns. Any
 * cleanup that references `e.currentTarget` inside the async `pointerup`
 * closure becomes a no-op, leaving pointer capture / move listeners stuck.
 * The element then keeps moving on hover after the user releases — exactly
 * the bug we're fixing.
 *
 * Window-level listeners sidestep all of this: pointermove fires only while
 * the button is down on a tracked drag, pointerup always cleans up, and we
 * never depend on a stale React event.
 */
export function useMapDrag({ containerRef, onStart, onMove, onEnd }) {
  const activeRef = useRef(false)

  return useCallback((e) => {
    // Don't start a new drag if one is already in progress (e.g. multi-touch)
    if (activeRef.current) return
    e.preventDefault()
    e.stopPropagation()
    activeRef.current = true
    onStart?.(e)

    const handleMove = (me) => {
      const rect = containerRef.current?.getBoundingClientRect()
      if (!rect) return
      onMove(me, rect)
    }
    const handleUp = (me) => {
      if (!activeRef.current) return
      activeRef.current = false
      window.removeEventListener('pointermove', handleMove)
      window.removeEventListener('pointerup', handleUp)
      window.removeEventListener('pointercancel', handleUp)
      onEnd?.(me)
    }

    window.addEventListener('pointermove', handleMove)
    window.addEventListener('pointerup', handleUp)
    window.addEventListener('pointercancel', handleUp)
  }, [containerRef, onStart, onMove, onEnd])
}
