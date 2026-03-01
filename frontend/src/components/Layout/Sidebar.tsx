import { NavLink } from 'react-router-dom'
import { FiHome, FiBarChart2, FiList, FiSliders, FiActivity, FiSettings } from 'react-icons/fi'

const navItems = [
  { to: '/', icon: FiHome, label: '대시보드' },
  { to: '/chart', icon: FiBarChart2, label: '차트' },
  { to: '/trades', icon: FiList, label: '거래 내역' },
  { to: '/rules', icon: FiSliders, label: '매매 규칙' },
  { to: '/signals', icon: FiActivity, label: '시그널' },
  { to: '/settings', icon: FiSettings, label: '설정' },
]

export default function Sidebar() {
  return (
    <aside className="w-56 bg-gray-800 border-r border-gray-700 flex flex-col">
      <div className="p-4 border-b border-gray-700">
        <div className="flex items-center justify-center gap-2">
          <img src="/favicon.svg" alt="PT" className="w-8 h-8" />
          <span className="text-2xl font-bold text-primary-400">PT</span>
        </div>
      </div>
      <nav className="flex-1 p-3 space-y-1">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${
                isActive
                  ? 'bg-primary-600/20 text-primary-400 font-medium'
                  : 'text-gray-400 hover:text-gray-200 hover:bg-gray-700/50'
              }`
            }
          >
            <item.icon className="w-5 h-5" />
            {item.label}
          </NavLink>
        ))}
      </nav>
      <div className="p-3 border-t border-gray-700">
        <div className="text-xs text-gray-500 text-center">v1.0.0</div>
      </div>
    </aside>
  )
}
