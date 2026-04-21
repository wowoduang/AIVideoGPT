import { useRef, useState } from 'react';
import { useNavigate, useOutletContext, useParams } from 'react-router-dom';
import {
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  FolderUp,
  RefreshCcw,
  UploadCloud,
  Wand2,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';
import {
  type Project,
  updateProject,
} from '@/lib/projects-store';
import { toast } from 'sonner';

type Ctx = { project?: Project };

const STEPS = [
  { key: 'upload', label: '视频上传' },
  { key: 'config', label: '参数配置' },
  { key: 'generate', label: '内容生成' },
] as const;

type StepKey = (typeof STEPS)[number]['key'];

export default function MaterialPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { project } = useOutletContext<Ctx>();

  const [step, setStep] = useState<StepKey>(project?.currentStep ?? 'upload');
  const [uploading, setUploading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const fileRef = useRef<HTMLInputElement | null>(null);

  const [cfgLLM, setCfgLLM] = useState(project?.config?.llmProvider ?? 'openai');
  const [cfgModel, setCfgModel] = useState(project?.config?.llmModel ?? 'gpt-4o');
  const [cfgStyle, setCfgStyle] = useState(project?.config?.style ?? 'neutral');
  const [cfgTTS, setCfgTTS] = useState(project?.config?.ttsProvider ?? 'edge-tts');
  const [cfgVoice, setCfgVoice] = useState(project?.config?.ttsVoice ?? 'zh-CN-XiaoxiaoNeural');
  const [cfgAspect, setCfgAspect] = useState(project?.config?.aspectRatio ?? '9:16');
  const [prompt, setPrompt] = useState(
    '生成风格活泼、语速适中的解说脚本，突出关键情节冲突与情绪反差。'
  );

  if (!id || !project) {
    return (
      <div className="container-page py-20 text-center text-white/60">
        项目不存在或已被删除。
        <Button className="ml-3" onClick={() => navigate('/projects')}>
          返回项目列表
        </Button>
      </div>
    );
  }

  const handleFile = async (file: File) => {
    setUploading(true);
    try {
      const objectUrl = URL.createObjectURL(file);
      // Simulate progress for a snappy UX; real API integration lives in /lib/api.ts.
      await new Promise((r) => setTimeout(r, 800));
      updateProject(id, {
        videoFileName: file.name,
        videoUrl: objectUrl,
        currentStep: 'upload',
        thumbnailUrl: project.thumbnailUrl,
      });
      toast.success('视频已载入');
    } finally {
      setUploading(false);
    }
  };

  const handleSelect: React.ChangeEventHandler<HTMLInputElement> = (e) => {
    const file = e.target.files?.[0];
    if (file) void handleFile(file);
  };

  const saveConfig = () => {
    updateProject(id, {
      currentStep: 'generate',
      config: {
        llmProvider: cfgLLM,
        llmModel: cfgModel,
        style: cfgStyle,
        ttsProvider: cfgTTS,
        ttsVoice: cfgVoice,
        aspectRatio: cfgAspect,
      },
    });
    setStep('generate');
  };

  const generate = async () => {
    setGenerating(true);
    try {
      await new Promise((r) => setTimeout(r, 1200));
      const now = new Date();
      updateProject(id, {
        status: 'completed',
        currentStep: 'generate',
        scriptItems: [
          {
            id: 's1',
            startTime: '00:00:00,000',
            endTime: '00:00:04,500',
            originalSubtitle: '雨后的长街只剩下零星的脚步声',
            narration: '这是一个属于他的时代——当雨还没停的时候。',
          },
          {
            id: 's2',
            startTime: '00:00:04,500',
            endTime: '00:00:09,200',
            originalSubtitle: '他缓缓抬头，看向远处的灯火',
            narration: '远处的灯火跳动，像命运正在向他低声点头。',
          },
          {
            id: 's3',
            startTime: '00:00:09,200',
            endTime: '00:00:14,000',
            originalSubtitle: '一阵风掠过，吹起衣角',
            narration: '风声里藏着未说出口的抉择，他终于迈出了第一步。',
          },
        ],
      });
      toast.success(`脚本生成完成，共 3 段 · ${now.toLocaleTimeString()}`);
      navigate(`/projects/${id}/analysis`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '生成失败');
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div className="container-page py-8 flex-1 flex flex-col">
      <header className="mb-6">
        <h2 className="text-xl font-bold">
          项目名称：<span className="text-[#46ec13]">{project.name}</span>
        </h2>
        <p className="text-sm text-white/50 mt-1">
          上传您的视频文件，系统将自动提取音频并识别字幕
        </p>
      </header>

      {/* Steps indicator */}
      <div className="flex items-center gap-3 mb-8 text-sm flex-wrap">
        {STEPS.map((s, i) => {
          const active = step === s.key;
          const done =
            STEPS.findIndex((x) => x.key === step) > i ||
            (project.currentStep === 'generate' && s.key !== 'generate');
          return (
            <div key={s.key} className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => setStep(s.key)}
                className={cn(
                  'flex items-center gap-2 px-3 py-1.5 rounded-full border transition',
                  active
                    ? 'border-[#46ec13] bg-[#46ec13]/10 text-[#46ec13]'
                    : done
                      ? 'border-[#46ec13]/30 text-white/80 hover:border-[#46ec13]/60'
                      : 'border-white/10 text-white/55 hover:border-white/25'
                )}
              >
                <span
                  className={cn(
                    'w-5 h-5 rounded-full flex items-center justify-center text-[11px] font-semibold',
                    active || done
                      ? 'bg-[#46ec13] text-[#060a07]'
                      : 'bg-white/10 text-white/70'
                  )}
                >
                  {done ? <CheckCircle2 className="w-3 h-3" /> : i + 1}
                </span>
                {s.label}
              </button>
              {i < STEPS.length - 1 ? (
                <div className="w-8 h-px bg-white/10" />
              ) : null}
            </div>
          );
        })}
      </div>

      {/* Step content */}
      <div className="flex-1">
        {step === 'upload' ? (
          <div
            className={cn(
              'rounded-2xl border-2 border-dashed border-white/10 bg-white/[0.02] p-16 flex flex-col items-center justify-center text-center min-h-[360px]',
              uploading && 'opacity-70'
            )}
          >
            <div
              className="w-16 h-16 rounded-full flex items-center justify-center mb-5"
              style={{ background: 'rgba(70,236,19,0.12)', color: '#46ec13' }}
            >
              <UploadCloud className="w-7 h-7" />
            </div>
            <h3 className="text-lg font-semibold">
              {project.videoFileName ? `已载入：${project.videoFileName}` : '拖拽或选择文件上传'}
            </h3>
            <p className="text-sm text-white/55 mt-2 max-w-md">
              支持 MP4, MOV, AVI, WEBM 等格式，文件大小不超过 1GB，建议视频时长不超过 40 分钟
            </p>
            <input
              ref={fileRef}
              onChange={handleSelect}
              type="file"
              accept="video/*"
              className="hidden"
            />
            <div className="mt-6 flex items-center gap-3">
              <Button
                onClick={() => fileRef.current?.click()}
                disabled={uploading}
                className="bg-[#46ec13] hover:bg-[#37c00c] text-[#060a07] font-semibold rounded-lg px-6"
              >
                <FolderUp className="w-4 h-4 mr-1" />
                {uploading ? '上传中…' : '选择文件'}
              </Button>
              <span className="text-xs text-white/45">
                或从 <a className="text-[#46ec13] hover:underline" href="#">素材库选择</a>
              </span>
            </div>
          </div>
        ) : null}

        {step === 'config' ? (
          <div className="grid md:grid-cols-2 gap-6">
            <div className="rounded-2xl border border-white/[0.06] bg-white/[0.02] p-6 space-y-4">
              <h3 className="font-semibold">AI 脚本生成</h3>
              <div className="grid gap-2">
                <Label className="text-xs text-white/70">LLM 提供商</Label>
                <Select value={cfgLLM} onValueChange={setCfgLLM}>
                  <SelectTrigger className="bg-[#0f1611] border-white/10"><SelectValue /></SelectTrigger>
                  <SelectContent className="bg-[#0b110d] border-white/10 text-white">
                    <SelectItem value="openai">OpenAI</SelectItem>
                    <SelectItem value="gemini">Google Gemini</SelectItem>
                    <SelectItem value="qwen">阿里 Qwen</SelectItem>
                    <SelectItem value="deepseek">DeepSeek</SelectItem>
                    <SelectItem value="siliconflow">SiliconFlow</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-2">
                <Label className="text-xs text-white/70">模型</Label>
                <Input value={cfgModel} onChange={(e) => setCfgModel(e.target.value)} className="bg-[#0f1611] border-white/10" />
              </div>
              <div className="grid gap-2">
                <Label className="text-xs text-white/70">解说风格</Label>
                <Select value={cfgStyle} onValueChange={setCfgStyle}>
                  <SelectTrigger className="bg-[#0f1611] border-white/10"><SelectValue /></SelectTrigger>
                  <SelectContent className="bg-[#0b110d] border-white/10 text-white">
                    <SelectItem value="neutral">中性客观</SelectItem>
                    <SelectItem value="energetic">活泼热血</SelectItem>
                    <SelectItem value="humor">幽默搞笑</SelectItem>
                    <SelectItem value="narrative">叙事深沉</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-2">
                <Label className="text-xs text-white/70">额外 Prompt（可选）</Label>
                <Textarea
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  rows={3}
                  className="bg-[#0f1611] border-white/10"
                />
              </div>
            </div>

            <div className="rounded-2xl border border-white/[0.06] bg-white/[0.02] p-6 space-y-4">
              <h3 className="font-semibold">配音 & 成片</h3>
              <div className="grid gap-2">
                <Label className="text-xs text-white/70">TTS 引擎</Label>
                <Select value={cfgTTS} onValueChange={setCfgTTS}>
                  <SelectTrigger className="bg-[#0f1611] border-white/10"><SelectValue /></SelectTrigger>
                  <SelectContent className="bg-[#0b110d] border-white/10 text-white">
                    <SelectItem value="edge-tts">Edge TTS</SelectItem>
                    <SelectItem value="siliconflow">SiliconFlow</SelectItem>
                    <SelectItem value="volcengine">火山引擎</SelectItem>
                    <SelectItem value="gpt-sovits">GPT-SoVITS</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-2">
                <Label className="text-xs text-white/70">音色</Label>
                <Input value={cfgVoice} onChange={(e) => setCfgVoice(e.target.value)} className="bg-[#0f1611] border-white/10" />
              </div>
              <div className="grid gap-2">
                <Label className="text-xs text-white/70">画面比例</Label>
                <Select value={cfgAspect} onValueChange={setCfgAspect}>
                  <SelectTrigger className="bg-[#0f1611] border-white/10"><SelectValue /></SelectTrigger>
                  <SelectContent className="bg-[#0b110d] border-white/10 text-white">
                    <SelectItem value="9:16">9:16（竖屏 · 抖音/小红书）</SelectItem>
                    <SelectItem value="16:9">16:9（横屏 · YouTube/B 站）</SelectItem>
                    <SelectItem value="1:1">1:1（方形 · Instagram）</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>
        ) : null}

        {step === 'generate' ? (
          <div className="rounded-2xl border border-white/[0.06] bg-white/[0.02] p-10 text-center min-h-[360px] flex flex-col items-center justify-center">
            <div
              className="w-16 h-16 rounded-full flex items-center justify-center mb-5"
              style={{ background: 'rgba(70,236,19,0.12)', color: '#46ec13' }}
            >
              <Wand2 className="w-7 h-7" />
            </div>
            <h3 className="text-lg font-semibold">准备好生成剪辑脚本</h3>
            <p className="text-sm text-white/55 mt-2 max-w-md">
              点击"开始生成"后，系统将自动转写字幕、切分关键片段并撰写解说文案。
            </p>
            <Button
              onClick={generate}
              disabled={generating}
              className="mt-6 bg-[#46ec13] hover:bg-[#37c00c] text-[#060a07] font-semibold rounded-lg px-6 brand-glow"
            >
              {generating ? (
                <>
                  <RefreshCcw className="w-4 h-4 mr-1 animate-spin" /> 生成中…
                </>
              ) : (
                <>
                  <Wand2 className="w-4 h-4 mr-1" /> 开始生成
                </>
              )}
            </Button>
          </div>
        ) : null}
      </div>

      {/* Footer actions */}
      <footer className="mt-8 flex items-center justify-between border-t border-white/5 pt-5">
        <Button
          variant="ghost"
          onClick={() => navigate('/projects')}
          className="text-white/60 hover:text-white"
        >
          <ArrowLeft className="w-4 h-4 mr-1" /> 返回
        </Button>
        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            onClick={() => fileRef.current?.click()}
            className="border-white/15 bg-transparent text-white hover:bg-white/5"
          >
            <UploadCloud className="w-4 h-4 mr-1" /> 重新上传
          </Button>
          {step === 'upload' ? (
            <Button
              disabled={!project.videoUrl}
              onClick={() => setStep('config')}
              className="bg-[#46ec13] hover:bg-[#37c00c] text-[#060a07] font-semibold disabled:opacity-50 disabled:pointer-events-none"
            >
              下一步：配置参数 <ArrowRight className="w-4 h-4 ml-1" />
            </Button>
          ) : null}
          {step === 'config' ? (
            <Button
              onClick={saveConfig}
              className="bg-[#46ec13] hover:bg-[#37c00c] text-[#060a07] font-semibold"
            >
              下一步：生成脚本 <ArrowRight className="w-4 h-4 ml-1" />
            </Button>
          ) : null}
          {step === 'generate' ? (
            <Button
              onClick={() => navigate(`/projects/${id}/analysis`)}
              variant="outline"
              className="border-[#46ec13]/50 text-[#46ec13] bg-transparent hover:bg-[#46ec13]/10"
            >
              查看剪辑脚本 <ArrowRight className="w-4 h-4 ml-1" />
            </Button>
          ) : null}
        </div>
      </footer>
    </div>
  );
}
