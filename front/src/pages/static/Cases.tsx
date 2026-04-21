import { MarketingLayout } from '@/components/layout/MarketingLayout';
import { Sparkles, TrendingUp, Users } from 'lucide-react';

const CASES = [
  {
    title: '头部影视解说账号：日更效率提升 12 倍',
    org: '短视频 MCN',
    img: 'https://images.unsplash.com/photo-1536440136628-849c177e76a1?auto=format&fit=crop&w=1200&q=60',
    stat: '12x',
    statLabel: '产出提速',
    desc: '通过 AIVideoGPT 的多模型脚本生成 + 批量配音，将日更任务由 3 人工 8 小时缩减至 1 人 1 小时。',
  },
  {
    title: '连锁品牌出海：多语言版本一键生成',
    org: '美妆品牌营销部',
    img: 'https://images.unsplash.com/photo-1522204523234-8729aa6e3d5f?auto=format&fit=crop&w=1200&q=60',
    stat: '7+',
    statLabel: '语种覆盖',
    desc: '中英日韩西法德 7 种语言版本的产品视频同时产出，减少外部译制供应商预算 60%。',
  },
  {
    title: '知识付费课程：长视频切片 + 配音 + 剪辑',
    org: '在线教育机构',
    img: 'https://images.unsplash.com/photo-1516321497487-e288fb19713f?auto=format&fit=crop&w=1200&q=60',
    stat: '8x',
    statLabel: '剪辑提速',
    desc: '将 2 小时录播课自动切片为 20 条精华短视频，留存率提升 31%。',
  },
  {
    title: '游戏实况解说：本地部署 + 批量任务',
    org: '游戏工作室',
    img: 'https://images.unsplash.com/photo-1552820728-8b83bb6b773f?auto=format&fit=crop&w=1200&q=60',
    stat: '100%',
    statLabel: '数据本地化',
    desc: '基于 AIVideoGPT 私有化部署，素材与脚本完全本地存储，生成速度依旧秒级。',
  },
];

export default function CasesPage() {
  return (
    <MarketingLayout>
      <section className="container-page pt-20 pb-10 text-center">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/5 border border-white/10 text-xs text-white/70 mb-6">
          <Sparkles className="w-3.5 h-3.5 text-[#46ec13]" />
          用户案例
        </div>
        <h1 className="text-4xl md:text-5xl font-extrabold">看看他们是如何用 AIVideoGPT 创作的</h1>
        <p className="mt-4 text-white/60 max-w-2xl mx-auto">
          从个人短视频创作者到出海品牌营销团队，AIVideoGPT 正在帮助全球 10K+ 创作者提升视频产出效率。
        </p>
        <div className="mt-8 flex items-center justify-center gap-8 text-sm text-white/60">
          <span className="flex items-center gap-1.5"><Users className="w-4 h-4 text-[#46ec13]" />10K+ 活跃用户</span>
          <span className="flex items-center gap-1.5"><TrendingUp className="w-4 h-4 text-[#46ec13]" />2M+ 生成视频</span>
        </div>
      </section>

      <section className="container-page pb-24 grid gap-6 md:grid-cols-2">
        {CASES.map((c) => (
          <article
            key={c.title}
            className="group rounded-2xl overflow-hidden bg-white/[0.03] border border-white/[0.06] hover:border-[#46ec13]/40 transition"
          >
            <div className="aspect-[16/9] overflow-hidden">
              <img
                src={c.img}
                alt={c.title}
                className="w-full h-full object-cover group-hover:scale-105 transition"
                loading="lazy"
              />
            </div>
            <div className="p-6">
              <div className="text-xs text-[#46ec13] font-semibold">{c.org}</div>
              <h3 className="mt-2 text-lg font-semibold leading-snug">{c.title}</h3>
              <p className="mt-3 text-sm text-white/60 leading-relaxed">{c.desc}</p>
              <div className="mt-4 flex items-center gap-2 text-sm">
                <span className="text-2xl font-extrabold text-[#46ec13]">{c.stat}</span>
                <span className="text-white/55">{c.statLabel}</span>
              </div>
            </div>
          </article>
        ))}
      </section>
    </MarketingLayout>
  );
}
