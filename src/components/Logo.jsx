import React from 'react'

/**
 * The DevTrack mark: velocity.
 *
 * Three strokes at one angle, each longer than the last, the newest in lime —
 * sprint over sprint, the team delivers more. The increasing *length* is the
 * whole idea; three parallel strokes of equal length are a hamburger menu.
 *
 * Inline rather than an <img>, for three reasons: the structure inherits
 * `currentColor` so one component serves the black sidebar and a white print
 * sheet, it costs no extra request, and it can be styled by whatever contains
 * it. The matching files in `public/` exist for everything outside React —
 * the favicon, a slide, a README.
 */
const STROKES = ['M9 8 L25 13.1', 'M9 19 L32 26.4', 'M9 30 L39 39.6']

export function LogoMark({ size = 26, mono = false, className, title = 'DevTrack' }) {
  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 48 48"
      role="img"
      aria-label={title}
      focusable="false"
    >
      {STROKES.map((d, i) => (
        <path
          key={d}
          d={d}
          fill="none"
          // Only the last stroke takes the accent — the newest sprint.
          // `--logo-accent` exists so a light surface can darken it: Lime 400
          // on white is 1.51:1, which makes that stroke effectively invisible.
          stroke={
            i === STROKES.length - 1 && !mono
              ? 'var(--logo-accent, var(--lime-400, #A3E635))'
              : 'currentColor'
          }
          strokeWidth="5"
          strokeLinecap="round"
        />
      ))}
    </svg>
  )
}

/** Mark plus wordmark, for the sidebar and the sign-in page. */
export function LogoLockup({ size = 26, className }) {
  return (
    <span className={className}>
      <LogoMark size={size} />
      <span>DevTrack</span>
    </span>
  )
}

export default LogoMark
