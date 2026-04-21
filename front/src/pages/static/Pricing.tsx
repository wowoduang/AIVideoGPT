import { Link } from 'react-router-dom';
import { CheckCircle2, Sparkles } from 'lucide-react';
import { MarketingLayout } from '@/components/layout/MarketingLayout';
import { Button } from '@/components/ui/button';

const PLANS = [
  {
    name: '创作者',
    tag: '个人创作者免费入门',
    price: '¥0',
    period: '永久免费',
    highlight: false,
    features: [
      '每月 200 分钟视频处理额度',
      '3 个同时进行的项目',
      '基础 TTS 音色',
      '720P 成片导出',
      'AI 字幕识别 + 解说脚本',
    ],
  },
  {
    name: '专业版',
    tag: '专业工作室首选',
    price: '¥199',
    period: '/ 月',
    highlight: true,
    features: [
      '每月 2000 分钟视频处理额度',
      '20 个同时进行的项目',
      '全量高级 TTS 音色',
      '1080P / 4K 成片导出',
      '团队共享素材库',
      '优先 GPU 队列',
      '自定义品牌水印',
    ],
  },
  {
    name: '企业版',
    tag: '企业与机构定制',
    price: '联系我们',
    period: '',
    highlight: false,
    features: [
      '无限时长额度 & 并发',
      '私有化部署 / VPC',
      '专属模型与微调',
      'SSO / 审计日志',
      '7x24 技术支持',
    ],
  },
];

export default function PricingPage() {
  return (
    <MarketingLayout>
      <section className="container-page pt-20 pb-10 text-center">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/5 border border-white/10 text-xs text-white/70 mb-6">
          <Sparkles className="w-3.5 h-3.5 text-[#46ec13]" />
          定价方案
        </div>
        <h1 className="text-4xl md:text-5xl font-extrabold">选择最适合你的方案</h1>
        <p className="mt-4 text-white/60">按月订阅，随时升降级；可免费试用专业版 14 天。</p>
      </section>

      <section className="container-page pb-24">
        <div className="grid gap-6 md:grid-cols-3">
          {PLANS.map((p) => (
            <div
              key={p.name}
              className={
                p.highlight
                  ? 'relative rounded-2xl p-8 border border-[#46ec13]/60 bg-[#0d1a0e] brand-glow'
                  : 'rounded-2xl p-8 border border-white/[0.08] bg-white/[0.02]'
              }
            >
              {p.highlight ? (
                <div className="absolute -top-3 left-8 px-3 py-1 rounded-full text-[11px] font-semibold text-[#060a07] bg-[#46ec13]">
                  最受欢迎
                </div>
              ) : null}
              <div className="text-sm text-white/50">{p.tag}</div>
              <div className="mt-2 text-xl font-semibold">{p.name}</div>
              <div className="mt-4 flex items-baseline gap-1">
                <span className="text-3xl font-extrabold">{p.price}</span>
                <span className="text-sm text-white/50">{p.period}</span>
              </div>
              <ul className="mt-6 space-y-2.5 text-sm">
                {p.features.map((f) => (
                  <li key={f} className="flex items-start gap-2 text-white/75">
                    <CheckCircle2 className="w-4 h-4 mt-0.5 text-[#46ec13] shrink-0" />
                    <span>{f}</span>
                  </li>
                ))}
              </ul>
              <Link to="/register" className="block mt-8">
                <Button
                  className={
                    p.highlight
                      ? 'w-full bg-[#46ec13] hover:bg-[#37c00c] text-[#060a07] font-semibold'
                      : 'w-full bg-white/5 hover:bg-white/10 border border-white/10 text-white'
                  }
                >
                  选择该方案
                </Button>
              </Link>
            </div>
          ))}
        </div>

        <div className="mt-16 rounded-2xl border border-white/[0.06] bg-white/[0.02] p-8 text-sm text-white/65 leading-relaxed">
          <h2 className="text-lg font-semibold text-white mb-3">常见问题</h2>
          <ul className="space-y-3">
            <li>
              <span className="text-white">1. 额度不足怎么办？</span>
              可以在控制台购买"加油包"，按需叠加处理分钟数。
            </li>
            <li>
              <span className="text-white">2. 是否支持发票？</span>
              专业版与企业版均提供电子发票或增值税专票。
            </li>
            <li>
              <span className="text-white">3. 可以退款吗？</span>
              14 天内如未使用超过 10% 额度，支持无理由退款。
            </li>
          </ul>
        </div>
      </section>
    </MarketingLayout>
  );
}
