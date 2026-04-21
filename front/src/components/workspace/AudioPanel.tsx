import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Mic, Volume2, Music, ChevronDown } from 'lucide-react';

type TTSEngine = 'edge' | 'cosyvoice' | 'fish' | 'clone';

const ttsEngines: { key: TTSEngine; label: string; desc: string }[] = [
  { key: 'edge', label: 'Edge TTS', desc: '免费，多语言支持' },
  { key: 'cosyvoice', label: 'CosyVoice', desc: '高质量中文语音' },
  { key: 'fish', label: 'Fish TTS', desc: '自然流畅语音' },
  { key: 'clone', label: '语音克隆', desc: '零样本声音克隆' },
];

const voiceOptions: Record<TTSEngine, string[]> = {
  edge: ['zh-CN-XiaoxiaoNeural', 'zh-CN-YunxiNeural', 'zh-CN-XiaoyiNeural', 'en-US-JennyNeural'],
  cosyvoice: ['中文女声-知性', '中文男声-磁性', '中文女声-甜美'],
  fish: ['默认女声', '默认男声', '温柔女声'],
  clone: ['自定义声音'],
};

const bgmOptions = [
  '无背景音乐',
  '轻柔钢琴',
  '史诗管弦',
  '科技电子',
  '温馨吉他',
  '悬疑氛围',
];

export default function AudioPanel() {
  const [ttsEngine, setTtsEngine] = useState<TTSEngine>('edge');
  const [voice, setVoice] = useState(voiceOptions.edge[0]);
  const [bgm, setBgm] = useState(bgmOptions[0]);
  const [narrationVolume, setNarrationVolume] = useState(80);
  const [bgmVolume, setBgmVolume] = useState(30);
  const [speed, setSpeed] = useState(1.0);

  const handleTtsChange = (engine: TTSEngine) => {
    setTtsEngine(engine);
    setVoice(voiceOptions[engine][0]);
  };

  return (
    <div className="max-w-3xl space-y-6">
      {/* TTS Engine */}
      <section className="glass-card p-5">
        <h3 className="text-sm font-semibold text-slate-300 mb-4 flex items-center gap-2">
          <Mic className="w-4 h-4 text-indigo-400" />
          TTS 引擎
        </h3>
        <div className="grid grid-cols-2 gap-3">
          {ttsEngines.map((engine) => (
            <button
              key={engine.key}
              onClick={() => handleTtsChange(engine.key)}
              className={`p-4 rounded-xl border text-left transition-all ${
                ttsEngine === engine.key
                  ? 'border-indigo-500/50 bg-indigo-500/10 text-white'
                  : 'border-white/[0.06] bg-white/[0.02] text-slate-400 hover:bg-white/[0.04]'
              }`}
            >
              <span className="font-medium text-sm block">{engine.label}</span>
              <span className="text-xs text-slate-500">{engine.desc}</span>
            </button>
          ))}
        </div>
      </section>

      {/* Voice Selection */}
      <section className="glass-card p-5">
        <h3 className="text-sm font-semibold text-slate-300 mb-4">语音选择</h3>
        <div className="relative">
          <select
            value={voice}
            onChange={(e) => setVoice(e.target.value)}
            className="w-full appearance-none bg-white/[0.03] border border-white/[0.06] rounded-xl px-4 py-3 text-sm text-slate-300 outline-none focus:border-indigo-500/40 transition-colors cursor-pointer"
          >
            {voiceOptions[ttsEngine].map((v) => (
              <option key={v} value={v} className="bg-[#12121A] text-white">
                {v}
              </option>
            ))}
          </select>
          <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500 pointer-events-none" />
        </div>
        {ttsEngine === 'clone' && (
          <div className="mt-3 border-2 border-dashed border-white/[0.08] rounded-xl p-6 text-center hover:border-indigo-500/30 transition-colors cursor-pointer">
            <Mic className="w-6 h-6 text-slate-500 mx-auto mb-2" />
            <p className="text-xs text-slate-500">上传音频样本进行声音克隆</p>
          </div>
        )}
        <div className="mt-4">
          <Button variant="outline" size="sm" className="border-white/10 text-slate-400 hover:text-white hover:bg-white/5 rounded-lg">
            试听语音
          </Button>
        </div>
      </section>

      {/* Speed Control */}
      <section className="glass-card p-5">
        <h3 className="text-sm font-semibold text-slate-300 mb-4">语速控制</h3>
        <div className="space-y-3">
          <div className="flex items-center justify-between text-xs text-slate-500">
            <span>0.5x</span>
            <span className="text-indigo-400 font-medium">{speed.toFixed(1)}x</span>
            <span>2.0x</span>
          </div>
          <input
            type="range"
            min="0.5"
            max="2.0"
            step="0.1"
            value={speed}
            onChange={(e) => setSpeed(parseFloat(e.target.value))}
            className="w-full"
          />
        </div>
      </section>

      {/* BGM Selection */}
      <section className="glass-card p-5">
        <h3 className="text-sm font-semibold text-slate-300 mb-4 flex items-center gap-2">
          <Music className="w-4 h-4 text-indigo-400" />
          背景音乐
        </h3>
        <div className="relative">
          <select
            value={bgm}
            onChange={(e) => setBgm(e.target.value)}
            className="w-full appearance-none bg-white/[0.03] border border-white/[0.06] rounded-xl px-4 py-3 text-sm text-slate-300 outline-none focus:border-indigo-500/40 transition-colors cursor-pointer"
          >
            {bgmOptions.map((b) => (
              <option key={b} value={b} className="bg-[#12121A] text-white">
                {b}
              </option>
            ))}
          </select>
          <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500 pointer-events-none" />
        </div>
      </section>

      {/* Volume Controls */}
      <section className="glass-card p-5">
        <h3 className="text-sm font-semibold text-slate-300 mb-4 flex items-center gap-2">
          <Volume2 className="w-4 h-4 text-indigo-400" />
          音量控制
        </h3>
        <div className="space-y-5">
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-xs text-slate-500">解说音量</label>
              <span className="text-xs text-indigo-400 font-medium">{narrationVolume}%</span>
            </div>
            <input
              type="range"
              min="0"
              max="100"
              value={narrationVolume}
              onChange={(e) => setNarrationVolume(parseInt(e.target.value))}
              className="w-full"
            />
          </div>
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-xs text-slate-500">背景音乐音量</label>
              <span className="text-xs text-indigo-400 font-medium">{bgmVolume}%</span>
            </div>
            <input
              type="range"
              min="0"
              max="100"
              value={bgmVolume}
              onChange={(e) => setBgmVolume(parseInt(e.target.value))}
              className="w-full"
            />
          </div>
        </div>
      </section>
    </div>
  );
}