import { useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { Eye, EyeOff, Lock, Mail } from 'lucide-react';
import { AuthShell } from './AuthShell';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useAuth } from '@/lib/auth';
import { toast } from 'sonner';

export default function LoginPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const redirect = params.get('redirect') || '/dashboard';

  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPwd, setShowPwd] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) {
      toast.error('请输入邮箱和密码');
      return;
    }
    setLoading(true);
    try {
      // Offline demo login - the existing backend does not ship a real auth endpoint.
      // We accept any non-empty credentials and store a local token so routes unlock.
      await new Promise((r) => setTimeout(r, 400));
      const fakeToken = `demo-${Date.now()}`;
      login(fakeToken, {
        email,
        username: email.split('@')[0] || 'hello',
        verified: true,
      });
      toast.success('登录成功');
      navigate(redirect, { replace: true });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '登录失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthShell title="登录工作台，开启更高效的创作协同" subtitle="一键同步脚本、素材与团队进度。AIVideoGPT 为你提供安全、可靠且充满灵感的创作体验。">
      <div className="flex items-center gap-2 mb-1">
        <div
          className="w-8 h-8 rounded-lg flex items-center justify-center"
          style={{ background: 'rgba(70,236,19,0.15)', color: '#46ec13' }}
        >
          <Lock className="w-4 h-4" />
        </div>
        <div>
          <h3 className="text-base font-semibold">欢迎回来</h3>
          <p className="text-xs text-white/55">使用企业邮箱登录，继续你的创作流程</p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="mt-6 space-y-4">
        <div className="space-y-2">
          <Label htmlFor="email" className="text-xs text-white/70">邮箱地址</Label>
          <div className="relative">
            <Mail className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-white/40" />
            <Input
              id="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="yourname@company.com"
              className="pl-9 bg-[#0f1611] border-white/10 focus-visible:ring-[#46ec13]/30"
            />
          </div>
        </div>

        <div className="space-y-2">
          <Label htmlFor="password" className="text-xs text-white/70">登录密码</Label>
          <div className="relative">
            <Lock className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-white/40" />
            <Input
              id="password"
              type={showPwd ? 'text' : 'password'}
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="请输入密码"
              className="pl-9 pr-10 bg-[#0f1611] border-white/10 focus-visible:ring-[#46ec13]/30"
            />
            <button
              type="button"
              onClick={() => setShowPwd((v) => !v)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-white/45 hover:text-white"
              aria-label={showPwd ? '隐藏密码' : '显示密码'}
            >
              {showPwd ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            </button>
          </div>
        </div>

        <div className="flex items-center justify-between text-xs">
          <Link to="/register" className="text-[#46ec13] hover:underline">
            还没有账户？立即注册
          </Link>
          <Link to="/forgot-password" className="text-white/60 hover:text-white">
            忘记密码？
          </Link>
        </div>

        <Button
          type="submit"
          disabled={loading}
          className="w-full text-white font-semibold rounded-lg h-11"
          style={{
            background:
              'linear-gradient(135deg, #6366f1 0%, #8b5cf6 50%, #a855f7 100%)',
          }}
        >
          {loading ? '登录中…' : '登录工作台'}
        </Button>
        <Link to="/">
          <Button
            type="button"
            variant="outline"
            className="w-full mt-1 h-11 border-white/15 bg-transparent text-white hover:bg-white/5"
          >
            返回首页
          </Button>
        </Link>

        <p className="text-[11px] text-white/45 text-center leading-relaxed pt-2">
          使用受信任设备登录将自动启用指纹识别、验证码等增强保护。<br />
          登录即表示你同意我们的
          <Link to="/terms-of-service" className="text-[#46ec13] mx-1">服务条款</Link>
          和
          <Link to="/privacy-policy" className="text-[#46ec13] mx-1">隐私政策</Link>。
        </p>
      </form>
    </AuthShell>
  );
}
