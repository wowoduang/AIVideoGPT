import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { FileText, Plus, Trash2, Sparkles, Upload, ChevronDown, Edit3, Copy } from 'lucide-react';

interface ScriptItem {
  id: number;
  timestamp: string;
  picture: string;
  narration: string;
  ost: number;
}

interface ScriptPanelProps {
  scriptItems: ScriptItem[];
  setScriptItems: React.Dispatch<React.SetStateAction<ScriptItem[]>>;
}

type ScriptMode = 'auto' | 'manual';

export default function ScriptPanel({ scriptItems, setScriptItems }: ScriptPanelProps) {
  const [scriptMode, setScriptMode] = useState<ScriptMode>('auto');
  const [subtitleSource, setSubtitleSource] = useState<'video' | 'audio'>('video');
  const [videoFile, setVideoFile] = useState<string>('');
  const [generating, setGenerating] = useState(false);

  const handleGenerate = () => {
    setGenerating(true);
    setTimeout(() => setGenerating(false), 2000);
  };

  const addItem = () => {
    const newId = scriptItems.length > 0 ? Math.max(...scriptItems.map((i) => i.id)) + 1 : 1;
    setScriptItems([
      ...scriptItems,
      {
        id: newId,
        timestamp: '00:00:00-00:00:00',
        picture: '新分镜描述',
        narration: '新解说文案',
        ost: 0,
      },
    ]);
  };

  const removeItem = (id: number) => {
    setScriptItems(scriptItems.filter((item) => item.id !== id));
  };

  const updateItem = (id: number, field: keyof ScriptItem, value: string | number) => {
    setScriptItems(
      scriptItems.map((item) => (item.id === id ? { ...item, [field]: value } : item))
    );
  };

  return (
    <div className="max-w-3xl space-y-6">
      {/* Script Mode */}
      <section className="glass-card p-5">
        <h3 className="text-sm font-semibold text-slate-300 mb-4 flex items-center gap-2">
          <FileText className="w-4 h-4 text-indigo-400" />
          脚本模式
        </h3>
        <div className="grid grid-cols-2 gap-3">
          <button
            onClick={() => setScriptMode('auto')}
            className={`p-4 rounded-xl border text-left transition-all ${
              scriptMode === 'auto'
                ? 'border-indigo-500/50 bg-indigo-500/10 text-white'
                : 'border-white/[0.06] bg-white/[0.02] text-slate-400 hover:bg-white/[0.04]'
            }`}
          >
            <div className="flex items-center gap-2 mb-1">
              <Sparkles className="w-4 h-4" />
              <span className="font-medium text-sm">自动生成</span>
            </div>
            <p className="text-xs text-slate-500">AI 自动分析视频生成脚本</p>
          </button>
          <button
            onClick={() => setScriptMode('manual')}
            className={`p-4 rounded-xl border text-left transition-all ${
              scriptMode === 'manual'
                ? 'border-indigo-500/50 bg-indigo-500/10 text-white'
                : 'border-white/[0.06] bg-white/[0.02] text-slate-400 hover:bg-white/[0.04]'
            }`}
          >
            <div className="flex items-center gap-2 mb-1">
              <Edit3 className="w-4 h-4" />
              <span className="font-medium text-sm">手动编写</span>
            </div>
            <p className="text-xs text-slate-500">自行编写分镜脚本内容</p>
          </button>
        </div>
      </section>

      {/* Video Source */}
      <section className="glass-card p-5">
        <h3 className="text-sm font-semibold text-slate-300 mb-4 flex items-center gap-2">
          <Upload className="w-4 h-4 text-indigo-400" />
          视频素材
        </h3>
        <div className="border-2 border-dashed border-white/[0.08] rounded-xl p-8 text-center hover:border-indigo-500/30 transition-colors cursor-pointer">
          <Upload className="w-8 h-8 text-slate-500 mx-auto mb-3" />
          <p className="text-sm text-slate-400 mb-1">
            {videoFile || '点击或拖拽上传视频文件'}
          </p>
          <p className="text-xs text-slate-600">支持 MP4、MOV、AVI 等格式</p>
        </div>
        <div className="mt-4">
          <label className="text-xs text-slate-500 mb-2 block">字幕来源</label>
          <div className="grid grid-cols-2 gap-3">
            <button
              onClick={() => setSubtitleSource('video')}
              className={`px-4 py-2.5 rounded-lg text-sm border transition-all ${
                subtitleSource === 'video'
                  ? 'border-indigo-500/50 bg-indigo-500/10 text-white'
                  : 'border-white/[0.06] text-slate-400 hover:bg-white/[0.04]'
              }`}
            >
              视频硬字幕
            </button>
            <button
              onClick={() => setSubtitleSource('audio')}
              className={`px-4 py-2.5 rounded-lg text-sm border transition-all ${
                subtitleSource === 'audio'
                  ? 'border-indigo-500/50 bg-indigo-500/10 text-white'
                  : 'border-white/[0.06] text-slate-400 hover:bg-white/[0.04]'
              }`}
            >
              音频转录
            </button>
          </div>
        </div>
      </section>

      {/* Generate Button */}
      {scriptMode === 'auto' && (
        <Button
          className="w-full gradient-bg hover:brightness-110 text-white rounded-xl h-11 gap-2"
          onClick={handleGenerate}
          disabled={generating}
        >
          <Sparkles className="w-4 h-4" />
          {generating ? 'AI 正在生成脚本...' : 'AI 生成脚本'}
        </Button>
      )}

      {/* Script Items */}
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-slate-300">分镜脚本</h3>
          <Button
            variant="ghost"
            size="sm"
            className="text-indigo-400 hover:text-indigo-300 gap-1"
            onClick={addItem}
          >
            <Plus className="w-4 h-4" />
            添加分镜
          </Button>
        </div>
        {scriptItems.map((item, index) => (
          <div key={item.id} className="glass-card p-4 group">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <span className="text-xs font-mono text-indigo-400 bg-indigo-500/10 px-2 py-0.5 rounded">
                  #{index + 1}
                </span>
                <input
                  type="text"
                  value={item.timestamp}
                  onChange={(e) => updateItem(item.id, 'timestamp', e.target.value)}
                  className="text-xs font-mono text-slate-400 bg-transparent border-none outline-none w-36"
                />
              </div>
              <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                <button className="p-1 rounded hover:bg-white/[0.06] text-slate-500 hover:text-slate-300">
                  <Copy className="w-3.5 h-3.5" />
                </button>
                <button
                  onClick={() => removeItem(item.id)}
                  className="p-1 rounded hover:bg-red-500/10 text-slate-500 hover:text-red-400"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
            <div className="space-y-2">
              <div>
                <label className="text-[10px] uppercase tracking-wider text-slate-600 mb-1 block">画面</label>
                <input
                  type="text"
                  value={item.picture}
                  onChange={(e) => updateItem(item.id, 'picture', e.target.value)}
                  className="w-full text-sm text-slate-300 bg-white/[0.03] border border-white/[0.06] rounded-lg px-3 py-2 outline-none focus:border-indigo-500/40 transition-colors"
                />
              </div>
              <div>
                <label className="text-[10px] uppercase tracking-wider text-slate-600 mb-1 block">解说</label>
                <input
                  type="text"
                  value={item.narration}
                  onChange={(e) => updateItem(item.id, 'narration', e.target.value)}
                  className="w-full text-sm text-slate-300 bg-white/[0.03] border border-white/[0.06] rounded-lg px-3 py-2 outline-none focus:border-indigo-500/40 transition-colors"
                />
              </div>
            </div>
          </div>
        ))}
      </section>
    </div>
  );
}