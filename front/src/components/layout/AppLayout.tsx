import { Link, NavLink, useNavigate } from 'react-router-dom';
import { Bell, ChevronDown, LogOut, Settings, User as UserIcon } from 'lucide-react';
import { cn } from '@/lib/utils';
import { BrandLogo } from '@/components/brand/Logo';
import { useAuth } from '@/lib/auth';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

const NAV = [
  { label: '仪表盘', to: '/dashboard' },
  { label: '项目', to: '/projects' },
  { label: '定价', to: '/pricing' },
];

export function AppLayout({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const displayName = user?.username || (user?.email ? user.email.split('@')[0] : 'guest');
  const initial = displayName.charAt(0).toUpperCase();

  return (
    <div className="min-h-screen flex flex-col bg-[#060a07] text-white">
      <header className="sticky top-0 z-40 border-b border-white/5 bg-[#060a07]/90 backdrop-blur">
        <div className="container-page h-16 flex items-center justify-between gap-4">
          <Link to="/" className="flex items-center gap-2">
            <BrandLogo />
          </Link>
          <nav className="flex-1 flex justify-center">
            <div className="inline-flex items-center bg-white/[0.04] border border-white/5 rounded-full p-1">
              {NAV.map((n) => (
                <NavLink
                  key={n.to}
                  to={n.to}
                  className={({ isActive }) =>
                    cn(
                      'px-4 py-1.5 rounded-full text-sm transition-all',
                      isActive
                        ? 'bg-[#46ec13] text-[#060a07] font-semibold'
                        : 'text-white/70 hover:text-white'
                    )
                  }
                >
                  {n.label}
                </NavLink>
              ))}
            </div>
          </nav>
          <div className="flex items-center gap-3">
            <button
              type="button"
              className="relative w-9 h-9 flex items-center justify-center rounded-full border border-white/10 text-white/70 hover:bg-white/5"
              aria-label="Notifications"
            >
              <Bell className="w-4 h-4" />
            </button>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button className="flex items-center gap-2 rounded-full pl-1 pr-2 py-1 border border-white/10 hover:bg-white/5">
                  <span
                    className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-semibold"
                    style={{
                      background:
                        'radial-gradient(circle at 30% 30%, #7dff4d, #2cb90a 70%)',
                      color: '#060a07',
                    }}
                  >
                    {initial}
                  </span>
                  <div className="hidden sm:flex flex-col items-start leading-tight">
                    <span className="text-xs text-white">{displayName}</span>
                    <span className="text-[10px] text-[#46ec13]">已验证</span>
                  </div>
                  <ChevronDown className="w-3.5 h-3.5 text-white/60" />
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-56 bg-[#0b110d] border-white/10 text-white">
                <DropdownMenuLabel className="text-xs text-white/60">
                  {user?.email || '未登录'}
                </DropdownMenuLabel>
                <DropdownMenuSeparator className="bg-white/10" />
                <DropdownMenuItem
                  className="cursor-pointer focus:bg-white/5"
                  onClick={() => navigate('/dashboard')}
                >
                  <UserIcon className="w-4 h-4 mr-2" /> 个人中心
                </DropdownMenuItem>
                <DropdownMenuItem
                  className="cursor-pointer focus:bg-white/5"
                  onClick={() => navigate('/pricing')}
                >
                  <Settings className="w-4 h-4 mr-2" /> 订阅与计费
                </DropdownMenuItem>
                <DropdownMenuSeparator className="bg-white/10" />
                <DropdownMenuItem
                  className="cursor-pointer focus:bg-white/5 text-red-400"
                  onClick={() => {
                    logout();
                    navigate('/');
                  }}
                >
                  <LogOut className="w-4 h-4 mr-2" /> 退出登录
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </header>
      <main className="flex-1">{children}</main>
    </div>
  );
}

export default AppLayout;
