import React, { useState } from 'react'

/**
 * Small chart set built on plain SVG — no library.
 *
 * Rules kept deliberately: one axis per chart, categorical hues assigned in
 * fixed order (never cycled), a legend whenever there are two series, values
 * direct-labelled rather than printed on every point, and grid lines that stay
 * recessive.
 */

export function BarList({ rows, max, colorFor, emptyText = 'Nothing to show yet.' }) {
  const ceiling = max ?? Math.max(1, ...rows.map((row) => row.value))

  if (rows.length === 0) return <p className="muted">{emptyText}</p>

  return (
    <div>
      {rows.map((row) => (
        <div className="bar-row" key={row.label}>
          <span className="bar-label" title={row.label}>
            {row.label}
          </span>
          <div className="bar-track">
            <div
              className="bar-fill"
              style={{
                width: `${(row.value / ceiling) * 100}%`,
                background: colorFor ? colorFor(row) : 'var(--chart-1)',
              }}
            />
          </div>
          <span className="bar-value">{row.value}</span>
        </div>
      ))}
    </div>
  )
}

/** Two-segment stacked bar per row, with a 2px gap so the split stays readable. */
export function SplitBarList({ rows, emptyText = 'Nothing to show yet.' }) {
  const ceiling = Math.max(1, ...rows.map((row) => row.total))

  if (rows.length === 0) return <p className="muted">{emptyText}</p>

  return (
    <div>
      {rows.map((row) => (
        <div className="bar-row" key={row.label}>
          <span className="bar-label" title={row.label}>
            {row.label}
          </span>
          <div className="bar-track" style={{ display: 'flex', gap: 2 }}>
            <div
              className="bar-fill"
              style={{ width: `${(row.done / ceiling) * 100}%`, background: 'var(--chart-2)' }}
              title={`${row.done} done`}
            />
            <div
              className="bar-fill"
              style={{
                width: `${((row.total - row.done) / ceiling) * 100}%`,
                background: 'var(--chart-1)',
              }}
              title={`${row.total - row.done} open`}
            />
          </div>
          <span className="bar-value">{row.total}</span>
        </div>
      ))}
      <Legend items={[{ label: 'Done', color: 'var(--chart-2)' }, { label: 'Open', color: 'var(--chart-1)' }]} />
    </div>
  )
}

export function Legend({ items }) {
  return (
    <div className="chart-legend">
      {items.map((item) => (
        <span key={item.label}>
          <i style={{ background: item.color, borderStyle: item.dashed ? 'dashed' : undefined }} />
          {item.label}
        </span>
      ))}
    </div>
  )
}

/**
 * Line chart with a crosshair and tooltip. `series` is one or two entries of
 * { label, color, dashed, points: [{ x, y }] } where y may be null to break
 * the line (a burndown's future days, for instance).
 */
export function LineChart({ series, labels, height = 190, yLabel }) {
  const [hover, setHover] = useState(null)

  const width = 560
  const padding = { top: 12, right: 12, bottom: 26, left: 34 }
  const plotWidth = width - padding.left - padding.right
  const plotHeight = height - padding.top - padding.bottom

  const allY = series.flatMap((s) => s.points.map((p) => p.y)).filter((y) => y != null)
  const maxY = Math.max(1, ...allY)
  const count = labels.length

  const xAt = (index) => padding.left + (count <= 1 ? plotWidth / 2 : (index / (count - 1)) * plotWidth)
  const yAt = (value) => padding.top + plotHeight - (value / maxY) * plotHeight

  const ticks = [0, 0.5, 1].map((fraction) => Math.round(maxY * fraction))

  function pathFor(points) {
    let path = ''
    let open = false
    points.forEach((point, index) => {
      if (point.y == null) {
        open = false
        return
      }
      path += `${open ? 'L' : 'M'}${xAt(index).toFixed(1)},${yAt(point.y).toFixed(1)} `
      open = true
    })
    return path.trim()
  }

  return (
    <div style={{ position: 'relative' }}>
      <svg
        className="chart-svg"
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label={yLabel ?? 'Line chart'}
        onMouseLeave={() => setHover(null)}
        onMouseMove={(e) => {
          const box = e.currentTarget.getBoundingClientRect()
          const x = ((e.clientX - box.left) / box.width) * width
          const index = Math.round(((x - padding.left) / plotWidth) * (count - 1))
          setHover(index >= 0 && index < count ? index : null)
        }}
      >
        {ticks.map((tick) => (
          <g key={tick}>
            <line
              x1={padding.left}
              x2={width - padding.right}
              y1={yAt(tick)}
              y2={yAt(tick)}
              stroke="var(--chart-grid)"
              strokeWidth="1"
            />
            <text x={padding.left - 7} y={yAt(tick) + 3.5} textAnchor="end" fontSize="10" fill="var(--chart-ink)">
              {tick}
            </text>
          </g>
        ))}

        {hover != null && (
          <line
            x1={xAt(hover)}
            x2={xAt(hover)}
            y1={padding.top}
            y2={padding.top + plotHeight}
            stroke="var(--chart-ink)"
            strokeWidth="1"
            strokeDasharray="3 3"
          />
        )}

        {series.map((line) => (
          <path
            key={line.label}
            d={pathFor(line.points)}
            fill="none"
            stroke={line.color}
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeDasharray={line.dashed ? '5 4' : undefined}
          />
        ))}

        {hover != null &&
          series.map((line) =>
            line.points[hover]?.y == null ? null : (
              <circle
                key={line.label}
                cx={xAt(hover)}
                cy={yAt(line.points[hover].y)}
                r="4"
                fill={line.color}
                stroke="var(--surface)"
                strokeWidth="2"
              />
            )
          )}

        {labels.map((label, index) =>
          index % Math.ceil(count / 7) === 0 || index === count - 1 ? (
            <text
              key={label + index}
              x={xAt(index)}
              y={height - 8}
              textAnchor="middle"
              fontSize="10"
              fill="var(--chart-ink)"
            >
              {label}
            </text>
          ) : null
        )}
      </svg>

      {hover != null && (
        <div
          style={{
            position: 'absolute',
            top: 0,
            left: `${(xAt(hover) / width) * 100}%`,
            transform: 'translateX(-50%)',
            background: 'var(--surface-raised)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-sm)',
            boxShadow: 'var(--shadow-md)',
            padding: '6px 9px',
            fontSize: 11.5,
            pointerEvents: 'none',
            whiteSpace: 'nowrap',
            zIndex: 2,
          }}
        >
          <div className="strong">{labels[hover]}</div>
          {series.map((line) => (
            <div key={line.label} className="row" style={{ gap: 6 }}>
              <i
                style={{
                  width: 8,
                  height: 2,
                  borderRadius: 2,
                  background: line.color,
                  display: 'inline-block',
                }}
              />
              <span className="muted">{line.label}</span>
              <span className="strong">{line.points[hover]?.y ?? '—'}</span>
            </div>
          ))}
        </div>
      )}

      {series.length > 1 && (
        <Legend items={series.map((s) => ({ label: s.label, color: s.color, dashed: s.dashed }))} />
      )}
    </div>
  )
}
