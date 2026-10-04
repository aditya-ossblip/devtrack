import React, { useEffect, useRef, useState } from 'react'

import '../styles/auth-loop.css'

/**
 * The sign-in frame: a full-bleed split, no card.
 *
 * Left is the mark at scale. The three strokes of the logo draw themselves,
 * then unfold into a stack — the one place files land — and the places a file
 * usually scatters to get pulled in and disappear. Then it folds back. The
 * strokes and the stack are the same three elements throughout, so the loop
 * reads as one object breathing rather than two animations taking turns.
 *
 * Right is the form, on a lifted surface so the halves separate without
 * leaving the palette. A black-and-white split would look sharper, but lime on
 * white is 1.5:1 and the app behind this screen is pure black; signing in
 * should not be a flash of white.
 */
export default function AuthShell({ children }) {
  return (
    <div className="auth-screen">
      <div className="auth-art" aria-hidden="true">
        <VelocityField />
        <VelocityLoop />
      </div>
      <div className="auth-form-side">
        <div className="auth-form-inner">{children}</div>
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ *
 * The loop
 * ------------------------------------------------------------------ */

/* Geometry taken straight from the logo, and sized from the panel rather than
 * pinned to a pixel count. The mark is drawn on a 48-unit viewBox, so one
 * scale factor turns every viewBox number below into pixels — which means the
 * animated mark and the SVG one can never drift apart, at any size.
 */
const VIEWBOX = 48
const STROKE_W = 3.4          // the logo's stroke-width, in viewBox units

/* How much of the panel's width the mark should occupy, and the range it is
   allowed to live in. The panel is half a browser window, so a fixed size
   that looks right on a laptop is lost on a wide monitor. */
const MARK_SHARE = 0.28
const MARK_MIN = 160
const MARK_MAX = 290

/* The three strokes, as [length, vertical offset] in viewBox units:
   M9 8 → L25 13.1,  M9 19 → L32 26.4,  M9 30 → L39 39.6 */
const STROKES = [
  { len: 16.8, y: 0 },
  { len: 24.2, y: 11 },
  { len: 31.5, y: 22 },
]

function geometry(stageWidth) {
  const target = Math.min(MARK_MAX, Math.max(MARK_MIN, stageWidth * MARK_SHARE))
  const k = target / VIEWBOX
  const barH = STROKE_W * k

  const mark = STROKES.map(s => ({ w: s.len * k, y: s.y * k }))

  /* The stack is half again as long as the longest stroke, so the unfold is a
     visible stretch rather than only a rotation. */
  const stackW = STROKES[2].len * k * 1.5
  const gap = barH * 2.2
  const stack = [0, 1, 2].map(i => ({ w: stackW, y: i * gap }))

  /* Tall enough for whichever arrangement is taller, plus room for the chip
     that sits lowest. */
  const height = Math.max(mark[2].y, stack[2].y) + barH + 62

  return { k, barH, mark, stack, height }
}

/* Chip positions are fractions of the stage, not pixels: this panel is half a
   browser window, so a hard-coded offset that sits nicely on a laptop hangs
   off the edge of a narrow one and strands itself on a wide one. */
const SOURCES = [
  { label: 'WhatsApp', x: 0.46, y: -0.30 },
  { label: 'Telegram', x: 0.60, y: -0.07 },
  { label: 'Drive', x: 0.72, y: 0.21 },
  { label: 'Email', x: 0.44, y: 0.45 },
  { label: 'Pen drive', x: 0.70, y: 0.60 },
]

const CYCLE = 15400

function VelocityLoop() {
  const rootRef = useRef(null)
  const stageRef = useRef(null)
  const barsRef = useRef([])
  const chipsRef = useRef([])
  const [line, setLine] = useState(null)

  useEffect(() => {
    const bars = barsRef.current.filter(Boolean)
    const chips = chipsRef.current.filter(Boolean)
    const stage = stageRef.current
    const root = rootRef.current
    if (!stage || !root || bars.length !== 3) return undefined

    /* Which arrangement the bars are currently in. A resize has to re-apply
       the shape at the new size, and it cannot ask the DOM which one it is. */
    let arrangement = 'mark'
    let geom = geometry(stage.clientWidth)

    const shape = (which, withWidths = true) => {
      arrangement = which
      const spec = which === 'mark' ? geom.mark : geom.stack
      const angle = which === 'mark' ? 'var(--al-angle)' : '0deg'
      bars.forEach((bar, i) => {
        if (withWidths) bar.style.width = `${spec[i].w}px`
        bar.style.transform = `translateY(${spec[i].y}px) rotate(${angle})`
      })
    }

    const measure = () => {
      geom = geometry(stage.clientWidth)
      root.style.setProperty('--al-stage-h', `${geom.height}px`)
      root.style.setProperty('--al-bar-h', `${geom.barH}px`)

      const width = stage.clientWidth
      chips.forEach((chip, i) => {
        const wanted = SOURCES[i].x * width
        // Never let a chip hang past the right edge, however narrow it gets.
        const x = Math.min(wanted, width - chip.offsetWidth - 2)
        chip.style.setProperty('--al-x', `${Math.max(0, x)}px`)
        chip.style.setProperty('--al-y', `${SOURCES[i].y * geom.height}px`)
      })
    }

    measure()

    const onResize = () => {
      measure()
      // Re-apply at the new scale, or the bars keep their old pixel widths.
      shape(arrangement)
    }
    window.addEventListener('resize', onResize)

    const reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    if (reduced) {
      // Settle on the mark and the first statement. Nothing runs.
      bars.forEach((bar) => { bar.style.transition = 'none' })
      shape('mark')
      setLine('H')
      return () => window.removeEventListener('resize', onResize)
    }

    /* The schedule, as a list. Reading the timings in a column beats chasing
       them through six levels of nested callbacks. */
    const timers = []
    const at = (ms, fn) => { timers.push(window.setTimeout(fn, ms)) }

    const run = () => {
      // --- H: the mark draws itself, short to longest ---
      at(0, () => {
        bars.forEach((bar) => { bar.style.width = '0px' })
        shape('mark', false)
        chips.forEach((chip) => { chip.className = 'al-chip' })
      })
      bars.forEach((bar, i) => at(120 + i * 130, () => { bar.style.width = `${geom.mark[i].w}px` }))
      at(700, () => setLine('H'))

      // --- the unfold: strokes rotate flat and become rows ---
      at(4000, () => setLine(null))
      at(4300, () => shape('stack'))

      /* --- G: the sources appear, then get pulled in ---
         The line arrives *with* the mess rather than after it. Holding it back
         until the chips had gone left this box empty for four seconds, which
         reads as a page that has broken rather than as a pause. */
      chips.forEach((chip, i) => at(5300 + i * 120, () => { chip.className = 'al-chip is-out' }))
      at(5500, () => setLine('G'))
      chips.forEach((chip, i) => at(7300 + i * 90, () => { chip.className = 'al-chip is-gone' }))

      // --- the fold: back to the mark, and round again ---
      at(11300, () => setLine(null))
      at(11600, () => shape('mark'))
      at(12400, () => setLine('H'))

      at(CYCLE, run)
    }

    run()

    return () => {
      timers.forEach(window.clearTimeout)
      window.removeEventListener('resize', onResize)
    }
  }, [])

  return (
    <div className="al-root" ref={rootRef}>
      <div className="al-stage" ref={stageRef}>
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            className="al-bar"
            ref={(el) => { barsRef.current[i] = el }}
          />
        ))}
        {SOURCES.map((source, i) => (
          <div
            key={source.label}
            className="al-chip"
            ref={(el) => { chipsRef.current[i] = el }}
          >
            {source.label}
          </div>
        ))}
      </div>

      <div className="al-caption">
        <div className={`al-line${line === 'H' ? ' is-on' : ''}`}>
          <h2>Every week,<br />a little further.</h2>
          <p>Work you can point at, not a feeling at the end of the week.</p>
        </div>
        <div className={`al-line${line === 'G' ? ' is-on' : ''}`}>
          <h2>Stop asking<br />who has the file.</h2>
          <p>The board, the files, the history — all in the same place as the work.</p>
        </div>
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ *
 * The drifting field, behind it all
 * ------------------------------------------------------------------ */

/* Tuning, kept together so the field can be retuned without reading the loop. */
const SLOPE = 0.32        // the logo's angle, reused exactly
const LANE_H = 26         // vertical pitch between lanes
const WEIGHT = 3          // stroke width
const LIME = '#a3e635'
const LIME_SHARE = 0.05
const BASE_SPEED = 7      // px per second in the top lane
const SPEED_RAMP = 2.4    // how much faster the bottom lane runs

/**
 * Lanes of drifting strokes.
 *
 * Each lane owns a list of strokes at fixed offsets and scrolls as a unit, so
 * the animation is one number per lane per frame rather than per stroke. The
 * offsets are laid out across a span wider than the canvas and taken modulo
 * that span, which makes the loop seamless without any bookkeeping at the
 * edges.
 */
function VelocityField() {
  const canvasRef = useRef(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return undefined

    const ctx = canvas.getContext('2d')
    const reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

    let width = 0
    let height = 0
    let lanes = []
    let raf = null
    let resizeRaf = null
    let last = 0

    const build = () => {
      const rect = canvas.getBoundingClientRect()
      if (!rect.width || !rect.height) return

      width = rect.width
      height = rect.height

      const dpr = Math.min(window.devicePixelRatio || 1, 2)
      canvas.width = Math.round(width * dpr)
      canvas.height = Math.round(height * dpr)
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)

      const laneCount = Math.ceil(height / LANE_H) + 1
      const span = width + 320   // wider than the canvas, so wrapping is unseen

      lanes = []
      for (let i = 0; i < laneCount; i += 1) {
        const depth = laneCount > 1 ? i / (laneCount - 1) : 0
        const strokes = []
        // Lower lanes carry more, and longer. The field thickens downward the
        // way the mark's strokes lengthen.
        const count = Math.round(4 + depth * 9 + Math.random() * 3)
        for (let s = 0; s < count; s += 1) {
          const lime = Math.random() < LIME_SHARE
          strokes.push({
            at: Math.random() * span,
            len: 22 + Math.random() * (60 + depth * 90),
            colour: lime ? LIME : '#ffffff',
            alpha: lime ? 0.45 + Math.random() * 0.3 : 0.05 + Math.random() * 0.22,
          })
        }
        lanes.push({
          y: i * LANE_H + 14,
          span,
          phase: Math.random() * span,
          speed: BASE_SPEED * (1 + depth * SPEED_RAMP),
          strokes,
        })
      }
    }

    const draw = () => {
      ctx.clearRect(0, 0, width, height)
      ctx.lineWidth = WEIGHT
      ctx.lineCap = 'round'

      for (const lane of lanes) {
        for (const stroke of lane.strokes) {
          // Start one span to the left so a stroke entering from off-screen is
          // already drawn rather than popping in at x = 0.
          const x = ((stroke.at + lane.phase) % lane.span) - 160
          if (x > width || x + stroke.len < 0) continue
          ctx.globalAlpha = stroke.alpha
          ctx.strokeStyle = stroke.colour
          ctx.beginPath()
          ctx.moveTo(x, lane.y)
          ctx.lineTo(x + stroke.len, lane.y + stroke.len * SLOPE)
          ctx.stroke()
        }
      }
      ctx.globalAlpha = 1
    }

    const frame = (now) => {
      const dt = last ? Math.min((now - last) / 1000, 0.05) : 0
      last = now
      for (const lane of lanes) lane.phase = (lane.phase + lane.speed * dt) % lane.span
      draw()
      raf = requestAnimationFrame(frame)
    }

    const onResize = () => {
      if (resizeRaf) cancelAnimationFrame(resizeRaf)
      resizeRaf = requestAnimationFrame(() => {
        build()
        draw()
      })
    }

    build()
    draw()
    if (!reduced) raf = requestAnimationFrame(frame)
    window.addEventListener('resize', onResize)

    return () => {
      if (raf) cancelAnimationFrame(raf)
      if (resizeRaf) cancelAnimationFrame(resizeRaf)
      window.removeEventListener('resize', onResize)
    }
  }, [])

  return <canvas ref={canvasRef} className="auth-art-canvas" />
}
