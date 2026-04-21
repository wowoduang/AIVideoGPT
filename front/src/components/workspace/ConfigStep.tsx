import { Mic, Video, Shuffle, Save, Play, ChevronRight } from 'lucide-react';
import { Button } from '@/components/ui/button';

export type EditMode = 'commentary_only' | 'original_only' | 'smart_insert';

export interface ConfigFormValue {
  editMode: EditMode;
  ttsEngine: string;
  voiceRole: string;
  speed: number;
  aspectRatio: string;
  videoQuality: string;
  subtitleFont: string;
  subtitleSize: number;
  subtitleEnabled: boolean;
}

interface ConfigStepProps {
  projectType: string;
  value: ConfigFormValue;
  onChange: (next: ConfigFormValue) => void;
  onGenerate: () => void;
  generating: boolean;
}

const editModes: { key: EditMode; icon: React.ReactNode; label: string; desc: string }[] = [
  { key: 'commentary_only', icon: <Mic className="w-6 h-6" />, label: '仅解说', desc: '统一声音，节奏可控，全程AI配音解说' },
  { key: 'original_only', icon: <Video className="w-6 h-6" />, label: '仅原片', desc: '保留现场氛围，原声原画呈现' },
  { key: 'smart_insert', icon: <Shuffle className="w-6 h-6" />, label: '智能穿插', desc: '自动平衡画面与解说，智能切换原片与配音' },
];

export default function ConfigStep({ projectType, value, onChange, onGenerate, generating }: ConfigStepProps) {
  const setField = <K extends keyof ConfigFormValue>(key: K, fieldValue: ConfigFormValue[K]) => {
    onChange({ ...value, [key]: fieldValue });
  };

  return (
    <div className="h-full overflow-y-auto px-6 py-4">
      <div className="max-w-3xl mx-auto space-y-6">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h3 className="text-base font-semibold text-white">配置解说参数</h3>
          </div>
          <p className="text-xs text-slate-500 mb-4">基础配置 · 视频剪辑模式 · {projectType}</p>

          <div className="grid grid-cols-3 gap-3">
            {editModes.map((mode) => {
              const isSelected = value.editMode === mode.key;
              return (
                <button
                  key={mode.key}
                  onClick={() => setField('editMode', mode.key)}
                  className={`p-5 rounded-xl border text-left transition-all duration-200 ${
                    isSelected
                      ? 'bg-indigo-500/10 border-indigo-500/50 shadow-lg shadow-indigo-500/5'
                      : 'bg-white/[0.02] border-white/[0.06] hover:border-white/[0.12]'
                  }`}
                >
                  <div className={`mb-3 ${isSelected ? 'text-indigo-400' : 'text-slate-400'}`}>{mode.icon}</div>
                  <h4 className={`text-sm font-semibold mb-1 ${isSelected ? 'text-white' : 'text-slate-300'}`}>{mode.label}</h4>
                  <p className="text-xs text-slate-500 leading-relaxed">{mode.desc}</p>
                </button>
              );
            })}
          </div>
        </div>

        <div className="h-px bg-white/[0.04]" />

        <div>
          <h4 className="text-sm font-semibold text-white mb-4 flex items-center gap-2">
            <Mic className="w-4 h-4 text-indigo-400" />音频配置
          </h4>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs text-slate-400 mb-1.5">TTS 引擎</label>
              <select value={value.ttsEngine} onChange={(e) => setField('ttsEngine', e.target.value)} className="w-full px-3 py-2 rounded-lg bg-white/[0.04] border border-white/[0.08] text-sm text-white focus:outline-none focus:border-indigo-500/50 appearance-none cursor-pointer">
                <option value="edge-tts">Edge TTS</option>
                <option value="cosyvoice">CosyVoice</option>
                <option value="fishtts">Fish TTS</option>
              </select>
            </div>
            <div>
              <label className="block text-xs text-slate-400 mb-1.5">语音角色</label>
              <select value={value.voiceRole} onChange={(e) => setField('voiceRole', e.target.value)} className="w-full px-3 py-2 rounded-lg bg-white/[0.04] border border-white/[0.08] text-sm text-white focus:outline-none focus:border-indigo-500/50 appearance-none cursor-pointer">
                <option value="female_gentle">女声-温柔</option>
                <option value="female_lively">女声-活泼</option>
                <option value="male_deep">男声-深沉</option>
                <option value="male_magnetic">男声-磁性</option>
              </select>
            </div>
          </div>
          <div className="mt-4">
            <label className="block text-xs text-slate-400 mb-1.5">语速: {value.speed.toFixed(1)}x</label>
            <input type="range" min="0.5" max="2.0" step="0.1" value={value.speed} onChange={(e) => setField('speed', parseFloat(e.target.value))} className="w-full h-1.5 rounded-full appearance-none bg-white/[0.06] accent-indigo-500 cursor-pointer" />
          </div>
        </div>

        <div className="h-px bg-white/[0.04]" />

        <div>
          <h4 className="text-sm font-semibold text-white mb-4 flex items-center gap-2">
            <Video className="w-4 h-4 text-indigo-400" />视频配置
          </h4>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs text-slate-400 mb-1.5">画面比例</label>
              <div className="flex gap-2">
                {['16:9', '9:16', '1:1'].map((ratio) => (
                  <button key={ratio} onClick={() => setField('aspectRatio', ratio)} className={`flex-1 py-2 rounded-lg text-xs font-medium transition-all ${value.aspectRatio === ratio ? 'bg-indigo-500/15 text-indigo-400 border border-indigo-500/30' : 'bg-white/[0.03] text-slate-400 border border-white/[0.06] hover:border-white/[0.12]'}`}>
                    {ratio}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label className="block text-xs text-slate-400 mb-1.5">视频质量</label>
              <div className="flex gap-2">
                {[{ key: 'low', label: '标清' }, { key: 'medium', label: '高清' }, { key: 'high', label: '超清' }].map((q) => (
                  <button key={q.key} onClick={() => setField('videoQuality', q.key)} className={`flex-1 py-2 rounded-lg text-xs font-medium transition-all ${value.videoQuality === q.key ? 'bg-indigo-500/15 text-indigo-400 border border-indigo-500/30' : 'bg-white/[0.03] text-slate-400 border border-white/[0.06] hover:border-white/[0.12]'}`}>
                    {q.label}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>

        <div className="h-px bg-white/[0.04]" />

        <div>
          <h4 className="text-sm font-semibold text-white mb-4 flex items-center gap-2"><span className="text-indigo-400">字幕</span>字幕配置</h4>
          <div className="flex items-center justify-between mb-4">
            <span className="text-xs text-slate-400">启用字幕</span>
            <button onClick={() => setField('subtitleEnabled', !value.subtitleEnabled)} className={`w-10 h-5 rounded-full transition-all duration-200 relative ${value.subtitleEnabled ? 'bg-indigo-500' : 'bg-white/[0.1]'}`}>
              <div className={`w-4 h-4 rounded-full bg-white absolute top-0.5 transition-all duration-200 ${value.subtitleEnabled ? 'left-5.5' : 'left-0.5'}`} />
            </button>
          </div>
          {value.subtitleEnabled && (
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs text-slate-400 mb-1.5">字幕字体</label>
                <select value={value.subtitleFont} onChange={(e) => setField('subtitleFont', e.target.value)} className="w-full px-3 py-2 rounded-lg bg-white/[0.04] border border-white/[0.08] text-sm text-white focus:outline-none focus:border-indigo-500/50 appearance-none cursor-pointer">
                  <option value="default">默认</option>
                  <option value="noto_sans">思源黑体</option>
                  <option value="noto_serif">思源宋体</option>
                </select>
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-1.5">字幕大小: {value.subtitleSize}px</label>
                <input type="range" min="16" max="48" step="2" value={value.subtitleSize} onChange={(e) => setField('subtitleSize', parseInt(e.target.value))} className="w-full h-1.5 rounded-full appearance-none bg-white/[0.06] accent-indigo-500 cursor-pointer" />
              </div>
            </div>
          )}
        </div>

        <div className="flex items-center justify-end gap-3 pt-2 pb-4">
          <Button variant="outline" size="sm" className="border-indigo-500/30 text-indigo-400 hover:bg-indigo-500/10 rounded-xl gap-1.5">
            <Save className="w-4 h-4" />保存配置
          </Button>
          <Button size="sm" onClick={onGenerate} disabled={generating} className="gradient-bg hover:brightness-110 text-white rounded-xl gap-1.5 disabled:opacity-50">
            <Play className="w-4 h-4" />{generating ? '生成中...' : '开始生成文案'}<ChevronRight className="w-4 h-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}
