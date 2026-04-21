import { useState } from 'react';
import { Video, Monitor, Smartphone, Square } from 'lucide-react';

type AspectRatio = '16:9' | '9:16' | '1:1';
type VideoQuality = '480p' | '720p' | '1080p' | '4k';

const aspectRatios: { key: AspectRatio; label: string; icon: React.ReactNode; desc: string }[] = [
  { key: '16:9', label: '横屏 16:9', icon: <Monitor className="w-5 h-5" />, desc: '适合 B站、YouTube' },
  { key: '9:16', label: '竖屏 9:16', icon: <Smartphone className="w-5 h-5" />, desc: '适合 抖音、小红书' },
  { key: '1:1', label: '方形 1:1', icon: <Square className="w-5 h-5" />, desc: '适合 微信视频号' },
];

const qualities: { key: VideoQuality; label: string; desc: string }[] = [
  { key: '480p', label: '480p', desc: '标清 · 体积小' },
  { key: '720p', label: '720p', desc: '高清 · 均衡' },
  { key: '1080p', label: '1080p', desc: '全高清 · 推荐' },
  { key: '4k', label: '4K', desc: '超高清 · 体积大' },
];

export default function VideoPanel() {
  const [aspectRatio, setAspectRatio] = useState<AspectRatio>('16:9');
  const [quality, setQuality] = useState<VideoQuality>('1080p');
  const [videoVolume, setVideoVolume] = useState(100);
  const [fps, setFps] = useState(30);

  return (
    <div className="max-w-3xl space-y-6">
      {/* Aspect Ratio */}
      <section className="glass-card p-5">
        <h3 className="text-sm font-semibold text-slate-300 mb-4 flex items-center gap-2">
          <Video className="w-4 h-4 text-indigo-400" />
          画面比例
        </h3>
        <div className="grid grid-cols-3 gap-3">
          {aspectRatios.map((ar) => (
            <button
              key={ar.key}
              onClick={() => setAspectRatio(ar.key)}
              className={`p-4 rounded-xl border text-center transition-all ${
                aspectRatio === ar.key
                  ? 'border-indigo-500/50 bg-indigo-500/10 text-white'
                  : 'border-white/[0.06] bg-white/[0.02] text-slate-400 hover:bg-white/[0.04]'
              }`}
            >
              <div className={`mx-auto mb-2 flex items-center justify-center ${
                aspectRatio === ar.key ? 'text-indigo-400' : 'text-slate-500'
              }`}>
                {ar.icon}
              </div>
              <span className="font-medium text-sm block">{ar.label}</span>
              <span className="text-[10px] text-slate-500">{ar.desc}</span>
            </button>
          ))}
        </div>
      </section>

      {/* Video Quality */}
      <section className="glass-card p-5">
        <h3 className="text-sm font-semibold text-slate-300 mb-4">视频质量</h3>
        <div className="grid grid-cols-2 gap-3">
          {qualities.map((q) => (
            <button
              key={q.key}
              onClick={() => setQuality(q.key)}
              className={`p-3 rounded-xl border text-left transition-all ${
                quality === q.key
                  ? 'border-indigo-500/50 bg-indigo-500/10 text-white'
                  : 'border-white/[0.06] bg-white/[0.02] text-slate-400 hover:bg-white/[0.04]'
              }`}
            >
              <span className="font-semibold text-sm block">{q.label}</span>
              <span className="text-[10px] text-slate-500">{q.desc}</span>
            </button>
          ))}
        </div>
      </section>

      {/* Video Volume */}
      <section className="glass-card p-5">
        <h3 className="text-sm font-semibold text-slate-300 mb-4">原视频音量</h3>
        <div className="space-y-3">
          <div className="flex items-center justify-between text-xs text-slate-500">
            <span>0%</span>
            <span className="text-indigo-400 font-medium">{videoVolume}%</span>
            <span>100%</span>
          </div>
          <input
            type="range"
            min="0"
            max="100"
            value={videoVolume}
            onChange={(e) => setVideoVolume(parseInt(e.target.value))}
            className="w-full"
          />
        </div>
      </section>

      {/* Frame Rate */}
      <section className="glass-card p-5">
        <h3 className="text-sm font-semibold text-slate-300 mb-4">帧率</h3>
        <div className="flex items-center gap-3">
          <div className="flex gap-2">
            {[24, 30, 60].map((f) => (
              <button
                key={f}
                onClick={() => setFps(f)}
                className={`px-4 py-2 rounded-lg text-sm border transition-all ${
                  fps === f
                    ? 'border-indigo-500/50 bg-indigo-500/10 text-white'
                    : 'border-white/[0.06] text-slate-400 hover:bg-white/[0.04]'
                }`}
              >
                {f} FPS
              </button>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}