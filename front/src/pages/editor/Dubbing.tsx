import { useMemo, useState } from 'react';
import { useNavigate, useOutletContext, useParams } from 'react-router-dom';
import {
  AlertTriangle,
  Check,
  Copy,
  Download,
  FileAudio,
  Film,
  Loader2,
  Mic,
  Play,
  Plus,
  RefreshCcw,
  Save,
  Scissors,
  Sparkles,
  Trash2,
  UploadCloud,
  Volume2,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Slider } from '@/components/ui/slider';
import {
  type Project,
  type ScriptItem,
  updateProject,
} from '@/lib/projects-store';
import { cn } from '@/lib/utils';
import { toast } from 'sonner';

type Ctx = { project?: Project };

type Tier = 'basic' | 'premium';
type VoiceMode = 'builtin' | 'clone';
type AudioStatus = 'pending' | 'ready' | 'generating';

type Voice = {
  id: string;
  name: string;
  tier: Tier;
  desc: string;
};

const BUILTIN_VOICES: Voice[] = [
  { id: 'zh-CN-XiaoxiaoNeural', name: 'Xiaoxiao', tier: 'basic', desc: '女声 · 温暖柔和' },
  { id: 'zh-CN-YunxiNeural', name: 'Yunxi', tier: 'basic', desc: '男声 · 沉稳磁性' },
  { id: 'zh-CN-XiaoyiNeural', name: 'Xiaoyi', tier: 'basic', desc: '女声 · 活泼明亮' },
  { id: 'zh-CN-YunyangNeural', name: 'Yunyang', tier: 'basic', desc: '男声 · 新闻播报' },
  { id: 'zh-CN-XiaomoNeural', name: 'Xiaomo', tier: 'basic', desc: '女声 · 电影解说' },
  { id: 'zh-CN-YunjianNeural', name: 'Yunjian', tier: 'basic', desc: '男声 · 纪录片' },
  { id: 'zh-CN-XiaoruiNeural', name: 'Xiaorui', tier: 'premium', desc: '女声 · 情感丰沛' },
  { id: 'zh-CN-YunhaoNeural', name: 'Yunhao', tier: 'premium', desc: '男声 · 激情热血' },
];

export default function DubbingPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { project } = useOutletContext<Ctx>();

  const [tier, setTier] = useState<Tier>('basic');
  const [voiceMode, setVoiceMode] = useState<VoiceMode>('builtin');
  const [voiceId, setVoiceId] = useState(
    project?.config?.ttsVoice ?? BUILTIN_VOICES[0].id
  );
  const [rate, setRate] = useState([1]);
  const [volume, setVolume] = useState([1]);

  const initialScript = project?.scriptItems ?? [];
  const [items, setItems] = useState<ScriptItem[]>(initialScript);
  const [audioStatus, setAudioStatus] = useState<Record<string, AudioStatus>>(
    Object.fromEntries(initialScript.map((s) => [s.id, 'pending' as AudioStatus]))
  );
  const [selected, setSelected] = useState<Record<string, boolean>>({});
  const [bulkSynth, setBulkSynth] = useState(false);

  const counts = useMemo(() => {
    const total = items.length;
    const withNarration = items.filter((i) => i.narration.trim().length > 0).length;
    const ready = Object.values(audioStatus).filter((s) => s === 'ready').length;
    return { total, withNarration, ready, pending: total - ready };
  }, [items, audioStatus]);

  if (!id || !project) return null;

  const persist = (next: ScriptItem[]) => {
    setItems(next);
    updateProject(id, { scriptItems: next });
  };

  const patch = (rowId: string, p: Partial<ScriptItem>) =>
    persist(items.map((x) => (x.id === rowId ? { ...x, ...p } : x)));

  const addRow = () => {
    const row: ScriptItem = {
      id: `s-${Date.now()}`,
      startTime: '00:00:00,000',
      endTime: '00:00:05,000',
      originalSubtitle: '',
      narration: '',
    };
    persist([...items, row]);
  };

  const removeRow = (rowId: string) => {
    persist(items.filter((x) => x.id !== rowId));
    setAudioStatus((s) => {
      const { [rowId]: _, ...rest } = s;
      return rest;
    });
  };

  const copyRow = (rowId: string) => {
    const idx = items.findIndex((x) => x.id === rowId);
    if (idx === -1) return;
    const src = items[idx];
    const clone: ScriptItem = { ...src, id: `s-${Date.now()}` };
    const next = [...items];
    next.splice(idx + 1, 0, clone);
    persist(next);
  };

  const genOne = async (rowId: string) => {
    setAudioStatus((s) => ({ ...s, [rowId]: 'generating' }));
    await new Promise((r) => setTimeout(r, 900));
    setAudioStatus((s) => ({ ...s, [rowId]: 'ready' }));
    toast.success('音频生成完成');
  };

  const genAll = async () => {
    if (items.length === 0) {
      toast.error('没有可生成的脚本片段');
      return;
    }
    setBulkSynth(true);
    try {
      for (const it of items) {
        setAudioStatus((s) => ({ ...s, [it.id]: 'generating' }));
        await new Promise((r) => setTimeout(r, 450));
        setAudioStatus((s) => ({ ...s, [it.id]: 'ready' }));
      }
      toast.success(`全部 ${items.length} 段配音生成完成`);
    } finally {
      setBulkSynth(false);
    }
  };

  const downloadScript = () => {
    const payload = items.map((s, i) => ({
      序号: i + 1,
      开始时间: s.startTime,
      结束时间: s.endTime,
      原始字幕: s.originalSubtitle,
      解说词: s.narration,
    }));
    const blob = new Blob([JSON.stringify(payload, null, 2)], {
      type: 'application/json',
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${project.name || 'script'}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const saveScript = () => {
    updateProject(id, {
      scriptItems: items,
      config: { ...(project.config ?? {}), ttsVoice: voiceId },
    });
    toast.success('脚本已保存');
  };

  const refresh = () => {
    toast.info('已刷新最新脚本');
  };

  const hasVideo = !!project.videoUrl;

  return (
    <div className="container-page py-8 space-y-6">
      <header className="flex items-start justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold">配音制作</h1>
          <p className="text-sm text-white/55 mt-1">
            管理脚本内容，生成配音音频，校准时间戳并合成最终视频。
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={downloadScript}
            className="border-white/15 bg-transparent text-white hover:bg-white/5"
          >
            <Download className="w-4 h-4 mr-1" /> 下载脚本
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={refresh}
            className="border-white/15 bg-transparent text-white hover:bg-white/5"
          >
            <RefreshCcw className="w-4 h-4 mr-1" /> 刷新数据
          </Button>
        </div>
      </header>

      {/* Service tier card */}
      <section className="rounded-2xl border border-white/[0.06] bg-white/[0.02] p-5">
        <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
          <div>
            <h3 className="font-semibold">服务等级</h3>
            <p className="text-xs text-white/55 mt-1 max-w-2xl">
              Basic 等级使用开源 TTS，无 token 消耗；Premium 等级启用高级合成模型，音质更自然稳定。
            </p>
          </div>
          <div className="flex items-center gap-2">
            {(['basic', 'premium'] as Tier[]).map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => setTier(t)}
                className={cn(
                  'rounded-xl border px-4 py-2 text-left min-w-[180px]',
                  tier === t
                    ? 'border-[#46ec13] bg-[#46ec13]/10'
                    : 'border-white/10 bg-white/[0.02] hover:border-white/25'
                )}
              >
                <div className="flex items-center gap-2 text-sm font-semibold">
                  <span
                    className={cn(
                      'w-3.5 h-3.5 rounded-full border inline-block',
                      tier === t
                        ? 'border-[#46ec13] bg-[#46ec13]'
                        : 'border-white/40'
                    )}
                  />
                  {t === 'basic' ? 'Basic（免费）' : 'Premium（进阶）'}
                </div>
                <div className="text-[11px] text-white/55 mt-1">
                  {t === 'basic'
                    ? '开源 TTS，不消耗 token'
                    : '高级模型，按字符计费'}
                </div>
              </button>
            ))}
          </div>
        </div>
      </section>

      {/* Voice + sliders */}
      <section className="rounded-2xl border border-white/[0.06] bg-white/[0.02] p-5 space-y-5">
        <header className="flex items-center gap-3">
          <span
            className="w-9 h-9 rounded-full flex items-center justify-center"
            style={{ background: 'rgba(70,236,19,0.12)', color: '#46ec13' }}
          >
            <Mic className="w-4 h-4" />
          </span>
          <div>
            <h3 className="font-semibold">音色选择</h3>
            <p className="text-xs text-white/50">选择内置音色，或稍后接入自定义克隆音色</p>
          </div>
        </header>

        <div className="space-y-3">
          <label className="inline-flex items-center gap-2 text-sm">
            <input
              type="radio"
              name="voice-mode"
              checked={voiceMode === 'builtin'}
              onChange={() => setVoiceMode('builtin')}
              className="accent-[#46ec13]"
            />
            内置音色
          </label>

          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
            {BUILTIN_VOICES.filter((v) => tier === 'premium' || v.tier === 'basic').map(
              (v) => {
                const active = voiceMode === 'builtin' && voiceId === v.id;
                return (
                  <button
                    type="button"
                    key={v.id}
                    onClick={() => {
                      setVoiceMode('builtin');
                      setVoiceId(v.id);
                    }}
                    className={cn(
                      'text-left rounded-xl border p-3 transition relative group',
                      active
                        ? 'border-[#46ec13] bg-[#46ec13]/[0.06]'
                        : 'border-white/10 bg-white/[0.02] hover:border-white/25'
                    )}
                  >
                    {active ? (
                      <span className="absolute top-2 right-2 w-4 h-4 rounded-full bg-[#46ec13] text-[#060a07] flex items-center justify-center">
                        <Check className="w-3 h-3" />
                      </span>
                    ) : null}
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <div className="text-sm font-semibold">{v.name}</div>
                        <div className="text-[11px] text-white/50 mt-0.5">{v.desc}</div>
                      </div>
                    </div>
                    <div className="flex items-center justify-between mt-3">
                      <span
                        className={cn(
                          'text-[10px] px-1.5 py-0.5 rounded',
                          v.tier === 'basic'
                            ? 'bg-white/5 text-white/60'
                            : 'bg-[#46ec13]/15 text-[#46ec13]'
                        )}
                      >
                        {v.tier === 'basic' ? 'Basic' : 'Premium'}
                      </span>
                      <span
                        onClick={(e) => {
                          e.stopPropagation();
                          toast.info(`试听：${v.name}`);
                        }}
                        className="w-7 h-7 rounded-full flex items-center justify-center bg-[#46ec13] text-[#060a07]"
                      >
                        <Play className="w-3.5 h-3.5 ml-0.5" />
                      </span>
                    </div>
                  </button>
                );
              }
            )}
          </div>

          <label className="inline-flex items-center gap-2 text-sm text-white/50 cursor-not-allowed">
            <input
              type="radio"
              name="voice-mode"
              checked={voiceMode === 'clone'}
              onChange={() => {
                setVoiceMode('clone');
                toast.info('克隆音色能力即将上线');
              }}
              className="accent-[#46ec13]"
            />
            克隆音色（即将上线）
          </label>
        </div>

        <div className="grid md:grid-cols-2 gap-4">
          <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-4">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-sm font-semibold">语速控制</div>
                <div className="text-[11px] text-white/50">调整整体语速，范围 0.5x - 1.5x</div>
              </div>
              <div className="text-sm font-mono text-[#46ec13]">{rate[0].toFixed(2)}x</div>
            </div>
            <Slider
              value={rate}
              min={0.5}
              max={1.5}
              step={0.05}
              onValueChange={setRate}
              className="mt-3"
            />
          </div>
          <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-4">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-sm font-semibold flex items-center gap-2">
                  <Volume2 className="w-4 h-4 text-white/60" /> 音量控制
                </div>
                <div className="text-[11px] text-white/50">调整配音音量倍数，1.0 = 原音量</div>
              </div>
              <div className="text-sm font-mono text-[#46ec13]">{volume[0].toFixed(2)}x</div>
            </div>
            <Slider
              value={volume}
              min={0}
              max={2}
              step={0.05}
              onValueChange={setVolume}
              className="mt-3"
            />
          </div>
        </div>
      </section>

      {/* Dubbing script table */}
      <section className="rounded-2xl border border-white/[0.06] bg-white/[0.02]">
        <div className="flex items-center justify-between px-5 py-4 border-b border-white/5 flex-wrap gap-3">
          <div className="flex items-center gap-3">
            <h2 className="font-semibold">配音脚本</h2>
            <div className="text-xs text-white/50 flex items-center gap-2">
              <span>共 {counts.total} 项</span>
              <span className="text-white/20">|</span>
              <span>解说 {counts.withNarration} 项</span>
              <span className="text-white/20">|</span>
              <span className="text-[#46ec13]">已配音 {counts.ready}</span>
              <span className="text-white/20">|</span>
              <span className="text-amber-400">待配音 {counts.pending}</span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button
              onClick={genAll}
              disabled={bulkSynth || items.length === 0}
              size="sm"
              className="bg-[#46ec13] hover:bg-[#37c00c] text-[#060a07] font-semibold"
            >
              {bulkSynth ? (
                <>
                  <Loader2 className="w-4 h-4 mr-1 animate-spin" /> 生成中…
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4 mr-1" /> 生成全部音频
                </>
              )}
            </Button>
            <Button
              onClick={saveScript}
              size="sm"
              variant="outline"
              className="border-white/15 bg-transparent text-white hover:bg-white/5"
            >
              <Save className="w-4 h-4 mr-1" /> 保存脚本
            </Button>
            <Button
              onClick={addRow}
              size="sm"
              variant="ghost"
              className="text-white/70 hover:text-white hover:bg-white/5"
            >
              <Plus className="w-4 h-4 mr-1" /> 添加
            </Button>
          </div>
        </div>

        {items.length === 0 ? (
          <EmptyState onAdd={addRow} onBack={() => navigate(`/projects/${id}/analysis`)} />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm min-w-[1100px]">
              <thead className="bg-white/[0.03] text-white/55 text-left">
                <tr>
                  <th className="px-4 py-3 font-normal w-10">
                    <Checkbox
                      checked={items.length > 0 && items.every((i) => selected[i.id])}
                      onCheckedChange={(v) => {
                        const next: Record<string, boolean> = {};
                        if (v) items.forEach((i) => (next[i.id] = true));
                        setSelected(next);
                      }}
                    />
                  </th>
                  <th className="px-3 py-3 font-normal w-12">序号</th>
                  <th className="px-3 py-3 font-normal w-32">开始时间</th>
                  <th className="px-3 py-3 font-normal w-32">结束时间</th>
                  <th className="px-3 py-3 font-normal">原始字幕</th>
                  <th className="px-3 py-3 font-normal">解说词</th>
                  <th className="px-3 py-3 font-normal w-24">音频状态</th>
                  <th className="px-3 py-3 font-normal w-20">音频操作</th>
                  <th className="px-3 py-3 font-normal w-24 text-right">操作</th>
                </tr>
              </thead>
              <tbody>
                {items.map((row, idx) => {
                  const st = audioStatus[row.id] ?? 'pending';
                  return (
                    <tr key={row.id} className="border-t border-white/5 align-top">
                      <td className="px-4 py-3">
                        <Checkbox
                          checked={!!selected[row.id]}
                          onCheckedChange={(v) =>
                            setSelected((s) => ({ ...s, [row.id]: Boolean(v) }))
                          }
                        />
                      </td>
                      <td className="px-3 py-3 text-white/70">{idx + 1}</td>
                      <td className="px-3 py-3">
                        <Input
                          value={row.startTime}
                          onChange={(e) => patch(row.id, { startTime: e.target.value })}
                          className="bg-[#0f1611] border-white/10 h-8 text-xs font-mono"
                        />
                      </td>
                      <td className="px-3 py-3">
                        <Input
                          value={row.endTime}
                          onChange={(e) => patch(row.id, { endTime: e.target.value })}
                          className="bg-[#0f1611] border-white/10 h-8 text-xs font-mono"
                        />
                      </td>
                      <td className="px-3 py-3">
                        <Input
                          value={row.originalSubtitle}
                          onChange={(e) =>
                            patch(row.id, { originalSubtitle: e.target.value })
                          }
                          placeholder="原始字幕"
                          className="bg-[#0f1611] border-white/10 h-8 text-xs"
                        />
                      </td>
                      <td className="px-3 py-3">
                        <Input
                          value={row.narration}
                          onChange={(e) => patch(row.id, { narration: e.target.value })}
                          placeholder="新解说词"
                          className="bg-[#0f1611] border-white/10 h-8 text-xs"
                        />
                      </td>
                      <td className="px-3 py-3">
                        <AudioStatusBadge status={st} />
                      </td>
                      <td className="px-3 py-3">
                        <div className="flex items-center gap-1">
                          <button
                            type="button"
                            disabled={st === 'generating'}
                            onClick={() => genOne(row.id)}
                            className={cn(
                              'w-7 h-7 rounded-md flex items-center justify-center border transition',
                              st === 'ready'
                                ? 'border-[#46ec13]/40 text-[#46ec13] hover:bg-[#46ec13]/10'
                                : 'border-white/10 text-white/65 hover:text-white hover:bg-white/5',
                              st === 'generating' && 'opacity-50'
                            )}
                            title={st === 'ready' ? '重新生成' : '生成音频'}
                          >
                            {st === 'generating' ? (
                              <Loader2 className="w-3.5 h-3.5 animate-spin" />
                            ) : (
                              <RefreshCcw className="w-3.5 h-3.5" />
                            )}
                          </button>
                          <button
                            type="button"
                            onClick={() =>
                              toast.info(`试听第 ${idx + 1} 段`)
                            }
                            disabled={st !== 'ready'}
                            className={cn(
                              'w-7 h-7 rounded-md flex items-center justify-center border',
                              st === 'ready'
                                ? 'border-[#46ec13]/40 text-[#46ec13] hover:bg-[#46ec13]/10'
                                : 'border-white/10 text-white/30 cursor-not-allowed'
                            )}
                            title="试听"
                          >
                            <Play className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </td>
                      <td className="px-3 py-3">
                        <div className="flex items-center justify-end gap-1">
                          <button
                            onClick={() => copyRow(row.id)}
                            className="w-7 h-7 rounded-md flex items-center justify-center text-white/55 hover:text-white hover:bg-white/5"
                            title="复制行"
                          >
                            <Copy className="w-3.5 h-3.5" />
                          </button>
                          <button
                            onClick={() => removeRow(row.id)}
                            className="w-7 h-7 rounded-md flex items-center justify-center text-white/55 hover:text-red-400 hover:bg-white/5"
                            title="删除"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Final synthesis action bar */}
      <section
        className={cn(
          'rounded-2xl border p-5 flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4',
          hasVideo
            ? 'border-white/[0.06] bg-white/[0.02]'
            : 'border-amber-400/20 bg-amber-400/[0.04]'
        )}
      >
        <div className="flex items-start gap-3">
          <span
            className={cn(
              'w-9 h-9 rounded-full flex items-center justify-center shrink-0',
              hasVideo ? 'bg-[#46ec13]/12 text-[#46ec13]' : 'bg-amber-400/15 text-amber-400'
            )}
          >
            {hasVideo ? <Film className="w-4 h-4" /> : <AlertTriangle className="w-4 h-4" />}
          </span>
          <div className="text-sm">
            {hasVideo ? (
              <>
                <div className="font-semibold">已准备就绪</div>
                <div className="text-white/60 text-xs mt-1">
                  所有配音音频都可用后，可导出到剪映草稿或一键合成成片。
                </div>
              </>
            ) : (
              <>
                <div className="font-semibold text-amber-200">缺少原始视频文件</div>
                <div className="text-white/60 text-xs mt-1">
                  出于安全考虑，原始素材仅在浏览器本地处理，请重新上传后再尝试合成。
                </div>
              </>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <Button
            variant="outline"
            size="sm"
            onClick={() => navigate(`/projects/${id}/material`)}
            className="border-white/15 bg-transparent text-white hover:bg-white/5"
          >
            <UploadCloud className="w-4 h-4 mr-1" /> 上传视频
          </Button>
          <Button
            size="sm"
            disabled={!hasVideo || counts.ready === 0}
            variant="outline"
            className="border-white/15 bg-transparent text-white hover:bg-white/5 disabled:opacity-40"
            onClick={() => toast.success('已导出剪映草稿')}
          >
            <Scissors className="w-4 h-4 mr-1" /> 导出到剪映草稿
          </Button>
          <Button
            size="sm"
            disabled={!hasVideo || counts.ready === 0}
            onClick={() => {
              updateProject(id, { status: 'exported' });
              toast.success('视频合成已开始');
            }}
            className="bg-[#46ec13] hover:bg-[#37c00c] text-[#060a07] font-semibold disabled:opacity-40"
          >
            <FileAudio className="w-4 h-4 mr-1" /> 开始视频合成
          </Button>
        </div>
      </section>
    </div>
  );
}

function AudioStatusBadge({ status }: { status: AudioStatus }) {
  if (status === 'ready') {
    return (
      <span className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded bg-[#46ec13]/10 text-[#46ec13]">
        <Check className="w-3 h-3" /> 已生成
      </span>
    );
  }
  if (status === 'generating') {
    return (
      <span className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded bg-white/5 text-white/70">
        <Loader2 className="w-3 h-3 animate-spin" /> 生成中
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded bg-amber-400/10 text-amber-300">
      <AlertTriangle className="w-3 h-3" /> 未生成
    </span>
  );
}

function EmptyState({
  onAdd,
  onBack,
}: {
  onAdd: () => void;
  onBack: () => void;
}) {
  return (
    <div className="py-16 flex flex-col items-center justify-center gap-4 text-sm">
      <div
        className="w-14 h-14 rounded-full flex items-center justify-center"
        style={{ background: 'rgba(70,236,19,0.12)', color: '#46ec13' }}
      >
        <FileAudio className="w-6 h-6" />
      </div>
      <div className="font-semibold">尚未生成脚本</div>
      <p className="text-white/50 max-w-md text-center">
        请先返回「分析」页面生成剪辑脚本，再回到这里进行配音合成；或手动添加一条解说词。
      </p>
      <div className="flex gap-2">
        <Button
          size="sm"
          onClick={onAdd}
          variant="outline"
          className="border-white/15 bg-transparent text-white hover:bg-white/5"
        >
          <Plus className="w-4 h-4 mr-1" /> 添加一条
        </Button>
        <Button
          size="sm"
          onClick={onBack}
          className="bg-[#46ec13] hover:bg-[#37c00c] text-[#060a07] font-semibold"
        >
          <Sparkles className="w-4 h-4 mr-1" /> 返回分析页面
        </Button>
      </div>
    </div>
  );
}
