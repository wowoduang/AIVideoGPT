import {
  FileText,
  Mic,
  Video,
  Subtitles,
  Settings,
  ChevronLeft,
  ChevronRight,
  Zap,
  Home,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';

type PanelKey = 'script' | 'audio' | 'video' | 'subtitle';

interface SidebarProps {
  collapsed: boolean;
  setCollapsed: (v: boolean) => void;
  activePanel: PanelKey;
  onPanelChange: (panel: PanelKey) => void;
}

const navItems: { key: PanelKey; icon: React.ReactNode; label: string }[] = [
  { key: 'script', icon: <FileText className="w-5 h-5" />, label: '脚本配置' },
  { key: 'audio', icon: <Mic className="w-5 h-5" />, label: '音频设置' },
  { key: 'video', icon: <Video className="w-5 h-5" />, label: '视频设置' },
  { key: 'subtitle', icon: <Subtitles className="w-5 h-5" />, label: '字幕设置' },
];

export default function Sidebar({ collapsed, setCollapsed, activePanel, onPanelChange }: SidebarProps) {
  const navigate = useNavigate();

  return (
    <aside
      className={`h-full border-r border-white/[0.06] bg-[#0D0D14] flex flex-col transition-all duration-300 shrink-0 ${
        collapsed ? 'w-16' : 'w-60'
      }`}
    >
      {/* Logo */}
      <div className="h-14 flex items-center px-4 border-b border-white/[0.06] shrink-0">
        <div className="w-8 h-8 rounded-lg gradient-bg flex items-center justify-center shrink-0">
          <Zap className="w-4 h-4 text-white" />
        </div>
        {!collapsed && (
          <span className="ml-2 font-bold text-sm whitespace-nowrap">AIVideoGPT</span>
        )}
      </div>

      {/* Nav Items */}
      <nav className="flex-1 py-4 px-2 space-y-1">
        {navItems.map((item) => {
          const isActive = activePanel === item.key;
          return (
            <button
              key={item.key}
              onClick={() => onPanelChange(item.key)}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm transition-all duration-200 relative ${
                isActive
                  ? 'bg-indigo-500/10 text-white'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-white/[0.03]'
              }`}
            >
              {isActive && (
                <div className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 rounded-r-full gradient-bg" />
              )}
              <span className={`shrink-0 ${isActive ? 'text-indigo-400' : ''}`}>{item.icon}</span>
              {!collapsed && <span className="whitespace-nowrap">{item.label}</span>}
            </button>
          );
        })}
      </nav>

      {/* Bottom Actions */}
      <div className="p-2 border-t border-white/[0.06] space-y-1">
        <button
          onClick={() => navigate('/')}
          className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm text-slate-400 hover:text-slate-200 hover:bg-white/[0.03] transition-all"
        >
          <Home className="w-5 h-5 shrink-0" />
          {!collapsed && <span>返回首页</span>}
        </button>
        <button
          className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm text-slate-400 hover:text-slate-200 hover:bg-white/[0.03] transition-all"
        >
          <Settings className="w-5 h-5 shrink-0" />
          {!collapsed && <span>系统设置</span>}
        </button>
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm text-slate-500 hover:text-slate-300 hover:bg-white/[0.03] transition-all"
        >
          {collapsed ? (
            <ChevronRight className="w-5 h-5 shrink-0" />
          ) : (
            <>
              <ChevronLeft className="w-5 h-5 shrink-0" />
              <span>收起侧栏</span>
            </>
          )}
        </button>
      </div>
    </aside>
  );
}