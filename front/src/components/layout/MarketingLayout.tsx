import { Link, NavLink, useLocation } from 'react-router-dom';
import { Menu } from 'lucide-react';
import { useState } from 'react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { BrandLogo } from '@/components/brand/Logo';
import { useAuth } from '@/lib/auth';

const NAV = [
  { label: '首页', to: '/' },
  { label: '案例', to: '/cases' },
  { label: '定价', to: '/pricing' },
];

export function MarketingLayout({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuth();
  const [open, setOpen] = useState(false);
  const location = useLocation();

  return (
    <div className="min-h-screen flex flex-col bg-[#060a07] text-white">
      <header className="sticky top-0 z-40 backdrop-blur-md bg-[#060a07]/85 border-b border-white/5">
        <div className="container-page flex items-center justify-between h-16">
          <Link to="/" className="flex items-center gap-2">
            <BrandLogo />
          </Link>
          <nav className="hidden md:flex items-center gap-8 text-sm">
            {NAV.map((n) => (
              <NavLink
                key={n.to}
                to={n.to}
                className={({ isActive }) =>
                  cn(
                    'transition-colors hover:text-white',
                    isActive || location.pathname === n.to
                      ? 'text-white'
                      : 'text-white/60'
                  )
                }
              >
                {n.label}
              </NavLink>
            ))}
          </nav>
          <div className="hidden md:flex items-center gap-2">
            {isAuthenticated ? (
              <Link to="/dashboard">
                <Button className="bg-[#46ec13] hover:bg-[#37c00c] text-[#060a07] font-semibold rounded-full px-5">
                  进入控制台
                </Button>
              </Link>
            ) : (
              <>
                <Link to="/login">
                  <Button variant="ghost" className="text-white/80 hover:text-white hover:bg-white/5">
                    登录
                  </Button>
                </Link>
                <Link to="/register">
                  <Button className="bg-[#46ec13] hover:bg-[#37c00c] text-[#060a07] font-semibold rounded-full px-5">
                    免费开始
                  </Button>
                </Link>
              </>
            )}
          </div>
          <button
            type="button"
            className="md:hidden inline-flex items-center justify-center w-10 h-10 rounded-md text-white/70 hover:bg-white/5"
            onClick={() => setOpen((v) => !v)}
            aria-label="Open menu"
          >
            <Menu className="w-5 h-5" />
          </button>
        </div>
        {open ? (
          <div className="md:hidden border-t border-white/5 bg-[#060a07]">
            <div className="container-page py-3 flex flex-col gap-2">
              {NAV.map((n) => (
                <Link
                  key={n.to}
                  to={n.to}
                  onClick={() => setOpen(false)}
                  className="py-2 text-white/80 hover:text-white"
                >
                  {n.label}
                </Link>
              ))}
              <div className="flex gap-2 pt-2 border-t border-white/5">
                {isAuthenticated ? (
                  <Link to="/dashboard" className="flex-1">
                    <Button className="w-full bg-[#46ec13] hover:bg-[#37c00c] text-[#060a07] font-semibold">
                      进入控制台
                    </Button>
                  </Link>
                ) : (
                  <>
                    <Link to="/login" className="flex-1">
                      <Button variant="outline" className="w-full border-white/15 text-white">
                        登录
                      </Button>
                    </Link>
                    <Link to="/register" className="flex-1">
                      <Button className="w-full bg-[#46ec13] hover:bg-[#37c00c] text-[#060a07] font-semibold">
                        免费开始
                      </Button>
                    </Link>
                  </>
                )}
              </div>
            </div>
          </div>
        ) : null}
      </header>

      <main className="flex-1">{children}</main>

      <footer className="mt-20 border-t border-white/5 bg-[#06090a]">
        <div className="container-page py-12 grid gap-10 md:grid-cols-4 text-sm">
          <div className="space-y-3">
            <BrandLogo />
            <p className="text-white/50 leading-relaxed">
              AI 驱动的视频创作平台，让每个人都能轻松制作专业级视频内容。
            </p>
          </div>
          <div>
            <h4 className="font-semibold mb-3 text-white">产品</h4>
            <ul className="space-y-2 text-white/55">
              <li><Link to="/projects" className="hover:text-white">项目管理</Link></li>
              <li><Link to="/dashboard" className="hover:text-white">控制台</Link></li>
              <li><Link to="/pricing" className="hover:text-white">定价方案</Link></li>
            </ul>
          </div>
          <div>
            <h4 className="font-semibold mb-3 text-white">资源</h4>
            <ul className="space-y-2 text-white/55">
              <li><Link to="/cases" className="hover:text-white">使用案例</Link></li>
              <li><Link to="/pricing" className="hover:text-white">会员权益</Link></li>
              <li><a className="hover:text-white" href="#">API 文档</a></li>
              <li><a className="hover:text-white" href="mailto:hello@aivideogpt.dev">联系我们</a></li>
            </ul>
          </div>
          <div>
            <h4 className="font-semibold mb-3 text-white">法律</h4>
            <ul className="space-y-2 text-white/55">
              <li><Link to="/privacy-policy" className="hover:text-white">隐私政策</Link></li>
              <li><Link to="/terms-of-service" className="hover:text-white">服务条款</Link></li>
            </ul>
          </div>
        </div>
        <div className="border-t border-white/5">
          <div className="container-page py-5 flex flex-col md:flex-row items-center justify-between gap-3 text-xs text-white/40">
            <span>© {new Date().getFullYear()} AIVideoGPT. All rights reserved.</span>
            <span>v1.0.0</span>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default MarketingLayout;
