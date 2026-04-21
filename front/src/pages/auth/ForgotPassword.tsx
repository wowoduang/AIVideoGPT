import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Mail, KeyRound } from 'lucide-react';
import { AuthShell } from './AuthShell';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { toast } from 'sonner';

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email) return;
    setLoading(true);
    await new Promise((r) => setTimeout(r, 600));
    setLoading(false);
    setSent(true);
    toast.success('重置邮件已发送');
  };

  return (
    <AuthShell title="忘记密码？我们来帮你找回" subtitle="输入注册邮箱，我们会向你发送密码重置链接。">
      <div className="flex items-center gap-2 mb-4">
        <div
          className="w-8 h-8 rounded-lg flex items-center justify-center"
          style={{ background: 'rgba(70,236,19,0.15)', color: '#46ec13' }}
        >
          <KeyRound className="w-4 h-4" />
        </div>
        <div>
          <h3 className="text-base font-semibold">重置密码</h3>
          <p className="text-xs text-white/55">发送重置链接到你的邮箱</p>
        </div>
      </div>
      {sent ? (
        <div className="rounded-xl border border-[#46ec13]/40 bg-[#0d1a0e] p-5 text-sm">
          我们已向 <span className="text-[#46ec13]">{email}</span> 发送了重置邮件，请在 30 分钟内点击邮件中的链接完成重置。
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="email" className="text-xs text-white/70">邮箱地址</Label>
            <div className="relative">
              <Mail className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-white/40" />
              <Input
                id="email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="yourname@company.com"
                className="pl-9 bg-[#0f1611] border-white/10 focus-visible:ring-[#46ec13]/30"
              />
            </div>
          </div>
          <Button
            type="submit"
            disabled={loading}
            className="w-full h-11 bg-[#46ec13] hover:bg-[#37c00c] text-[#060a07] font-semibold rounded-lg"
          >
            {loading ? '发送中…' : '发送重置邮件'}
          </Button>
        </form>
      )}
      <div className="mt-4 text-xs text-white/60 text-center">
        想起来了？
        <Link to="/login" className="text-[#46ec13] ml-1 hover:underline">
          返回登录
        </Link>
      </div>
    </AuthShell>
  );
}
