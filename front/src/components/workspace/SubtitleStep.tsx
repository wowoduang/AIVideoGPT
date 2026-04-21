import { useRef, useState } from 'react';
import { Sparkles, Upload, FileText, Edit3, Play } from 'lucide-react';
import { Button } from '@/components/ui/button';
import type { SubtitleLine } from '@/lib/api';

interface SubtitleStepProps {
  subtitleMode: 'auto' | 'upload' | null;
  onModeSelect: (mode: 'auto' | 'upload') => void;
  isRecognizing: boolean;
  recognitionDone: boolean;
  onStartRecognition: () => void;
  subtitles: SubtitleLine[];
  onSubtitlesChange: (subs: SubtitleLine[]) => void;
  onSubtitleFileSelect?: (file: File, parsed: SubtitleLine[]) => void;
}

function parseSRT(srt: string): SubtitleLine[] {
  const blocks = srt.trim().split(/\r?\n\r?\n+/);

  return blocks
    .map((block, index) => {
      const lines = block.split(/\r?\n/).filter(Boolean);
      const timeLine = lines.find((line) => line.includes('-->')) || '';
      const textLines = lines.filter((line) => !/^\d+$/.test(line.trim()) && !line.includes('-->'));
      const timeMatch = timeLine.match(/(\d+:\d+:\d+[,.]\d+)\s*-->\s*(\d+:\d+:\d+[,.]\d+)/);

      return {
        id: index + 1,
        start: timeMatch ? timeMatch[1].replace(',', '.') : `${index * 5}.0s`,
        end: timeMatch ? timeMatch[2].replace(',', '.') : `${index * 5 + 5}.0s`,
        text: textLines.join(' ').trim() || `字幕 ${index + 1}`,
      };
    })
    .filter((item) => item.text.length > 0);
}

export default function SubtitleStep({
  subtitleMode,
  onModeSelect,
  isRecognizing,
  recognitionDone,
  onStartRecognition,
  subtitles,
  onSubtitlesChange,
  onSubtitleFileSelect,
}: SubtitleStepProps) {
  const srtInputRef = useRef<HTMLInputElement>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editText, setEditText] = useState('');

  const handleSrtUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (ev) => {
      const content = String(ev.target?.result || '');
      const parsed = parseSRT(content);
      onSubtitlesChange(parsed);
      onModeSelect('upload');
      onSubtitleFileSelect?.(file, parsed);
    };
    reader.readAsText(file);
  };

  const handleEditStart = (sub: SubtitleLine) => {
    setEditingId(sub.id);
    setEditText(sub.text);
  };

  const handleEditSave = (id: number) => {
    onSubtitlesChange(subtitles.map((s) => (s.id === id ? { ...s, text: editText } : s)));
    setEditingId(null);
  };

  if (!subtitleMode && !recognitionDone) {
    return (
      <div className="h-full flex items-center justify-center px-6">
        <div className="w-full max-w-lg">
          <div className="p-8 rounded-2xl bg-white/[0.02] border border-white/[0.06] text-center">
            <div className="w-16 h-16 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center mx-auto mb-5">
              <Sparkles className="w-8 h-8 text-indigo-400" />
            </div>
            <h3 className="text-xl font-semibold text-white mb-2">准备开始字幕识别</h3>
            <p className="text-sm text-slate-400 mb-6 leading-relaxed">自动识别将调用后端 Qwen 语音识别流程；也可以直接上传现成 SRT。</p>
            <div className="flex items-center justify-center gap-3 mb-5">
              <Button onClick={onStartRecognition} disabled={isRecognizing} className="gradient-bg hover:brightness-110 text-white rounded-xl px-6 gap-2" size="lg">
                {isRecognizing ? (
                  <>
                    <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    识别中...
                  </>
                ) : (
                  <>
                    <Play className="w-4 h-4" />
                    开始识别
                  </>
                )}
              </Button>
              <Button variant="outline" onClick={() => srtInputRef.current?.click()} className="border-indigo-500/30 text-indigo-400 hover:bg-indigo-500/10 rounded-xl px-6 gap-2" size="lg">
                <Upload className="w-4 h-4" />上传 SRT
              </Button>
              <input ref={srtInputRef} type="file" accept=".srt,.vtt,.txt" className="hidden" onChange={handleSrtUpload} />
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col px-6 py-4 gap-4 overflow-hidden">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-base font-semibold text-white">字幕结果</h3>
          <p className="text-xs text-slate-500 mt-1">共 {subtitles.length} 条，可直接编辑后进入下一步</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => srtInputRef.current?.click()} className="border-white/[0.08] text-slate-300 hover:bg-white/[0.04]">
            <Upload className="w-4 h-4 mr-1" />替换字幕
          </Button>
          <input ref={srtInputRef} type="file" accept=".srt,.vtt,.txt" className="hidden" onChange={handleSrtUpload} />
        </div>
      </div>

      <div className="flex-1 overflow-y-auto rounded-2xl border border-white/[0.06] bg-white/[0.02] p-4 space-y-3">
        {subtitles.length === 0 && <div className="text-sm text-slate-500">暂无字幕</div>}
        {subtitles.map((sub) => (
          <div key={sub.id} className="rounded-xl border border-white/[0.06] bg-black/20 p-3">
            <div className="flex items-center justify-between gap-3 mb-2">
              <div className="flex items-center gap-2 text-xs text-slate-500">
                <FileText className="w-3.5 h-3.5" />
                <span>{sub.start}</span>
                <span>→</span>
                <span>{sub.end}</span>
              </div>
              {editingId === sub.id ? (
                <Button size="sm" onClick={() => handleEditSave(sub.id)} className="gradient-bg text-white rounded-lg h-8">保存</Button>
              ) : (
                <Button variant="ghost" size="sm" onClick={() => handleEditStart(sub)} className="text-slate-400 hover:text-white h-8">
                  <Edit3 className="w-4 h-4" />
                </Button>
              )}
            </div>
            {editingId === sub.id ? (
              <textarea value={editText} onChange={(e) => setEditText(e.target.value)} className="w-full min-h-20 rounded-lg bg-white/[0.04] border border-white/[0.08] p-3 text-sm text-white outline-none focus:border-indigo-500/40" />
            ) : (
              <p className="text-sm text-slate-200 leading-6">{sub.text}</p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
