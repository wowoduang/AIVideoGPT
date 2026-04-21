import { useState } from 'react';
import { useNavigate, useOutletContext, useParams } from 'react-router-dom';
import { ArrowLeft, Mic, PlayCircle, Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Slider } from '@/components/ui/slider';
import { type Project } from '@/lib/projects-store';
import { toast } from 'sonner';

type Ctx = { project?: Project };

export default function DubbingPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { project } = useOutletContext<Ctx>();
  const hasScript = !!project?.scriptItems && project.scriptItems.length > 0;
  const [voice, setVoice] = useState(project?.config?.ttsVoice ?? 'zh-CN-XiaoxiaoNeural');
  const [rate, setRate] = useState([1]);
  const [pitch, setPitch] = useState([1]);
  const [synthing, setSynthing] = useState(false);

  const synth = async () => {
    setSynthing(true);
    await new Promise((r) => setTimeout(r, 1200));
    setSynthing(false);
    toast.success('所有片段配音合成完成');
  };

  if (!id || !project) return null;

  if (!hasScript) {
    return (
      <div className="container-page py-24 text-center">
        <h2 className="text-3xl font-bold">脚本未生成</h2>
        <p className="mt-3 text-sm text-white/55">请先在分析阶段生成或编辑脚本。</p>
        <Button
          onClick={() => navigate(`/projects/${id}/analysis`)}
          className="mt-6 bg-[#46ec13] hover:bg-[#37c00c] text-[#060a07] font-semibold"
        >
          <Sparkles className="w-4 h-4 mr-1" /> 返回分析页面
        </Button>
      </div>
    );
  }

  return (
    <div className="container-page py-8">
      <header className="mb-6">
        <h2 className="text-2xl font-bold">配音合成</h2>
        <p className="text-sm text-white/55 mt-1">为每条解说词生成语音并与原视频合成成片</p>
      </header>

      <div className="grid lg:grid-cols-[320px,1fr] gap-6">
        <aside className="rounded-2xl border border-white/[0.06] bg-white/[0.02] p-5 space-y-4 h-max">
          <h3 className="font-semibold flex items-center gap-2">
            <Mic className="w-4 h-4 text-[#46ec13]" /> 语音参数
          </h3>
          <div className="space-y-2">
            <Label className="text-xs text-white/70">音色</Label>
            <Select value={voice} onValueChange={setVoice}>
              <SelectTrigger className="bg-[#0f1611] border-white/10"><SelectValue /></SelectTrigger>
              <SelectContent className="bg-[#0b110d] border-white/10 text-white">
                <SelectItem value="zh-CN-XiaoxiaoNeural">Xiaoxiao（女声 · 柔和）</SelectItem>
                <SelectItem value="zh-CN-YunxiNeural">Yunxi（男声 · 青年）</SelectItem>
                <SelectItem value="zh-CN-XiaoyiNeural">Xiaoyi（女声 · 活力）</SelectItem>
                <SelectItem value="zh-CN-YunyangNeural">Yunyang（男声 · 新闻）</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label className="text-xs text-white/70">语速 ({rate[0].toFixed(2)}x)</Label>
            <Slider
              value={rate}
              min={0.5}
              max={1.5}
              step={0.05}
              onValueChange={setRate}
            />
          </div>
          <div className="space-y-2">
            <Label className="text-xs text-white/70">音高 ({pitch[0].toFixed(2)})</Label>
            <Slider
              value={pitch}
              min={0.5}
              max={1.5}
              step={0.05}
              onValueChange={setPitch}
            />
          </div>
          <Button
            onClick={synth}
            disabled={synthing}
            className="w-full bg-[#46ec13] hover:bg-[#37c00c] text-[#060a07] font-semibold"
          >
            {synthing ? '合成中…' : '一键合成全部配音'}
          </Button>
        </aside>

        <section className="rounded-2xl border border-white/[0.06] bg-white/[0.02] p-5">
          <h3 className="font-semibold mb-4">解说词预览（{project.scriptItems!.length} 段）</h3>
          <ul className="space-y-3">
            {project.scriptItems!.map((s, i) => (
              <li
                key={s.id}
                className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-4 flex items-start gap-3"
              >
                <div className="shrink-0 w-8 h-8 rounded-full bg-white/5 text-white/70 flex items-center justify-center text-xs font-semibold">
                  {i + 1}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-[11px] text-white/45 font-mono mb-1">
                    {s.startTime} → {s.endTime}
                  </div>
                  <div className="text-sm text-white/85 leading-relaxed">{s.narration}</div>
                  {s.originalSubtitle ? (
                    <div className="text-xs text-white/40 mt-1">原：{s.originalSubtitle}</div>
                  ) : null}
                </div>
                <Button
                  size="sm"
                  variant="ghost"
                  className="text-[#46ec13] hover:bg-[#46ec13]/10"
                  onClick={() => toast.info(`已播放第 ${i + 1} 段预览`)}
                >
                  <PlayCircle className="w-4 h-4 mr-1" /> 预听
                </Button>
              </li>
            ))}
          </ul>
        </section>
      </div>

      <div className="mt-6 flex items-center justify-between">
        <Button
          variant="ghost"
          onClick={() => navigate(`/projects/${id}/analysis`)}
          className="text-white/60 hover:text-white"
        >
          <ArrowLeft className="w-4 h-4 mr-1" /> 返回脚本
        </Button>
        <Button
          onClick={() => {
            toast.success('已导出成片');
            navigate('/projects');
          }}
          className="bg-[#46ec13] hover:bg-[#37c00c] text-[#060a07] font-semibold"
        >
          导出成片
        </Button>
      </div>
    </div>
  );
}
