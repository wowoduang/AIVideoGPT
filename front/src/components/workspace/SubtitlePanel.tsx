import { useState } from 'react';
import { Subtitles, Type, AlignCenter, AlignLeft, AlignRight } from 'lucide-react';

type SubtitlePosition = 'bottom' | 'center' | 'top';
type SubtitleFont = 'NotoSansSC' | 'SimHei' | 'KaiTi' | 'FangSong';

const fonts: { key: SubtitleFont; label: string }[] = [
  { key: 'NotoSansSC', label: '思源黑体' },
  { key: 'SimHei', label: '黑体' },
  { key: 'KaiTi', label: '楷体' },
  { key: 'FangSong', label: '仿宋' },
];

const positions: { key: SubtitlePosition; label: string; icon: React.ReactNode }[] = [
  { key: 'top', label: '顶部', icon: <AlignLeft className="w-4 h-4 rotate-90" /> },
  { key: 'center', label: '居中', icon: <AlignCenter className="w-4 h-4" /> },
  { key: 'bottom', label: '底部', icon: <AlignRight className="w-4 h-4 rotate-90" /> },
];

export default function SubtitlePanel() {
  const [enabled, setEnabled] = useState(true);
  const [font, setFont] = useState<SubtitleFont>('NotoSansSC');
  const [fontSize, setFontSize] = useState(24);
  const [position, setPosition] = useState<SubtitlePosition>('bottom');
  const [primaryColor, setPrimaryColor] = useState('#FFFFFF');
  const [outlineColor, setOutlineColor] = useState('#000000');
  const [outlineWidth, setOutlineWidth] = useState(2);
  const [bold, setBold] = useState(false);

  return (
    <div className="max-w-3xl space-y-6">
      {/* Enable Toggle */}
      <section className="glass-card p-5">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-slate-300 flex items-center gap-2">
            <Subtitles className="w-4 h-4 text-indigo-400" />
            字幕开关
          </h3>
          <button
            onClick={() => setEnabled(!enabled)}
            className={`relative w-11 h-6 rounded-full transition-colors ${
              enabled ? 'bg-indigo-500' : 'bg-slate-700'
            }`}
          >
            <div
              className={`absolute top-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform ${
                enabled ? 'translate-x-5.5 left-0.5' : 'left-0.5'
              }`}
              style={{ transform: enabled ? 'translateX(22px)' : 'translateX(0)' }}
            />
          </button>
        </div>
      </section>

      {enabled && (
        <>
          {/* Font Selection */}
          <section className="glass-card p-5">
            <h3 className="text-sm font-semibold text-slate-300 mb-4 flex items-center gap-2">
              <Type className="w-4 h-4 text-indigo-400" />
              字体选择
            </h3>
            <div className="grid grid-cols-2 gap-3">
              {fonts.map((f) => (
                <button
                  key={f.key}
                  onClick={() => setFont(f.key)}
                  className={`p-3 rounded-xl border text-center transition-all ${
                    font === f.key
                      ? 'border-indigo-500/50 bg-indigo-500/10 text-white'
                      : 'border-white/[0.06] bg-white/[0.02] text-slate-400 hover:bg-white/[0.04]'
                  }`}
                >
                  <span className="font-medium text-sm">{f.label}</span>
                </button>
              ))}
            </div>
          </section>

          {/* Font Size */}
          <section className="glass-card p-5">
            <h3 className="text-sm font-semibold text-slate-300 mb-4">字号大小</h3>
            <div className="space-y-3">
              <div className="flex items-center justify-between text-xs text-slate-500">
                <span>12px</span>
                <span className="text-indigo-400 font-medium">{fontSize}px</span>
                <span>48px</span>
              </div>
              <input
                type="range"
                min="12"
                max="48"
                value={fontSize}
                onChange={(e) => setFontSize(parseInt(e.target.value))}
                className="w-full"
              />
            </div>
            <div className="mt-3 flex items-center gap-2">
              <button
                onClick={() => setBold(!bold)}
                className={`px-3 py-1.5 rounded-lg text-sm border transition-all ${
                  bold
                    ? 'border-indigo-500/50 bg-indigo-500/10 text-white'
                    : 'border-white/[0.06] text-slate-400 hover:bg-white/[0.04]'
                }`}
              >
                <strong>B</strong> 粗体
              </button>
            </div>
          </section>

          {/* Position */}
          <section className="glass-card p-5">
            <h3 className="text-sm font-semibold text-slate-300 mb-4">字幕位置</h3>
            <div className="grid grid-cols-3 gap-3">
              {positions.map((p) => (
                <button
                  key={p.key}
                  onClick={() => setPosition(p.key)}
                  className={`p-3 rounded-xl border text-center transition-all flex flex-col items-center gap-1 ${
                    position === p.key
                      ? 'border-indigo-500/50 bg-indigo-500/10 text-white'
                      : 'border-white/[0.06] bg-white/[0.02] text-slate-400 hover:bg-white/[0.04]'
                  }`}
                >
                  {p.icon}
                  <span className="text-xs">{p.label}</span>
                </button>
              ))}
            </div>
          </section>

          {/* Colors */}
          <section className="glass-card p-5">
            <h3 className="text-sm font-semibold text-slate-300 mb-4">字幕样式</h3>
            <div className="space-y-4">
              <div className="flex items-center gap-4">
                <label className="text-xs text-slate-500 w-16 shrink-0">填充色</label>
                <div className="flex items-center gap-2 flex-1">
                  <input
                    type="color"
                    value={primaryColor}
                    onChange={(e) => setPrimaryColor(e.target.value)}
                    className="w-8 h-8 rounded-lg border border-white/10 cursor-pointer bg-transparent"
                  />
                  <input
                    type="text"
                    value={primaryColor}
                    onChange={(e) => setPrimaryColor(e.target.value)}
                    className="flex-1 text-sm text-slate-300 bg-white/[0.03] border border-white/[0.06] rounded-lg px-3 py-2 outline-none focus:border-indigo-500/40 font-mono"
                  />
                </div>
              </div>
              <div className="flex items-center gap-4">
                <label className="text-xs text-slate-500 w-16 shrink-0">描边色</label>
                <div className="flex items-center gap-2 flex-1">
                  <input
                    type="color"
                    value={outlineColor}
                    onChange={(e) => setOutlineColor(e.target.value)}
                    className="w-8 h-8 rounded-lg border border-white/10 cursor-pointer bg-transparent"
                  />
                  <input
                    type="text"
                    value={outlineColor}
                    onChange={(e) => setOutlineColor(e.target.value)}
                    className="flex-1 text-sm text-slate-300 bg-white/[0.03] border border-white/[0.06] rounded-lg px-3 py-2 outline-none focus:border-indigo-500/40 font-mono"
                  />
                </div>
              </div>
              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="text-xs text-slate-500">描边宽度</label>
                  <span className="text-xs text-indigo-400 font-medium">{outlineWidth}px</span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="5"
                  value={outlineWidth}
                  onChange={(e) => setOutlineWidth(parseInt(e.target.value))}
                  className="w-full"
                />
              </div>
            </div>
          </section>

          {/* Preview */}
          <section className="glass-card p-5">
            <h3 className="text-sm font-semibold text-slate-300 mb-4">字幕预览</h3>
            <div className="relative w-full aspect-video rounded-xl bg-[#12121A] border border-white/[0.06] overflow-hidden flex items-end justify-center pb-6">
              <div className="absolute inset-0 bg-gradient-to-t from-black/40 to-transparent" />
              <span
                className="relative z-10"
                style={{
                  fontFamily: font === 'NotoSansSC' ? 'Inter, sans-serif' : font,
                  fontSize: `${fontSize}px`,
                  color: primaryColor,
                  fontWeight: bold ? 'bold' : 'normal',
                  WebkitTextStroke: outlineWidth > 0 ? `${outlineWidth}px ${outlineColor}` : 'none',
                  textShadow: outlineWidth > 0 ? `0 0 ${outlineWidth * 2}px ${outlineColor}40` : 'none',
                }}
              >
                字幕预览文字
              </span>
            </div>
          </section>
        </>
      )}
    </div>
  );
}