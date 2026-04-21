import { useRef, useState, useEffect, useCallback } from 'react';
import { CloudUpload, ArrowLeft, RefreshCw, ArrowRight, AlertTriangle, X } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface VideoUploadStepProps {
  uploadedFile: File | null;
  onFileSelect: (file: File | null) => void;
  onNext?: () => void;
  onBack?: () => void;
  videoUrl?: string;
}

export default function VideoUploadStep({ uploadedFile, onFileSelect, onNext, onBack, videoUrl }: VideoUploadStepProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [showReuploadConfirm, setShowReuploadConfirm] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [isUploading, setIsUploading] = useState(false);
  const [videoDuration, setVideoDuration] = useState(207.3);
  const [trimStart, setTrimStart] = useState(0);
  const [trimEnd, setTrimEnd] = useState(207.3);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  // 清理定时器
  const clearUploadInterval = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  // 组件卸载时清理
  useEffect(() => {
    return () => clearUploadInterval();
  }, [clearUploadInterval]);

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const handleTrimStartChange = (value: number) => {
    const newValue = Math.max(0, Math.min(value, trimEnd - 1));
    setTrimStart(newValue);
  };

  const handleTrimEndChange = (value: number) => {
    const newValue = Math.max(trimStart + 1, Math.min(value, videoDuration));
    setTrimEnd(newValue);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    if (file && file.type.startsWith('video/')) {
      simulateUpload(file);
    }
  };

  const handleSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      simulateUpload(file);
    }
  };

  const simulateUpload = useCallback((file: File) => {
    // 清理之前的定时器
    clearUploadInterval();
    
    setIsUploading(true);
    setUploadProgress(0);
    
    intervalRef.current = setInterval(() => {
      setUploadProgress((prev) => {
        const increment = Math.random() * 15;
        const newProgress = prev + increment;
        
        if (newProgress >= 100) {
          // 上传完成
          clearUploadInterval();
          // 使用 setTimeout 确保状态更新顺序正确
          setTimeout(() => {
            setIsUploading(false);
            onFileSelect(file);
          }, 100);
          return 100;
        }
        return newProgress;
      });
    }, 200);
  }, [clearUploadInterval, onFileSelect]);

  const handleReuploadClick = () => {
    setShowReuploadConfirm(true);
  };

  const handleConfirmReupload = () => {
    setShowReuploadConfirm(false);
    // 重置裁剪状态
    setVideoDuration(207.3);
    setTrimStart(0);
    setTrimEnd(207.3);
    onFileSelect(null);
    // 延迟触发文件选择，确保状态已更新
    setTimeout(() => {
      fileInputRef.current?.click();
    }, 0);
  };

  const handleCancelReupload = () => {
    setShowReuploadConfirm(false);
  };

  return (
    <div className="h-full flex flex-col">
      {/* 中部内容区 */}
      <div className="flex-1 px-6 py-4 overflow-auto">
        {isUploading ? (
          /* 上传进度 */
          <div className="h-full flex flex-col items-center justify-center">
            <div className="w-20 h-20 rounded-full bg-[#4ADE80]/10 flex items-center justify-center mb-6">
              <CloudUpload className="w-10 h-10 text-[#4ADE80]" />
            </div>
            <p className="text-lg font-medium text-white mb-2">上传中...</p>
            <p className="text-sm text-slate-500 mb-6">进度: {Math.min(Math.round(uploadProgress), 100)}%</p>
            <div className="w-96 h-2 bg-white/[0.08] rounded-full overflow-hidden">
              <div 
                className="h-full bg-[#4ADE80] rounded-full transition-all duration-200"
                style={{ width: `${Math.min(uploadProgress, 100)}%` }}
              />
            </div>
          </div>
        ) : !uploadedFile ? (
          /* 上传区域 */
          <div
            onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`h-full border-2 border-dashed rounded-2xl flex flex-col items-center justify-center cursor-pointer transition-all duration-300 ${
              isDragging
                ? 'border-[#4ADE80] bg-[#4ADE80]/5'
                : 'border-white/[0.1] bg-white/[0.01] hover:border-[#4ADE80]/30 hover:bg-white/[0.02]'
            }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept="video/*"
              onChange={handleSelect}
              className="hidden"
            />
            <div className="w-20 h-20 rounded-full bg-[#4ADE80]/10 flex items-center justify-center mb-6">
              <CloudUpload className="w-10 h-10 text-[#4ADE80]" />
            </div>
            <p className="text-lg font-medium text-white mb-2">拖拽或选择文件上传</p>
            <p className="text-sm text-slate-500 mb-6">
              支持 MP4, MOV, AVI, WEBM 等格式，文件大小不超过 1GB，建议视频时长不超过 40 分钟
            </p>
            <Button className="bg-[#4ADE80] hover:bg-[#4ADE80]/90 text-black font-medium px-6">
              选择文件
            </Button>
          </div>
        ) : (
          /* 已上传文件显示 - 视频预览和裁剪 */
          <div className="h-full flex flex-col">
            {/* 视频裁剪卡片 */}
            <div className="rounded-2xl border border-white/[0.06] bg-[#0f0f0f] overflow-hidden">
              {/* 视频播放器 - 限制最大宽度，居中显示 */}
              <div className="relative bg-black flex items-center justify-center" style={{ minHeight: '300px' }}>
                {videoUrl ? (
                  <video
                    key={videoUrl}
                    src={videoUrl}
                    className="max-w-full max-h-[400px] w-auto h-auto"
                    controls
                    preload="metadata"
                    onLoadedMetadata={(e) => {
                      const video = e.target as HTMLVideoElement;
                      console.log('[VideoUploadStep] Video loaded, duration:', video.duration, 'url:', videoUrl);
                      setVideoDuration(video.duration || 207.3);
                      setTrimEnd(video.duration || 207.3);
                    }}
                    onError={(e) => {
                      const video = e.target as HTMLVideoElement;
                      console.error('[VideoUploadStep] Video load error:', video.error, 'url:', videoUrl);
                      alert('视频加载失败: ' + videoUrl);
                    }}
                  />
                ) : (
                  <div className="text-slate-500 text-sm">视频加载中... (videoUrl: {videoUrl || 'empty'})</div>
                )}
              </div>

              {/* 裁剪控制区 */}
              <div className="p-5 space-y-4">
                {/* 原视频时长 */}
                <div className="flex items-center justify-between">
                  <span className="text-sm text-slate-400">原视频时长</span>
                  <span className="text-sm text-[#4ADE80] font-medium">{formatTime(videoDuration)}</span>
                </div>

                {/* 选择裁剪范围 */}
                <div>
                  <span className="text-sm text-slate-400 mb-3 block">选择裁剪范围</span>
                  <div className="relative px-2 py-2">
                    <input
                      type="range"
                      min="0"
                      max={videoDuration}
                      step="0.1"
                      value={trimStart}
                      onChange={(e) => handleTrimStartChange(parseFloat(e.target.value))}
                      className="absolute w-full h-2 bg-transparent appearance-none cursor-pointer z-20"
                      style={{ top: '50%', transform: 'translateY(-50%)' }}
                    />
                    <input
                      type="range"
                      min="0"
                      max={videoDuration}
                      step="0.1"
                      value={trimEnd}
                      onChange={(e) => handleTrimEndChange(parseFloat(e.target.value))}
                      className="absolute w-full h-2 bg-transparent appearance-none cursor-pointer z-20"
                      style={{ top: '50%', transform: 'translateY(-50%)' }}
                    />
                    <div className="relative h-2 bg-white/[0.08] rounded-full">
                      <div 
                        className="absolute h-full bg-[#4ADE80] rounded-full"
                        style={{ 
                          left: `${(trimStart / videoDuration) * 100}%`, 
                          right: `${100 - (trimEnd / videoDuration) * 100}%` 
                        }}
                      />
                    </div>
                  </div>
                  <div className="flex justify-between mt-2 text-xs text-slate-500">
                    <span>{formatTime(trimStart)}</span>
                    <span>{formatTime(trimEnd)}</span>
                  </div>
                </div>

                {/* 时间输入 */}
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-xs text-slate-500 mb-1.5 block">起始时间（秒）</label>
                    <input
                      type="number"
                      value={trimStart.toFixed(1)}
                      onChange={(e) => handleTrimStartChange(parseFloat(e.target.value) || 0)}
                      className="w-full px-3 py-2 rounded-lg bg-white/[0.04] border border-white/[0.08] text-sm text-white outline-none focus:border-[#4ADE80]/50"
                      min="0"
                      max={trimEnd}
                      step="0.1"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-slate-500 mb-1.5 block">结束时间（秒）</label>
                    <input
                      type="number"
                      value={trimEnd.toFixed(1)}
                      onChange={(e) => handleTrimEndChange(parseFloat(e.target.value) || videoDuration)}
                      className="w-full px-3 py-2 rounded-lg bg-white/[0.04] border border-white/[0.08] text-sm text-white outline-none focus:border-[#4ADE80]/50"
                      min={trimStart}
                      max={videoDuration}
                      step="0.1"
                    />
                  </div>
                </div>

                {/* 裁剪后时长 */}
                <div className="flex items-center justify-between py-3 px-4 rounded-lg bg-white/[0.02] border border-white/[0.06]">
                  <span className="text-sm text-slate-400">裁剪后时长</span>
                  <div className="flex items-center gap-2">
                    <svg className="w-4 h-4 text-[#4ADE80]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <circle cx="12" cy="12" r="10"/>
                      <path d="M12 6v6l4 2"/>
                    </svg>
                    <span className="text-sm text-[#4ADE80] font-medium">{formatTime(trimEnd - trimStart)}</span>
                    <span className="text-xs text-[#4ADE80]/70">可自动转录</span>
                  </div>
                </div>

                {/* 裁剪操作按钮 */}
                <div className="flex items-center justify-between pt-2">
                  <Button variant="ghost" size="sm" className="text-slate-500 hover:text-slate-300">
                    跳过裁剪
                  </Button>
                  <Button size="sm" className="bg-[#4ADE80] hover:bg-[#4ADE80]/90 text-black font-medium gap-1.5">
                    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <circle cx="6" cy="6" r="3"/>
                      <path d="M8.12 8.12 12 12"/>
                      <circle cx="18" cy="6" r="3"/>
                      <path d="M15.88 8.12 12 12"/>
                      <path d="M12 12v8"/>
                      <circle cx="6" cy="18" r="3"/>
                      <path d="M8.12 15.88 12 12"/>
                      <circle cx="18" cy="18" r="3"/>
                      <path d="M15.88 15.88 12 12"/>
                    </svg>
                    确认裁剪
                    <ArrowRight className="w-4 h-4" />
                  </Button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* 底部操作栏 */}
      <div className="h-16 border-t border-white/[0.06] bg-[#0A0A0F] flex items-center justify-between px-6 shrink-0">
        <div>
          {onBack && (
            <Button variant="ghost" size="sm" onClick={onBack} className="text-slate-400 hover:text-white gap-1.5">
              <ArrowLeft className="w-4 h-4" />返回
            </Button>
          )}
        </div>
        <div className="flex items-center gap-3">
          {uploadedFile && (
            <Button variant="outline" size="sm" onClick={handleReuploadClick} className="border-white/[0.08] text-slate-400 hover:text-white hover:bg-white/[0.04] gap-1.5">
              <RefreshCw className="w-4 h-4" />重新上传
            </Button>
          )}
          {onNext && (
            <Button size="sm" onClick={onNext} disabled={!uploadedFile} className="bg-[#4ADE80] hover:bg-[#4ADE80]/90 text-black font-medium gap-1.5 disabled:opacity-40 disabled:cursor-not-allowed">
              下一步：配置参数
              <ArrowRight className="w-4 h-4" />
            </Button>
          )}
        </div>
      </div>

      {/* 重新上传确认弹窗 */}
      {showReuploadConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-2xl border border-white/[0.08] bg-[#141414] p-6 shadow-2xl">
            <div className="flex items-start gap-4 mb-4">
              <div className="w-12 h-12 rounded-full bg-amber-500/10 flex items-center justify-center shrink-0">
                <AlertTriangle className="w-6 h-6 text-amber-500" />
              </div>
              <div className="flex-1">
                <h3 className="text-lg font-semibold text-amber-500 mb-2">重新上传视频</h3>
                <p className="text-sm text-slate-400 leading-relaxed">
                  重新上传将会删除当前项目的字幕数据，确定要继续吗？
                </p>
              </div>
              <button onClick={handleCancelReupload} className="p-1 rounded-lg text-slate-500 hover:text-slate-300 hover:bg-white/[0.05] transition-colors">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="flex items-center justify-end gap-3 mt-6">
              <Button variant="outline" onClick={handleCancelReupload} className="border-white/[0.08] text-slate-300 hover:text-white hover:bg-white/[0.04] px-6">
                取消
              </Button>
              <Button onClick={handleConfirmReupload} className="bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-500 hover:to-purple-500 text-white px-6">
                确认重新上传
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
