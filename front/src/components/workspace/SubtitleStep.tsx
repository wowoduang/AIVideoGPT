import { useRef, useState } from 'react';
import { Upload, FileText, Edit3, Play, Film, Clock, FileVideo, Video, CheckCircle2, Maximize2, RefreshCw, X, Download, Settings } from 'lucide-react';
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
  videoFile?: File | null;
  videoUrl?: string;
  onReupload?: () => void;
}

function parseSRT(srt: string): SubtitleLine[] {
  // 先清理行尾空格，然后用一个或多个空白行（可能包含空格）分割
  const cleaned = srt.replace(/[ \t]+\n/g, '\n');
  const blocks = cleaned.trim().split(/\r?\n\s*\r?\n+/);

  return blocks
    .map((block, index) => {
      const lines = block.split(/\r?\n/).filter((line) => line.trim().length > 0);
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

// 格式化时间显示
function formatTimeDisplay(timeStr: string): string {
  // 处理 00:00:01.000 格式
  const match = timeStr.match(/(\d+):(\d+):(\d+)[.,]?(\d*)/);
  if (!match) return timeStr;
  const [, h, m, s, ms] = match;
  const totalSeconds = parseInt(h) * 3600 + parseInt(m) * 60 + parseInt(s);
  return `${totalSeconds}.${ms?.padEnd(3, '0').slice(0, 1) || '0'}s`;
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
  videoFile,
  videoUrl,
  onReupload,
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

  const handleExport = () => {
    // 导出字幕为SRT文件
    let srtContent = '';
    subtitles.forEach((sub, index) => {
      const start = sub.start.replace('.', ',');
      const end = sub.end.replace('.', ',');
      srtContent += `${index + 1}\n${start} --> ${end}\n${sub.text}\n\n`;
    });
    const blob = new Blob([srtContent], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `subtitles_${Date.now()}.srt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // 格式化文件大小
  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  // 初始状态 - 选择识别方式
  if (!subtitleMode && !recognitionDone) {
    return (
      <div className="h-full flex items-center justify-center px-6">
        <div className="w-full max-w-2xl">
          <div className="text-center mb-8">
            <h2 className="text-2xl font-semibold text-white mb-2">字幕识别</h2>
            <p className="text-sm text-slate-400">选择字幕获取方式，支持自动识别或上传已有字幕文件</p>
          </div>
          
          <div className="grid grid-cols-2 gap-4">
            {/* 自动识别 */}
            <button
              onClick={onStartRecognition}
              disabled={isRecognizing}
              className="group p-6 rounded-2xl bg-[#1a1a1a] border border-white/[0.06] hover:border-[#4ADE80]/30 transition-all text-left"
            >
              <div className="w-12 h-12 rounded-xl bg-[#4ADE80]/10 border border-[#4ADE80]/20 flex items-center justify-center mb-4 group-hover:bg-[#4ADE80]/20 transition-colors">
                {isRecognizing ? (
                  <div className="w-5 h-5 border-2 border-[#4ADE80]/30 border-t-[#4ADE80] rounded-full animate-spin" />
                ) : (
                  <Play className="w-5 h-5 text-[#4ADE80]" />
                )}
              </div>
              <h3 className="text-base font-medium text-white mb-1">自动识别</h3>
              <p className="text-xs text-slate-500">使用AI语音识别自动生成字幕</p>
            </button>

            {/* 上传字幕 */}
            <button
              onClick={() => srtInputRef.current?.click()}
              className="group p-6 rounded-2xl bg-[#1a1a1a] border border-white/[0.06] hover:border-[#4ADE80]/30 transition-all text-left"
            >
              <div className="w-12 h-12 rounded-xl bg-[#4ADE80]/10 border border-[#4ADE80]/20 flex items-center justify-center mb-4 group-hover:bg-[#4ADE80]/20 transition-colors">
                <Upload className="w-5 h-5 text-[#4ADE80]" />
              </div>
              <h3 className="text-base font-medium text-white mb-1">上传字幕</h3>
              <p className="text-xs text-slate-500">支持 SRT、VTT 格式字幕文件</p>
            </button>
            <input ref={srtInputRef} type="file" accept=".srt,.vtt,.txt" className="hidden" onChange={handleSrtUpload} />
          </div>
        </div>
      </div>
    );
  }

  // 识别中状态
  if (isRecognizing) {
    return (
      <div className="h-full flex items-center justify-center px-6">
        <div className="text-center">
          <div className="w-16 h-16 rounded-2xl bg-[#4ADE80]/10 border border-[#4ADE80]/20 flex items-center justify-center mx-auto mb-4">
            <div className="w-6 h-6 border-2 border-[#4ADE80]/30 border-t-[#4ADE80] rounded-full animate-spin" />
          </div>
          <h3 className="text-lg font-medium text-white mb-2">正在识别字幕...</h3>
          <p className="text-sm text-slate-500">请稍候，AI正在分析视频音频内容</p>
        </div>
      </div>
    );
  }

  // 字幕编辑状态
  return (
    <div className="h-full flex flex-col">
      {/* 顶部栏 */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-white/[0.06]">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-[#4ADE80]/10 border border-[#4ADE80]/20 flex items-center justify-center">
            <CheckCircle2 className="w-4 h-4 text-[#4ADE80]" />
          </div>
          <div>
            <h3 className="text-base font-medium text-white">字幕预览与编辑</h3>
            <p className="text-xs text-slate-500">共 {subtitles.length} 条字幕，可直接编辑</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button 
            variant="outline" 
            size="sm"
            onClick={() => srtInputRef.current?.click()}
            className="border-white/[0.08] text-slate-400 hover:text-white hover:bg-white/[0.04]"
          >
            <X className="w-4 h-4 mr-1.5" />取消
          </Button>
          <Button 
            size="sm"
            onClick={() => onSubtitlesChange([...subtitles])}
            className="bg-[#4ADE80] hover:bg-[#4ADE80]/90 text-black"
          >
            <CheckCircle2 className="w-4 h-4 mr-1.5" />保存
          </Button>
          <Button 
            variant="outline" 
            size="sm"
            onClick={handleExport}
            className="border-white/[0.08] text-slate-400 hover:text-white hover:bg-white/[0.04]"
          >
            <Download className="w-4 h-4 mr-1.5" />导出
          </Button>
          <Button 
            variant="outline" 
            size="sm"
            className="border-white/[0.08] text-slate-400 hover:text-white hover:bg-white/[0.04]"
          >
            <Settings className="w-4 h-4" />
          </Button>
          <input ref={srtInputRef} type="file" accept=".srt,.vtt,.txt" className="hidden" onChange={handleSrtUpload} />
        </div>
      </div>

      {/* 主内容区 */}
      <div className="flex-1 flex overflow-hidden">
        {/* 左侧：视频预览 - 50%宽度 */}
        <div className="w-1/2 border-r border-white/[0.06] flex flex-col">
          {/* 视频播放器 */}
          <div className="flex-1 bg-black flex items-center justify-center p-4">
            {videoUrl ? (
              <div className="relative w-full">
                <video
                  src={videoUrl}
                  controls
                  className="w-full rounded-lg"
                />
                <button className="absolute top-2 right-2 w-8 h-8 rounded-lg bg-black/50 flex items-center justify-center text-white/70 hover:text-white">
                  <Maximize2 className="w-4 h-4" />
                </button>
              </div>
            ) : (
              <div className="text-center">
                <div className="w-16 h-16 rounded-2xl bg-white/[0.03] border border-white/[0.06] flex items-center justify-center mx-auto mb-4">
                  <Video className="w-8 h-8 text-slate-600" />
                </div>
                <p className="text-sm text-slate-500 mb-1">视频预览</p>
                <p className="text-xs text-slate-600">视频文件仅在本地处理，不上传云端</p>
              </div>
            )}
          </div>
          
          {/* 视频信息 */}
          <div className="p-4 border-t border-white/[0.06]">
            {videoFile && (
              <div className="flex items-center gap-3 text-xs text-slate-500">
                <FileVideo className="w-4 h-4 text-[#4ADE80]" />
                <span className="text-slate-300">{videoFile.name}</span>
                <span className="text-slate-600">·</span>
                <span>{formatFileSize(videoFile.size)}</span>
              </div>
            )}
            <Button 
              variant="outline" 
              size="sm"
              onClick={onReupload}
              className="w-full mt-3 border-[#4ADE80]/30 text-[#4ADE80] hover:bg-[#4ADE80]/10"
            >
              <RefreshCw className="w-4 h-4 mr-1.5" />重新选择视频
            </Button>
          </div>
        </div>

        {/* 右侧：字幕列表 - 50%宽度 */}
        <div className="w-1/2 flex flex-col bg-[#0f0f0f]">
          <div className="flex-1 overflow-y-auto p-4 space-y-2">
            {subtitles.length === 0 ? (
              <div className="h-full flex items-center justify-center">
                <div className="text-center">
                  <div className="w-14 h-14 rounded-2xl bg-white/[0.03] border border-white/[0.06] flex items-center justify-center mx-auto mb-3">
                    <FileText className="w-7 h-7 text-slate-600" />
                  </div>
                  <p className="text-sm text-slate-500">暂无字幕数据</p>
                </div>
              </div>
            ) : (
              subtitles.map((sub) => (
                <div 
                  key={sub.id} 
                  className="group flex items-start gap-4 p-4 rounded-xl bg-[#1a1a1a] border border-white/[0.04] hover:border-white/[0.08] transition-all"
                >
                  {/* 时间范围 */}
                  <div className="w-24 shrink-0 text-xs font-mono text-slate-500 pt-1">
                    {formatTimeDisplay(sub.start)} - {formatTimeDisplay(sub.end)}
                  </div>
                  
                  {/* 字幕内容 */}
                  <div className="flex-1 min-w-0">
                    {editingId === sub.id ? (
                      <div className="flex items-start gap-2">
                        <textarea 
                          value={editText} 
                          onChange={(e) => setEditText(e.target.value)} 
                          className="flex-1 min-h-[60px] rounded-lg bg-white/[0.06] border border-[#4ADE80]/30 p-3 text-sm text-white outline-none focus:border-[#4ADE80]/50 resize-none"
                          autoFocus
                        />
                        <Button 
                          size="sm" 
                          onClick={() => handleEditSave(sub.id)} 
                          className="bg-[#4ADE80] hover:bg-[#4ADE80]/90 text-black shrink-0"
                        >
                          保存
                        </Button>
                      </div>
                    ) : (
                      <div className="flex items-start justify-between gap-2">
                        <p className="text-sm text-slate-300 leading-relaxed flex-1">
                          {sub.text}
                        </p>
                        <button
                          onClick={() => handleEditStart(sub)}
                          className="opacity-0 group-hover:opacity-100 p-1.5 rounded-lg text-slate-500 hover:text-white hover:bg-white/[0.08] transition-all shrink-0"
                        >
                          <Edit3 className="w-4 h-4" />
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
      
    </div>
  );
}
