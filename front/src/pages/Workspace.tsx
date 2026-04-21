import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import CreateProjectModal from '@/components/workspace/CreateProjectModal';
import VideoUploadStep from '@/components/workspace/VideoUploadStep';
import SubtitleStep from '@/components/workspace/SubtitleStep';
import ConfigStep, { type ConfigFormValue } from '@/components/workspace/ConfigStep';
import {
  uploadVideo,
  uploadSubtitle,
  readSubtitleLines,
  createMovieStoryJob,
  waitForJob,
  extractMovieStoryArtifacts,
  createVideoJob,
  extractVideoOutputs,
  type SubtitleLine,
} from '@/lib/api';
import { getAPIBaseURL } from '@/lib/config';
import { Zap, ChevronLeft, ChevronRight, RotateCcw, Bell, User, Check, Loader2, AlertTriangle, FolderOpen, X } from 'lucide-react';

type ProjectType = 'movie_review' | 'drama_mix' | 'drama_review';
type WorkflowStep = 'upload' | 'subtitle' | 'config' | 'generate';

const stepLabels: { key: WorkflowStep; label: string }[] = [
  { key: 'upload', label: '视频上传' },
  { key: 'subtitle', label: '字幕识别' },
  { key: 'config', label: '参数配置' },
  { key: 'generate', label: '内容生成' },
];

const projectTypeLabels: Record<ProjectType, string> = {
  movie_review: '影视解说',
  drama_mix: '短剧混剪',
  drama_review: '短剧解说',
};

interface Project { name: string; type: ProjectType; }

const defaultConfig: ConfigFormValue = {
  // 基础配置
  editMode: 'smart_insert',
  originalRatio: 45,
  videoLanguage: 'zh',
  narrationLanguage: 'zh',
  
  // 解说配置
  generationMode: 'auto',
  speechSpeed: 'moderate',
  wordCount: 'default',
  perspective: 'third',
  narrationStyle: 'default',
  
  // 高级选项
  scriptType: 'standard',
  temperature: 0.7,
  
  // 后端现有参数
  ttsEngine: 'edge-tts',
  voiceRole: 'female_gentle',
  speed: 1,
  aspectRatio: '16:9',
  videoQuality: 'high',
  subtitleFont: 'default',
  subtitleSize: 24,
  subtitleEnabled: true,
};

function mapVoiceRole(role: string) {
  switch (role) {
    case 'female_lively':
      return 'zh-CN-XiaoyiNeural';
    case 'male_deep':
      return 'zh-CN-YunjianNeural';
    case 'male_magnetic':
      return 'zh-CN-YunxiNeural';
    case 'female_gentle':
    default:
      return 'zh-CN-XiaoxiaoNeural';
  }
}

function mapFont(font: string) {
  switch (font) {
    case 'noto_sans':
      return 'SimHei';
    case 'noto_serif':
      return 'SimSun';
    default:
      return 'SimHei';
  }
}

export default function Workspace() {
  const navigate = useNavigate();
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [project, setProject] = useState<Project | null>(null);
  const [currentStep, setCurrentStep] = useState<WorkflowStep>('upload');
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [uploadedVideoPath, setUploadedVideoPath] = useState('');
  const [uploadedSubtitlePath, setUploadedSubtitlePath] = useState('');
  const [subtitleMode, setSubtitleMode] = useState<'auto' | 'upload' | null>(null);
  const [subtitles, setSubtitles] = useState<SubtitleLine[]>([]);
  const [isRecognizing, setIsRecognizing] = useState(false);
  const [recognitionDone, setRecognitionDone] = useState(false);
  const [isUploadingVideo, setIsUploadingVideo] = useState(false);
  const [isUploadingSubtitle, setIsUploadingSubtitle] = useState(false);
  const [config, setConfig] = useState<ConfigFormValue>(defaultConfig);
  const [generatedScriptItems, setGeneratedScriptItems] = useState<any[]>([]);
  const [generatedScriptPath, setGeneratedScriptPath] = useState('');
  const [generateTaskId, setGenerateTaskId] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [generatedVideos, setGeneratedVideos] = useState<string[]>([]);
  const [statusMessage, setStatusMessage] = useState('');
  const [errorMessage, setErrorMessage] = useState('');

  const currentStepIndex = stepLabels.findIndex((s) => s.key === currentStep);

  const canGoNext = useMemo(() => {
    if (currentStep === 'upload') return Boolean(uploadedVideoPath) && !isUploadingVideo;
    if (currentStep === 'subtitle') return recognitionDone;
    return true;
  }, [currentStep, uploadedVideoPath, isUploadingVideo, recognitionDone]);

  const handleCreateProject = (name: string, type: ProjectType) => {
    setProject({ name, type });
    setCreateModalOpen(false);
    setCurrentStep('upload');
    setUploadedFile(null);
    setUploadedVideoPath('');
    setUploadedSubtitlePath('');
    setSubtitleMode(null);
    setSubtitles([]);
    setRecognitionDone(false);
    setGeneratedScriptItems([]);
    setGeneratedScriptPath('');
    setGeneratedVideos([]);
    setGenerateTaskId('');
    setStatusMessage('');
    setErrorMessage('');
    setConfig(defaultConfig);
  };

  const handleNext = () => {
    const idx = currentStepIndex;
    if (idx < stepLabels.length - 1) setCurrentStep(stepLabels[idx + 1].key);
  };

  const handlePrev = () => {
    const idx = currentStepIndex;
    if (idx > 0) setCurrentStep(stepLabels[idx - 1].key);
  };

  const handleReset = () => {
    setUploadedFile(null);
    setUploadedVideoPath('');
    setUploadedSubtitlePath('');
    setSubtitleMode(null);
    setSubtitles([]);
    setRecognitionDone(false);
    setGeneratedScriptItems([]);
    setGeneratedScriptPath('');
    setGeneratedVideos([]);
    setGenerateTaskId('');
    setErrorMessage('');
    setStatusMessage('');
    setConfig(defaultConfig);
    setCurrentStep('upload');
  };

  const handleVideoFileSelect = async (file: File | null) => {
    setUploadedFile(file);
    setUploadedVideoPath('');
    setRecognitionDone(false);
    setSubtitleMode(null);
    setSubtitles([]);
    setGeneratedScriptItems([]);
    setGeneratedScriptPath('');
    setGeneratedVideos([]);
    setErrorMessage('');
    setStatusMessage('');
    if (!file) return;

    try {
      setIsUploadingVideo(true);
      setStatusMessage('正在上传视频到后端工作区...');
      const result = await uploadVideo(file);
      console.log('Upload result:', result);
      setUploadedVideoPath(result.url && result.url.startsWith('/') ? result.url : result.path);
      setStatusMessage(`视频上传完成：${result.filename}`);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : '视频上传失败');
    } finally {
      setIsUploadingVideo(false);
    }
  };

  const handleSubtitleFileSelect = async (file: File, parsed: SubtitleLine[]) => {
    try {
      setIsUploadingSubtitle(true);
      setStatusMessage('正在上传字幕文件到后端工作区...');
      const result = await uploadSubtitle(file);
      setUploadedSubtitlePath(result.path);
      setSubtitles(parsed);
      setRecognitionDone(true);
      setStatusMessage(`字幕上传完成：${result.filename}`);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : '字幕上传失败');
    } finally {
      setIsUploadingSubtitle(false);
    }
  };

  const handleStartRecognition = async () => {
    if (!uploadedVideoPath) {
      setErrorMessage('请先上传视频');
      return;
    }

    try {
      setIsRecognizing(true);
      setErrorMessage('');
      setStatusMessage('正在提交 Qwen 语音识别与脚本分析任务...');
      const accepted = await createMovieStoryJob({
        video_path: uploadedVideoPath,
        subtitle_path: uploadedSubtitlePath,
        video_theme: project?.name || '',
        narration_style: project?.type === 'movie_review' ? 'cinematic' : 'general',
        generation_mode: 'balanced',
        visual_mode: 'auto',
        target_duration_minutes: 8,
        highlight_only: false,
        asr_backend: 'qwen3.6-plus',
      });
      setStatusMessage(`识别任务已创建：${accepted.task_id}`);
      const snapshot = await waitForJob(accepted.task_id, {
        intervalMs: 2000,
        onTick: (tick) => setStatusMessage(`字幕识别中 ${tick.progress}% · ${tick.message || '处理中'}`),
      });
      const artifacts = extractMovieStoryArtifacts(snapshot);
      if (artifacts.subtitlePath) {
        const lines = await readSubtitleLines(artifacts.subtitlePath);
        setSubtitles(lines);
        setUploadedSubtitlePath(artifacts.subtitlePath);
      }
      if (artifacts.scriptItems.length) {
        setGeneratedScriptItems(artifacts.scriptItems);
      }
      if (artifacts.scriptPath) {
        setGeneratedScriptPath(artifacts.scriptPath);
      }
      setSubtitleMode('auto');
      setRecognitionDone(true);
      setStatusMessage('字幕识别完成，已回填到编辑区');
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : '字幕识别失败');
    } finally {
      setIsRecognizing(false);
    }
  };

  const handleGenerate = async () => {
    if (!uploadedVideoPath) {
      setErrorMessage('缺少视频路径，无法生成');
      return;
    }
    if (!generatedScriptItems.length && !generatedScriptPath) {
      setErrorMessage('当前没有可用脚本，请先完成字幕识别');
      return;
    }

    try {
      setIsGenerating(true);
      setErrorMessage('');
      setStatusMessage('正在提交最终视频生成任务...');
      const accepted = await createVideoJob({
        video_clip_json: generatedScriptItems,
        video_clip_json_path: generatedScriptPath,
        video_origin_path: uploadedVideoPath,
        video_aspect: config.aspectRatio,
        voice_name: mapVoiceRole(config.voiceRole),
        voice_rate: config.speed,
        voice_pitch: 1,
        tts_engine: config.ttsEngine,
        subtitle_enabled: config.subtitleEnabled,
        font_name: mapFont(config.subtitleFont),
        font_size: config.subtitleSize,
        text_fore_color: '#FFFFFF',
        stroke_color: '#000000',
        stroke_width: 1.5,
        subtitle_position: 'bottom',
        custom_position: 70,
        bgm_name: 'random',
        bgm_type: 'random',
        n_threads: 16,
      });
      setGenerateTaskId(accepted.task_id);
      setStatusMessage(`生成任务已创建：${accepted.task_id}`);
      setCurrentStep('generate');
      const snapshot = await waitForJob(accepted.task_id, {
        intervalMs: 2500,
        onTick: (tick) => setStatusMessage(`视频生成中 ${tick.progress}% · ${tick.message || '处理中'}`),
      });
      const outputs = extractVideoOutputs(snapshot);
      setGeneratedVideos(outputs);
      setStatusMessage(outputs.length ? '视频生成完成' : '任务完成，但暂未发现输出路径');
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : '生成失败');
    } finally {
      setIsGenerating(false);
    }
  };

  if (!project) {
    return (
      <div className="h-screen flex flex-col bg-[#0A0A0F] text-white">
        <header className="h-14 border-b border-white/[0.06] bg-[#0A0A0F]/80 backdrop-blur-xl flex items-center justify-between px-6 shrink-0">
          <div className="flex items-center gap-3">
            <button onClick={() => navigate('/')} className="text-slate-400 hover:text-white transition-colors"><ChevronLeft className="w-5 h-5" /></button>
            <div className="w-6 h-6 rounded-md gradient-bg flex items-center justify-center"><Zap className="w-3 h-3 text-white" /></div>
            <span className="font-semibold text-sm">AIVideoGPT</span>
          </div>
          <div className="flex items-center gap-3"><Bell className="w-4 h-4 text-slate-400" /><div className="flex items-center gap-2"><div className="w-6 h-6 rounded-full bg-indigo-500/20 flex items-center justify-center"><User className="w-3 h-3 text-indigo-400" /></div><span className="text-sm text-slate-400">hello</span></div></div>
        </header>
        <div className="flex-1 flex items-center justify-center"><div className="text-center"><div className="w-20 h-20 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center mx-auto mb-5"><Zap className="w-9 h-9 text-indigo-400" /></div><h2 className="text-xl font-semibold text-white mb-2">开始创作</h2><p className="text-sm text-slate-400 mb-6">创建一个新项目，开始您的 AI 视频创作之旅</p><Button onClick={() => setCreateModalOpen(true)} className="gradient-bg hover:brightness-110 text-white rounded-xl px-8 gap-2" size="lg">创建项目</Button></div></div>
        <CreateProjectModal open={createModalOpen} onClose={() => setCreateModalOpen(false)} onCreate={handleCreateProject} />
      </div>
    );
  }

  return (
    <div className="h-screen flex flex-col bg-[#0A0A0F] text-white">
      <header className="h-14 border-b border-white/[0.06] bg-[#0A0A0F] flex items-center justify-between px-6 shrink-0">
        <div className="flex items-center gap-3"><div className="w-6 h-6 rounded-md gradient-bg flex items-center justify-center"><Zap className="w-3 h-3 text-white" /></div><span className="font-semibold text-sm">AIVideoGPT</span></div>
        <div className="flex items-center bg-white/[0.04] rounded-lg p-0.5">{['素材', '分析', '配音'].map((tab, i) => <button key={tab} className={`px-4 py-1.5 rounded-md text-xs font-medium transition-all ${i === 0 ? 'bg-indigo-500/20 text-indigo-400' : 'text-slate-400 hover:text-slate-300'}`}>{tab}</button>)}</div>
        <div className="flex items-center gap-3"><Bell className="w-4 h-4 text-slate-400" /><div className="flex items-center gap-2"><div className="w-6 h-6 rounded-full bg-indigo-500/20 flex items-center justify-center"><User className="w-3 h-3 text-indigo-400" /></div><span className="text-sm text-slate-400">hello</span><span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">已验证</span></div></div>
      </header>

      <div className="px-6 pt-4 pb-3 shrink-0">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <span className="text-sm text-slate-400">项目名称：</span>
            <span className="text-sm font-medium text-white">{project.name}</span>
            <span className="text-xs px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">{projectTypeLabels[project.type]}</span>
          </div>
          {uploadedVideoPath && <div className="text-xs text-emerald-400 flex items-center gap-1"><Check className="w-3 h-3" />已接入后端工作区</div>}
        </div>

        <div className="flex items-center gap-1">{stepLabels.map((step, i) => { const isActive = currentStepIndex === i; const isDone = currentStepIndex > i; return <div key={step.key} className="flex items-center flex-1"><div className="flex items-center gap-2.5 flex-1"><div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold transition-all duration-300 shrink-0 ${isDone ? 'bg-indigo-500 text-white' : isActive ? 'bg-indigo-500 text-white shadow-lg shadow-indigo-500/25' : 'bg-white/[0.05] text-slate-500 border border-white/[0.08]'}`}>{isDone ? <Check className="w-3.5 h-3.5" /> : i + 1}</div><span className={`text-xs whitespace-nowrap font-medium ${isActive ? 'text-white' : isDone ? 'text-indigo-400' : 'text-slate-500'}`}>{step.label}</span></div>{i < stepLabels.length - 1 && <div className={`h-px flex-1 mx-2 ${isDone ? 'bg-indigo-500/50' : 'bg-white/[0.06]'}`} />}</div>; })}</div>
      </div>

      {(statusMessage || errorMessage) && (
        <div className="px-6 pb-3 shrink-0">
          {statusMessage && (
            <div className="rounded-xl border border-indigo-500/20 bg-indigo-500/10 px-4 py-3 text-sm text-indigo-200 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Loader2 className={`w-4 h-4 ${isUploadingVideo || isUploadingSubtitle || isRecognizing || isGenerating ? 'animate-spin' : ''}`} />
                {statusMessage}
              </div>
              <button 
                onClick={() => setStatusMessage('')}
                className="text-indigo-400 hover:text-indigo-300 transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          )}
          {errorMessage && (
            <div className="mt-2 rounded-xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-200 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <AlertTriangle className="w-4 h-4" />
                {errorMessage}
              </div>
              <button 
                onClick={() => setErrorMessage('')}
                className="text-red-400 hover:text-red-300 transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          )}
        </div>
      )}

      <div className="flex-1 overflow-hidden">
        {currentStep === 'upload' && <VideoUploadStep uploadedFile={uploadedFile} onFileSelect={handleVideoFileSelect} onNext={handleNext} onBack={handlePrev} videoUrl={uploadedVideoPath ? `${getAPIBaseURL()}${uploadedVideoPath}` : ''} />}
        {currentStep === 'subtitle' && <SubtitleStep subtitleMode={subtitleMode} onModeSelect={setSubtitleMode} isRecognizing={isRecognizing} recognitionDone={recognitionDone} onStartRecognition={handleStartRecognition} subtitles={subtitles} onSubtitlesChange={setSubtitles} onSubtitleFileSelect={handleSubtitleFileSelect} videoFile={uploadedFile} videoUrl={uploadedVideoPath ? `${getAPIBaseURL()}${uploadedVideoPath}` : ''} onReupload={handleReset} />}
        {currentStep === 'config' && <ConfigStep projectType={project?.type || 'movie_review'} value={config} onChange={setConfig} onGenerate={handleGenerate} generating={isGenerating} onBack={() => setCurrentStep('subtitle')} onReupload={handleReset} />}
        {currentStep === 'generate' && (
          <div className="h-full flex items-center justify-center px-6">
            <div className="w-full max-w-3xl rounded-2xl border border-white/[0.06] bg-white/[0.03] p-8">
              <div className="flex items-center gap-3 mb-6"><div className="w-12 h-12 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center"><Zap className="w-6 h-6 text-indigo-400" /></div><div><h3 className="text-lg font-semibold text-white">生成任务状态</h3><p className="text-sm text-slate-400">任务 ID：{generateTaskId || '尚未创建'}</p></div></div>
              <div className="rounded-xl border border-white/[0.06] bg-black/20 p-4 text-sm text-slate-300 mb-4">{statusMessage || '等待开始生成'}</div>
              {generatedVideos.length > 0 ? (
                <div className="space-y-3">
                  <h4 className="text-sm font-semibold text-white">输出结果</h4>
                  {generatedVideos.map((video) => <div key={video} className="rounded-xl border border-emerald-500/20 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-200 flex items-center gap-2"><FolderOpen className="w-4 h-4" />{video}</div>)}
                </div>
              ) : (
                <div className="text-sm text-slate-500">当前还没有输出视频路径。任务完成后会展示在这里。</div>
              )}
            </div>
          </div>
        )}
      </div>

      <CreateProjectModal open={createModalOpen} onClose={() => setCreateModalOpen(false)} onCreate={handleCreateProject} />
    </div>
  );
}
