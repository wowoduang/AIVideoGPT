import { useRef, useState } from 'react';
import { CloudUpload, Upload, FileVideo, Trash2, Check } from 'lucide-react';

interface VideoUploadStepProps {
  uploadedFile: File | null;
  onFileSelect: (file: File | null) => void;
}

export default function VideoUploadStep({ uploadedFile, onFileSelect }: VideoUploadStepProps) {
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    if (file && file.type.startsWith('video/')) {
      onFileSelect(file);
    }
  };

  const handleSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) onFileSelect(file);
  };

  return (
    <div className="h-full flex flex-col px-6 py-4">
      {/* Info */}
      <div className="mb-4">
        <p className="text-xs text-slate-500">
          上传视频后将自动提取音频并识别字幕，为后续配置提供基础数据
        </p>
      </div>

      {!uploadedFile ? (
        /* Upload Zone */
        <div
          onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          className={`flex-1 border-2 border-dashed rounded-2xl flex flex-col items-center justify-center cursor-pointer transition-all duration-300 ${
            isDragging
              ? 'border-indigo-500 bg-indigo-500/5'
              : 'border-white/[0.1] bg-white/[0.01] hover:border-indigo-500/30 hover:bg-white/[0.02]'
          }`}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept="video/*"
            onChange={handleSelect}
            className="hidden"
          />
          {/* Cloud Icon */}
          <div className="w-20 h-20 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center mb-5">
            <CloudUpload className="w-10 h-10 text-indigo-400" />
          </div>
          <p className="text-base font-medium text-slate-200 mb-2">拖拽或选择文件上传</p>
          <p className="text-sm text-slate-500 mb-6">支持批量上传，自动识别视频内容</p>
          <div className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 text-sm font-medium hover:bg-indigo-500/15 transition-colors">
            <Upload className="w-4 h-4" />
            选择文件
          </div>
          {/* Format info */}
          <div className="mt-8 flex items-center justify-center gap-3 text-xs text-slate-600">
            <span>MP4</span>
            <span className="w-1 h-1 rounded-full bg-slate-700" />
            <span>MOV</span>
            <span className="w-1 h-1 rounded-full bg-slate-700" />
            <span>AVI</span>
            <span className="w-1 h-1 rounded-full bg-slate-700" />
            <span>WEBM</span>
            <span className="w-1 h-1 rounded-full bg-slate-700" />
            <span>最大 1GB</span>
            <span className="w-1 h-1 rounded-full bg-slate-700" />
            <span>建议时长 &lt; 40分钟</span>
          </div>
        </div>
      ) : (
        /* Uploaded File Display */
        <div className="flex-1 flex flex-col">
          <div className="p-5 rounded-xl bg-white/[0.02] border border-white/[0.06]">
            <div className="flex items-start gap-4">
              <div className="w-14 h-14 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center shrink-0">
                <FileVideo className="w-7 h-7 text-indigo-400" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-white truncate mb-1">{uploadedFile.name}</p>
                <p className="text-xs text-slate-500 mb-3">
                  {(uploadedFile.size / (1024 * 1024)).toFixed(1)} MB · {uploadedFile.type || 'video/mp4'}
                </p>
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <Check className="w-3.5 h-3.5 text-emerald-400" />
                    <span className="text-xs text-emerald-400">视频上传完成</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Check className="w-3.5 h-3.5 text-emerald-400" />
                    <span className="text-xs text-emerald-400">音频提取完成</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Check className="w-3.5 h-3.5 text-emerald-400" />
                    <span className="text-xs text-emerald-400">字幕识别完成</span>
                  </div>
                </div>
              </div>
              <button
                onClick={() => onFileSelect(null)}
                className="p-2 rounded-lg text-slate-400 hover:text-red-400 hover:bg-red-500/10 transition-all"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Add more */}
          <button
            onClick={() => fileInputRef.current?.click()}
            className="w-full mt-3 py-3 rounded-xl border border-dashed border-white/[0.08] text-sm text-slate-500 hover:text-slate-300 hover:border-white/[0.15] transition-all flex items-center justify-center gap-2"
          >
            <Upload className="w-4 h-4" />
            继续添加视频素材
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept="video/*"
            onChange={handleSelect}
            className="hidden"
          />
        </div>
      )}
    </div>
  );
}