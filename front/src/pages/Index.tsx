import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import {
  Video,
  FileText,
  Mic,
  Sparkles,
  Play,
  ArrowRight,
  CheckCircle2,
  Layers,
  Wand2,
  Download,
  ChevronRight,
  Zap,
  Brain,
  Clapperboard,
} from 'lucide-react';

const HERO_IMG = 'https://mgx-backend-cdn.metadl.com/generate/images/1135846/2026-04-20/m62flkiaafiq/hero-ai-video-generation.png';
const FEATURE_SCRIPT_IMG = 'https://mgx-backend-cdn.metadl.com/generate/images/1135846/2026-04-20/m62fhuqaafga/feature-smart-script.png';
const FEATURE_VOICE_IMG = 'https://mgx-backend-cdn.metadl.com/generate/images/1135846/2026-04-20/m62fgpyaafia/feature-ai-voice.png';
const USE_CASE_IMG = 'https://mgx-backend-cdn.metadl.com/generate/images/1135846/2026-04-20/m62fjyyaafha/use-case-content-creator.png';

const features = [
  {
    icon: <FileText className="w-6 h-6" />,
    title: '智能字幕识别',
    desc: '自动识别视频中的对话字幕，精准提取时间轴与文本内容',
  },
  {
    icon: <Clapperboard className="w-6 h-6" />,
    title: '智能分镜脚本',
    desc: 'AI 自动分析视频内容，生成结构化分镜脚本与解说文案',
  },
  {
    icon: <Brain className="w-6 h-6" />,
    title: '解说文案生成',
    desc: '基于视频内容智能生成引人入胜的解说文案，支持多种风格',
  },
  {
    icon: <Video className="w-6 h-6" />,
    title: '视频画面分析',
    desc: '深度理解视频画面内容，识别场景、人物、动作等关键元素',
  },
  {
    icon: <Mic className="w-6 h-6" />,
    title: 'AI 配音克隆',
    desc: '多种 TTS 引擎支持，零样本语音克隆，打造专属声音',
  },
  {
    icon: <Download className="w-6 h-6" />,
    title: '快速导出成片',
    desc: '一键合成视频，支持多种分辨率与比例，快速输出成品',
  },
];

const steps = [
  {
    num: '01',
    icon: <UploadIcon />,
    title: '上传视频',
    desc: '上传你的原始视频素材，支持 MP4、MOV 等主流格式',
  },
  {
    num: '02',
    icon: <Sparkles className="w-5 h-5" />,
    title: 'AI 生成脚本',
    desc: 'AI 自动分析视频内容，生成解说文案与分镜脚本',
  },
  {
    num: '03',
    icon: <Wand2 className="w-5 h-5" />,
    title: '编辑调整',
    desc: '在线编辑脚本、调整配音、设置字幕样式与背景音乐',
  },
  {
    num: '04',
    icon: <Play className="w-5 h-5" />,
    title: '导出成片',
    desc: '一键合成并导出高质量视频，快速发布到各平台',
  },
];

const useCases = [
  {
    title: '影视解说创作者',
    desc: '快速生成影视解说视频，从字幕提取到文案生成全流程自动化',
    tags: ['影视解说', '短剧混剪', '精彩粗剪'],
  },
  {
    title: '自媒体内容团队',
    desc: '批量生产高质量视频内容，提升内容产出效率 10 倍以上',
    tags: ['内容批量生产', '多平台分发', '品牌一致性'],
  },
  {
    title: '教育培训机构',
    desc: '将课程视频快速转化为带解说的教学短片，提升学习体验',
    tags: ['课程剪辑', '知识提炼', '教学辅助'],
  },
];

function UploadIcon() {
  return (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
    </svg>
  );
}

export default function Index() {
  const navigate = useNavigate();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  return (
    <div className="min-h-screen bg-[#0A0A0F] text-white overflow-x-hidden">
      {/* Navigation */}
      <nav className="fixed top-0 left-0 right-0 z-50 bg-[#0A0A0F]/80 backdrop-blur-xl border-b border-white/[0.06]">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg gradient-bg flex items-center justify-center">
              <Zap className="w-4 h-4 text-white" />
            </div>
            <span className="text-lg font-bold">AIVideoGPT</span>
          </div>
          <div className="hidden md:flex items-center gap-8">
            <a href="#features" className="text-sm text-slate-400 hover:text-white transition-colors">功能特性</a>
            <a href="#process" className="text-sm text-slate-400 hover:text-white transition-colors">使用流程</a>
            <a href="#usecases" className="text-sm text-slate-400 hover:text-white transition-colors">应用场景</a>
          </div>
          <div className="hidden md:flex items-center gap-3">
            <Button
              variant="ghost"
              className="text-slate-400 hover:text-white"
              onClick={() => navigate('/workspace')}
            >
              登录
            </Button>
            <Button
              className="gradient-bg hover:brightness-110 text-white rounded-xl px-6"
              onClick={() => navigate('/workspace')}
            >
              开始使用
            </Button>
          </div>
          <button
            className="md:hidden text-slate-400"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          >
            <Layers className="w-6 h-6" />
          </button>
        </div>
        {mobileMenuOpen && (
          <div className="md:hidden bg-[#0A0A0F]/95 backdrop-blur-xl border-b border-white/[0.06] px-6 py-4 space-y-3">
            <a href="#features" className="block text-sm text-slate-400 hover:text-white" onClick={() => setMobileMenuOpen(false)}>功能特性</a>
            <a href="#process" className="block text-sm text-slate-400 hover:text-white" onClick={() => setMobileMenuOpen(false)}>使用流程</a>
            <a href="#usecases" className="block text-sm text-slate-400 hover:text-white" onClick={() => setMobileMenuOpen(false)}>应用场景</a>
            <Button className="w-full gradient-bg text-white rounded-xl mt-2" onClick={() => navigate('/workspace')}>
              开始使用
            </Button>
          </div>
        )}
      </nav>

      {/* Hero Section */}
      <section className="relative pt-32 pb-20 px-6">
        <div className="absolute inset-0 overflow-hidden">
          <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-indigo-500/10 rounded-full blur-[128px]" />
          <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-purple-500/10 rounded-full blur-[128px]" />
        </div>
        <div className="relative max-w-7xl mx-auto">
          <div className="text-center max-w-4xl mx-auto">
            <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full border border-indigo-500/30 bg-indigo-500/10 text-indigo-300 text-sm mb-8">
              <Sparkles className="w-4 h-4" />
              <span>AI 驱动的视频创作平台</span>
            </div>
            <h1 className="text-5xl md:text-7xl font-extrabold leading-tight mb-6">
              <span className="gradient-text">AIVideoGPT</span>
              <br />
              <span className="text-white">你的专属视频剪辑智能体</span>
            </h1>
            <p className="text-lg md:text-xl text-slate-400 mb-10 max-w-2xl mx-auto leading-relaxed">
              从字幕识别到脚本生成，从 AI 配音到视频合成，一站式智能视频创作平台，让视频创作效率提升 10 倍
            </p>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
              <Button
                size="lg"
                className="gradient-bg hover:brightness-110 text-white rounded-xl px-8 h-12 text-base glow-md"
                onClick={() => navigate('/workspace')}
              >
                免费开始创作
                <ArrowRight className="w-4 h-4 ml-2" />
              </Button>
              <Button
                size="lg"
                variant="outline"
                className="border-white/10 text-slate-300 hover:bg-white/5 rounded-xl px-8 h-12 text-base"
                onClick={() => document.getElementById('process')?.scrollIntoView({ behavior: 'smooth' })}
              >
                了解更多
              </Button>
            </div>
          </div>
          <div className="mt-16 relative">
            <div className="absolute inset-0 gradient-bg rounded-2xl opacity-20 blur-2xl" />
            <img
              src={HERO_IMG}
              alt="AI Video Generation"
              className="relative w-full rounded-2xl border border-white/10 glow-lg"
            />
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section id="features" className="py-24 px-6">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-3xl md:text-4xl font-bold mb-4">
              强大的 <span className="gradient-text">AI 功能</span>
            </h2>
            <p className="text-slate-400 text-lg max-w-2xl mx-auto">
              全方位 AI 视频创作工具链，覆盖从素材分析到成片输出的完整流程
            </p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {features.map((f, i) => (
              <div
                key={i}
                className="glass-card-hover p-6 group"
              >
                <div className="w-12 h-12 rounded-xl gradient-bg flex items-center justify-center text-white mb-4 group-hover:scale-110 transition-transform">
                  {f.icon}
                </div>
                <h3 className="text-lg font-semibold mb-2">{f.title}</h3>
                <p className="text-slate-400 text-sm leading-relaxed">{f.desc}</p>
              </div>
            ))}
          </div>
          {/* Feature showcase images */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-12">
            <div className="glass-card p-1 overflow-hidden">
              <img src={FEATURE_SCRIPT_IMG} alt="Smart Script" className="w-full rounded-xl" />
              <div className="p-4">
                <h3 className="font-semibold text-lg mb-1">智能脚本生成</h3>
                <p className="text-slate-400 text-sm">AI 深度理解视频内容，自动生成结构化分镜脚本</p>
              </div>
            </div>
            <div className="glass-card p-1 overflow-hidden">
              <img src={FEATURE_VOICE_IMG} alt="AI Voice" className="w-full rounded-xl" />
              <div className="p-4">
                <h3 className="font-semibold text-lg mb-1">AI 配音引擎</h3>
                <p className="text-slate-400 text-sm">多种 TTS 引擎与语音克隆，打造专属声音</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Process Section */}
      <section id="process" className="py-24 px-6 relative">
        <div className="absolute inset-0 bg-gradient-to-b from-transparent via-indigo-500/[0.03] to-transparent" />
        <div className="relative max-w-7xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-3xl md:text-4xl font-bold mb-4">
              简单 <span className="gradient-text">四步</span> 完成创作
            </h2>
            <p className="text-slate-400 text-lg max-w-2xl mx-auto">
              从上传到导出，全流程 AI 辅助，让视频创作变得简单高效
            </p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {steps.map((s, i) => (
              <div key={i} className="relative group">
                <div className="glass-card-hover p-6 h-full">
                  <div className="text-3xl font-black gradient-text mb-4">{s.num}</div>
                  <div className="w-10 h-10 rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 mb-4">
                    {s.icon}
                  </div>
                  <h3 className="text-lg font-semibold mb-2">{s.title}</h3>
                  <p className="text-slate-400 text-sm leading-relaxed">{s.desc}</p>
                </div>
                {i < steps.length - 1 && (
                  <div className="hidden lg:block absolute top-1/2 -right-3 text-indigo-500/40">
                    <ChevronRight className="w-6 h-6" />
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Use Cases Section */}
      <section id="usecases" className="py-24 px-6">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-3xl md:text-4xl font-bold mb-4">
              丰富的 <span className="gradient-text">应用场景</span>
            </h2>
            <p className="text-slate-400 text-lg max-w-2xl mx-auto">
              无论你是影视解说、自媒体还是教育机构，AIVideoGPT 都能满足你的需求
            </p>
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {useCases.map((uc, i) => (
              <div key={i} className="glass-card-hover p-6">
                <h3 className="text-lg font-semibold mb-2">{uc.title}</h3>
                <p className="text-slate-400 text-sm leading-relaxed mb-4">{uc.desc}</p>
                <div className="flex flex-wrap gap-2">
                  {uc.tags.map((tag, j) => (
                    <span
                      key={j}
                      className="px-3 py-1 rounded-full text-xs bg-indigo-500/10 text-indigo-300 border border-indigo-500/20"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
          <div className="mt-12 relative">
            <div className="absolute inset-0 gradient-bg rounded-2xl opacity-10 blur-2xl" />
            <img
              src={USE_CASE_IMG}
              alt="Content Creator"
              className="relative w-full rounded-2xl border border-white/10"
            />
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-24 px-6">
        <div className="max-w-4xl mx-auto text-center">
          <div className="glass-card p-12 md:p-16 relative overflow-hidden">
            <div className="absolute inset-0 gradient-bg opacity-10" />
            <div className="relative">
              <h2 className="text-3xl md:text-4xl font-bold mb-4">
                准备好开始 <span className="gradient-text">AI 视频创作</span> 了吗？
              </h2>
              <p className="text-slate-400 text-lg mb-8 max-w-xl mx-auto">
                加入数千名创作者的行列，用 AI 重新定义视频创作流程
              </p>
              <Button
                size="lg"
                className="gradient-bg hover:brightness-110 text-white rounded-xl px-10 h-14 text-lg glow-md"
                onClick={() => navigate('/workspace')}
              >
                立即开始
                <ArrowRight className="w-5 h-5 ml-2" />
              </Button>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-white/[0.06] py-12 px-6">
        <div className="max-w-7xl mx-auto">
          <div className="flex flex-col md:flex-row items-center justify-between gap-6">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg gradient-bg flex items-center justify-center">
                <Zap className="w-4 h-4 text-white" />
              </div>
              <span className="text-lg font-bold">AIVideoGPT</span>
            </div>
            <div className="flex items-center gap-6 text-sm text-slate-500">
              <span>© 2026 AIVideoGPT</span>
              <a href="#" className="hover:text-slate-300 transition-colors">隐私政策</a>
              <a href="#" className="hover:text-slate-300 transition-colors">使用条款</a>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}