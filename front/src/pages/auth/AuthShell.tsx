import { Link } from 'react-router-dom';
import { ShieldCheck, Sparkles, Clock } from 'lucide-react';
import { BrandLogo } from '@/components/brand/Logo';

const HIGHLIGHTS = [
  {
    icon: ShieldCheck,
    title: '企业级安全防护',
    desc: '统一身份验证与审计追踪，保障每一次创作安全可控',
  },
  {
    icon: Sparkles,
    title: '多模态创作协同',
    desc: '与团队共享项目与素材，快速同步最新脚本与版本',
  },
  {
    icon: Clock,
    title: '智能加速工作流',
    desc: '自动保存进度并建议下一步动作，创作效率提升 3 倍',
  },
];

const STATS = [
  { value: '2K+', label: '团队成员' },
  { value: '96%', label: '月度活跃' },
  { value: '14h/周', label: '平均节省时间' },
];

export function AuthShell({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle: string;
  children: React.ReactNode;
}) {
  return (
    <div
      className="min-h-screen flex flex-col text-white"
      style={{
        background:
          'radial-gradient(ellipse at 10% 10%, rgba(70,236,19,0.22), transparent 55%), radial-gradient(ellipse at 90% 80%, rgba(70,236,19,0.12), transparent 55%), #050807',
      }}
    >
      <div className="flex-1 grid md:grid-cols-2 gap-8 lg:gap-16 px-6 lg:px-16 py-10 lg:py-20 max-w-[1400px] w-full mx-auto">
        <div className="flex flex-col justify-center">
          <Link to="/" className="mb-10 inline-flex">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-white/10 bg-white/[0.04] text-xs">
              <Sparkles className="w-3.5 h-3.5 text-[#46ec13]" />
              AIVideoGPT · 视频创作智能体平台
            </div>
          </Link>
          <h1 className="text-3xl lg:text-4xl font-extrabold leading-tight">{title}</h1>
          <p className="mt-4 text-white/60 max-w-md">{subtitle}</p>

          <div className="mt-8 grid sm:grid-cols-2 gap-4 max-w-xl">
            {HIGHLIGHTS.map((h) => {
              const Icon = h.icon;
              return (
                <div
                  key={h.title}
                  className="rounded-2xl p-5 bg-white/[0.03] border border-white/[0.06]"
                >
                  <div
                    className="w-9 h-9 rounded-lg flex items-center justify-center mb-3"
                    style={{
                      background: 'rgba(70, 236, 19, 0.12)',
                      color: '#46ec13',
                    }}
                  >
                    <Icon className="w-4 h-4" />
                  </div>
                  <div className="font-semibold text-sm">{h.title}</div>
                  <div className="mt-1 text-xs text-white/55 leading-relaxed">{h.desc}</div>
                </div>
              );
            })}
          </div>

          <div className="mt-6 flex gap-6 flex-wrap">
            {STATS.map((s) => (
              <div key={s.label} className="rounded-xl px-4 py-2 bg-white/[0.03] border border-white/[0.06]">
                <div className="text-lg font-bold text-[#46ec13]">{s.value}</div>
                <div className="text-[11px] text-white/55">{s.label}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="flex flex-col justify-center">
          <div
            className="relative rounded-2xl bg-[#0a100b]/80 backdrop-blur border border-white/10 p-8 lg:p-10 max-w-md w-full mx-auto"
            style={{ boxShadow: '0 0 48px rgba(70,236,19,0.12)' }}
          >
            <div className="flex items-center gap-3 mb-6">
              <BrandLogo size={32} showText={false} />
              <div>
                <h2 className="text-lg font-semibold">AIVideoGPT</h2>
                <p className="text-xs text-white/55">你的 AI 视频创作伙伴</p>
              </div>
            </div>
            {children}
          </div>
        </div>
      </div>
    </div>
  );
}

export default AuthShell;
