import React from 'react'

export default function Empty({ mark = '◇', title, children, action }) {
  return (
    <div className="empty">
      <div className="empty-mark" aria-hidden="true">
        {mark}
      </div>
      {title && <div className="empty-title">{title}</div>}
      {children && <p className="empty-text">{children}</p>}
      {action}
    </div>
  )
}
