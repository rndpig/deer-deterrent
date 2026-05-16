import { useCallback, useRef } from 'react'
import { pixelToNormalized } from './coords'

export function usePointerDrag(containerRef, onMove, onEnd) {
  const dragging = useRef(false)

  const onPointerDown = useCallback((e) => {
    e.preventDefault()
    e.stopPropagation()
    dragging.current = true
    e.currentTarget.setPointerCapture(e.pointerId)

    const move = (me) => {
      if (!dragging.current) return
      const rect = containerRef.current?.getBoundingClientRect()
      if (!rect) return
      onMove(pixelToNormalized(me.clientX, me.clientY, rect), me)
    }

    const up = (ue) => {
      dragging.current = false
      ue.currentTarget?.releasePointerCapture?.(ue.pointerId)
      onEnd?.()
      ue.currentTarget?.removeEventListener('pointermove', move)
      ue.currentTarget?.removeEventListener('pointerup', up)
    }

    e.currentTarget.addEventListener('pointermove', move)
    e.currentTarget.addEventListener('pointerup', up)
  }, [containerRef, onMove, onEnd])

  return { onPointerDown }
}
