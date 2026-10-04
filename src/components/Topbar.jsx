import React from 'react'

export default function Topbar({ title, subtitle, members = [], children }) {
  return (
    <header className="topbar">
      <div className="topbar-heading">
        <h1 className="topbar-title">{title}</h1>
        {subtitle && <div className="topbar-subtitle">{subtitle}</div>}
      </div>

      <div className="topbar-right">
        {children}
        {members.length > 0 && (
          <div className="avatar-group">
            {members.slice(0, 4).map((member) => (
              <div className="avatar avatar-sm" key={member.id} title={member.name}>
                {member.initials}
              </div>
            ))}
            {members.length > 4 && (
              <div className="avatar avatar-sm avatar-empty" title={`${members.length} members`}>
                +{members.length - 4}
              </div>
            )}
          </div>
        )}
      </div>
    </header>
  )
}
