import { Link } from 'react-router-dom';
import {
  ArrowRight,
  Sparkles,
  FileText,
  Mic,
  Film,
  Wand2,
  Gauge,
  ShieldCheck,
  Upload,
  Brain,
  Settings,
  PlayCircle,
  CheckCircle2,
  Star,
  Users,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { MarketingLayout } from '@/components/layout/MarketingLayout';

const FEATURES = [
  {
    icon: FileText,
    title: '智能字幕识别',
    desc: '自动识别视频对白与字幕，精准提取时间轴与文本内容',
  },
  {
    icon: Wand2,
    title: 'AI 解说脚本',
    desc: '多 LLM 模型一键生成高质量解说词，风格可定制',
  },
  {
    icon: Mic,
    title: '多引擎配音合成',
    desc: '集成 Edge TSS、火山引擎、SiliconFlow 等主流 TTS 引擎',
  },
  {
    icon: Film,
    title: '智能剪辑合成',
    desc: '根据脚本自动匹配素材，生成成片，支持批量导出',
  },
  {
    icon: Gauge,
    title: '高效工作流',
    desc: '三步完成视频创作：上传素材 → AI 分析 → 一键生成',
  },
  {
    icon: ShieldCheck,
    title: '企业级安全',
    desc: '本地化部署 + 细粒度权限控制，数据全程自主掌控',
  },
];

const STEPS = [
  {
    icon: Upload,
    label: '上传素材',
    desc: '导入视频文件或从素材库选择，支持 MP4/MOV/AVI/WEBM',
  },
  {
    icon: Brain,
    label: 'AI 分析',
    desc: '自动识别字幕、关键片段并生成剪辑脚本',
  },
  {
    icon: Settings,
    label: '参数配置',
    desc: '选择解说风格、配音音色、画面比例等个性化参数',
  },
  {
    icon: PlayCircle,
    label: '一键成片',
    desc: '自动合成视频与配音，一键导出高清成片',
  },
];

const CASES = [
  {
    title: '短视频创作者',
    desc: '批量将影视剧、游戏实况剪辑成解说短视频，效率提升 10 倍',
    img: 'https://images.unsplash.com/photo-1536240478700-b869070f9279?auto=format&fit=crop&w=900&q=60',
  },
  {
    title: '品牌营销团队',
    desc: '品牌故事 / 产品介绍一键生成多语言版本，降低视频制作成本',
    img: 'https://images.unsplash.com/photo-1522204523234-8729aa6e3d5f?auto=format&fit=crop&w=900&q=60',
  },
  {
    title: '教育课程制作',
    desc: '长视频课程自动切片、转写、配音、剪辑，让知识更易触达',
    img: 'https://images.unsplash.com/photo-1516321497487-e288fb19713f?auto=format&fit=crop&w=900&q=60',
  },
];

const PRICING = [
  {
    name: '创作者',
    tag: '适合个人创作者',
    price: '¥0',
    period: '永久免费',
    highlight: false,
    features: ['每月 200 分钟视频处理额度', '3 个同时进行的项目', '基础 TTS 音色', '720P 导出'],
    cta: '免费开始',
  },
  {
    name: '专业版',
    tag: '适合专业工作室',
    price: '¥199',
    period: '/ 月',
    highlight: true,
    features: [
      '每月 2000 分钟视频处理额度',
      '20 个同时进行的项目',
      '全量高级 TTS 音色',
      '1080P/4K 导出',
      '团队共享素材库',
      '优先 GPU 队列',
    ],
    cta: '立即升级',
  },
  {
    name: '企业版',
    tag: '适合企业与团队',
    price: '联系我们',
    period: '',
    highlight: false,
    features: ['无限时长额度', '私有化部署', '专属模型微调', 'SSO / 审计日志', '7x24 技术支持'],
    cta: '预约沟通',
  },
];

const STATS = [
  { value: '10K+', label: '活跃创作者' },
  { value: '2M+', label: '生成视频数' },
  { value: '98%', label: '用户满意度' },
  { value: '50+', label: '支持语音模型' },
];

export default function Landing() {
  return (
    <MarketingLayout>
      {/* HERO */}
      <section className="relative overflow-hidden">
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            background:
              'radial-gradient(ellipse at 30% 20%, rgba(70,236,19,0.22), transparent 60%), radial-gradient(ellipse at 80% 10%, rgba(99,102,241,0.15), transparent 55%)',
          }}
        />
        <div className="container-page relative pt-24 pb-20 text-center">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/5 border border-white/10 text-xs text-white/70 mb-6">
            <Sparkles className="w-3.5 h-3.5 text-[#46ec13]" />
            AI 驱动的视频创作平台
          </div>
          <h1 className="text-4xl md:text-6xl font-extrabold tracking-tight leading-[1.08]">
            <span className="text-white">AIVideoGPT: </span>
            <span className="brand-gradient-text">你的专属视频剪辑智能体</span>
          </h1>
          <p className="mt-6 text-base md:text-lg text-white/65 max-w-2xl mx-auto">
            基于大模型与多模态识别，一键完成脚本撰写、配音合成、智能剪辑，
            让视频创作像打字一样简单。
          </p>
          <div className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-3">
            <Link to="/register">
              <Button
                size="lg"
                className="bg-[#46ec13] hover:bg-[#37c00c] text-[#060a07] font-semibold rounded-full px-8 brand-glow"
              >
                免费开始创作 <ArrowRight className="w-4 h-4 ml-2" />
              </Button>
            </Link>
            <Link to="/cases">
              <Button
                size="lg"
                variant="outline"
                className="rounded-full px-8 border-white/15 text-white hover:bg-white/5"
              >
                查看案例
              </Button>
            </Link>
          </div>

          <div className="mt-16 grid grid-cols-2 md:grid-cols-4 gap-6 max-w-3xl mx-auto">
            {STATS.map((s) => (
              <div key={s.label} className="text-center">
                <div className="text-2xl md:text-3xl font-bold text-[#46ec13]">{s.value}</div>
                <div className="text-xs md:text-sm text-white/55 mt-1">{s.label}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* FEATURES */}
      <section className="container-page py-20">
        <div className="text-center mb-12">
          <h2 className="text-3xl md:text-4xl font-bold">强大的 AI 功能</h2>
          <p className="mt-3 text-white/55">让视频制作更简单高效的智能体组合</p>
        </div>
        <div className="grid gap-5 md:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f) => {
            const Icon = f.icon;
            return (
              <div
                key={f.title}
                className="group rounded-2xl p-6 bg-white/[0.03] border border-white/[0.06] hover:border-[#46ec13]/50 hover:bg-white/[0.05] transition"
              >
                <div
                  className="w-11 h-11 rounded-xl flex items-center justify-center mb-4"
                  style={{
                    background: 'rgba(70, 236, 19, 0.12)',
                    color: '#46ec13',
                  }}
                >
                  <Icon className="w-5 h-5" />
                </div>
                <h3 className="text-lg font-semibold mb-2">{f.title}</h3>
                <p className="text-sm text-white/60 leading-relaxed">{f.desc}</p>
              </div>
            );
          })}
        </div>
      </section>

      {/* STEPS */}
      <section className="bg-[#070c08] border-y border-white/5">
        <div className="container-page py-20">
          <div className="text-center mb-12">
            <h2 className="text-3xl md:text-4xl font-bold">简单四步，视频即成</h2>
            <p className="mt-3 text-white/55">从想法到成片，只需几分钟</p>
          </div>
          <div className="grid gap-6 md:grid-cols-4">
            {STEPS.map((s, i) => {
              const Icon = s.icon;
              return (
                <div
                  key={s.label}
                  className="relative rounded-2xl p-6 bg-white/[0.03] border border-white/[0.06]"
                >
                  <div className="absolute top-5 right-5 text-5xl font-extrabold text-white/[0.04]">
                    0{i + 1}
                  </div>
                  <div
                    className="w-10 h-10 rounded-xl flex items-center justify-center mb-4"
                    style={{
                      background: 'rgba(70, 236, 19, 0.12)',
                      color: '#46ec13',
                    }}
                  >
                    <Icon className="w-5 h-5" />
                  </div>
                  <div className="text-sm text-[#46ec13] font-semibold mb-1">STEP {i + 1}</div>
                  <div className="font-semibold mb-2">{s.label}</div>
                  <div className="text-sm text-white/55 leading-relaxed">{s.desc}</div>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* CASES */}
      <section className="container-page py-20">
        <div className="text-center mb-12">
          <h2 className="text-3xl md:text-4xl font-bold">适用于多种创作场景</h2>
          <p className="mt-3 text-white/55">从个人创作者到企业团队，AIVideoGPT 都能胜任</p>
        </div>
        <div className="grid gap-6 md:grid-cols-3">
          {CASES.map((c) => (
            <div
              key={c.title}
              className="group rounded-2xl overflow-hidden bg-white/[0.03] border border-white/[0.06] hover:border-white/20 transition"
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
                <h3 className="text-lg font-semibold mb-2">{c.title}</h3>
                <p className="text-sm text-white/60 leading-relaxed">{c.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* PRICING */}
      <section className="bg-[#070c08] border-y border-white/5">
        <div className="container-page py-20">
          <div className="text-center mb-12">
            <h2 className="text-3xl md:text-4xl font-bold">灵活的订阅方案</h2>
            <p className="mt-3 text-white/55">从免费开始，按需升级</p>
          </div>
          <div className="grid gap-6 md:grid-cols-3">
            {PRICING.map((p) => (
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
                    {p.cta}
                  </Button>
                </Link>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* TESTIMONIALS */}
      <section className="container-page py-20">
        <div className="text-center mb-12">
          <h2 className="text-3xl md:text-4xl font-bold">创作者怎么说</h2>
        </div>
        <div className="grid gap-6 md:grid-cols-3">
          {[
            { name: '李导演', role: '短视频账号主理人', text: '从写稿到成片，以前要一天，现在半小时搞定，账号更新频率直接翻倍。' },
            { name: 'Nina', role: '品牌内容经理', text: '我们把海外产品介绍视频批量本地化，素材库 + 脚本模板用起来非常顺手。' },
            { name: '阿Ken', role: '教育博主', text: '配音质量接近真人，长课程剪辑成短视频效率提升了 8 倍不止。' },
          ].map((t) => (
            <div key={t.name} className="rounded-2xl p-6 bg-white/[0.03] border border-white/[0.06]">
              <div className="flex gap-1 text-[#46ec13] mb-3">
                {Array.from({ length: 5 }).map((_, i) => (
                  <Star key={i} className="w-4 h-4 fill-[#46ec13]" />
                ))}
              </div>
              <p className="text-sm text-white/80 leading-relaxed">"{t.text}"</p>
              <div className="mt-5 flex items-center gap-3">
                <div className="w-9 h-9 rounded-full bg-white/10 flex items-center justify-center">
                  <Users className="w-4 h-4 text-white/70" />
                </div>
                <div>
                  <div className="text-sm font-semibold">{t.name}</div>
                  <div className="text-xs text-white/50">{t.role}</div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="container-page pb-24">
        <div
          className="relative overflow-hidden rounded-3xl p-10 md:p-16 text-center border border-[#46ec13]/30"
          style={{
            background:
              'radial-gradient(ellipse at 50% 0%, rgba(70,236,19,0.22), transparent 60%), #0a130b',
          }}
        >
          <h2 className="text-3xl md:text-4xl font-bold">准备好让 AI 帮你剪视频了吗？</h2>
          <p className="mt-4 text-white/65 max-w-xl mx-auto">
            注册即送 200 分钟免费额度，几分钟内体验完整的 AI 视频创作流程。
          </p>
          <div className="mt-8 flex items-center justify-center gap-3">
            <Link to="/register">
              <Button
                size="lg"
                className="bg-[#46ec13] hover:bg-[#37c00c] text-[#060a07] font-semibold rounded-full px-8 brand-glow"
              >
                免费开始创作 <ArrowRight className="w-4 h-4 ml-2" />
              </Button>
            </Link>
            <Link to="/pricing">
              <Button
                size="lg"
                variant="outline"
                className="rounded-full px-8 border-white/20 text-white hover:bg-white/5"
              >
                查看定价
              </Button>
            </Link>
          </div>
        </div>
      </section>
    </MarketingLayout>
  );
}
