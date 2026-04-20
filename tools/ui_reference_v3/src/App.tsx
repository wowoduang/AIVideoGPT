/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useCallback, useEffect, useState } from 'react';
import { useMachine } from '@xstate/react';
import { videoMachine } from '@/lib/videoMachine';
import { api } from '@/lib/api';
import { Job, User, WorkspaceInfo } from '@/types/api';
import { motion, AnimatePresence } from 'motion/react';
import { 
  Upload, 
  Video, 
  FileText, 
  Mic, 
  Play, 
  RefreshCw, 
  CheckCircle, 
  AlertCircle,
  ChevronRight,
  Edit3,
  Download,
  Settings,
  Bell,
  ChevronDown,
  Trash2,
  Volume2,
  Zap,
  Languages,
  Clock,
  Type,
  Eye,
  Sparkles,
  ArrowLeft,
  Save,
  LogIn,
  User as UserIcon,
  History as HistoryIcon,
  LogOut
} from 'lucide-react';
import { useDropzone } from 'react-dropzone';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Toaster, toast } from 'sonner';
import { Slider } from '@/components/ui/slider';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import { cn } from '@/lib/utils';

export default function App() {
  const [state, send] = useMachine(videoMachine);
  const { context } = state;
  const [user, setUser] = useState<User | null>(null);
  const [history, setHistory] = useState<Job[]>([]);
  const [activeTab, setActiveTab] = useState<'create' | 'history' | 'auth'>('create');
  const [authMode, setAuthMode] = useState<'login' | 'register'>('login');
  const [authData, setAuthData] = useState({ email: '', password: '', username: '' });

  const [workspace, setWorkspace] = useState<WorkspaceInfo | null>(null);

  // Load draft from localStorage
  useEffect(() => {
    const draft = localStorage.getItem('video_config_draft');
    if (draft) {
      try {
        send({ type: 'SET_CONFIG', config: JSON.parse(draft) });
      } catch (e) {
        console.error('Failed to load draft', e);
      }
    }
    api.getWorkspace().then(setWorkspace).catch(() => {});
  }, [send]);

  // Save draft to localStorage
  useEffect(() => {
    localStorage.setItem('video_config_draft', JSON.stringify(context.config));
  }, [context.config]);

  // Check auth on mount
  useEffect(() => {
    api.getMe().then(setUser).catch(() => setUser(null));
  }, []);

  // Fetch history when history tab is active
  useEffect(() => {
    if (activeTab === 'history' && user) {
      api.getHistory().then(setHistory).catch(err => toast.error(err.message));
    }
  }, [activeTab, user]);

  // Polling logic for tasks
  useEffect(() => {
    let timer: number;
    if (context.taskId && !['completed', 'failed', 'canceled'].includes(state.value as string)) {
      const poll = async () => {
        try {
          const job = await api.getJobStatus(context.taskId!);
          if (job.status === 'completed') {
            if (state.matches('analyzing')) {
              send({ type: 'ANALYSIS_COMPLETE', analysis: job.result?.task_dir || 'Done' });
            } else if (state.matches('scripting')) {
              send({ type: 'SCRIPT_COMPLETE', script: job.result?.task_dir || 'Done' });
            } else if (state.matches('generatingAudio')) {
              send({ type: 'AUDIO_COMPLETE', audioUrl: job.result?.combined_videos?.[0] || '' });
            }
          } else if (job.status === 'failed') {
            send({ type: 'ERROR', message: job.result?.error || 'Task failed' });
          } else {
            send({ type: 'SET_PROGRESS', progress: job.progress });
            timer = window.setTimeout(poll, 2000);
          }
        } catch (err) {
          send({ type: 'ERROR', message: (err as Error).message });
        }
      };
      timer = window.setTimeout(poll, 2000);
    }
    return () => clearTimeout(timer);
  }, [context.taskId, state.value, send]);

  const handleAuth = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = authMode === 'login' 
        ? await api.login({ email: authData.email, password: authData.password })
        : await api.register(authData);
      setUser(res.user);
      setActiveTab('create');
      toast.success(authMode === 'login' ? '登录成功' : '注册成功');
    } catch (err) {
      toast.error((err as Error).message);
    }
  };

  const handleLogout = async () => {
    await api.logout();
    setUser(null);
    toast.success('已退出登录');
  };

  const startJob = async () => {
    if (!user) {
      setActiveTab('auth');
      toast.error('请先登录');
      return;
    }
    try {
      let job: Job;
      if (state.matches('configuring')) {
        job = await api.createMovieStoryJob({
          video_path: context.videoFile?.name, // Simplified for demo
          config: context.config
        });
      } else if (state.matches('editing')) {
        job = await api.createVideoJob({
          script: context.script,
          config: context.config
        });
      } else {
        return;
      }
      send({ type: 'TASK_CREATED', taskId: job.task_id });
    } catch (err) {
      toast.error((err as Error).message);
    }
  };

  const onDrop = useCallback((acceptedFiles: File[], fileRejections: any[]) => {
    if (fileRejections.length > 0) {
      const rejection = fileRejections[0];
      if (rejection.errors[0]?.code === 'file-too-large') {
        toast.error('文件太大，最大支持 10GB');
      } else {
        toast.error('文件格式不支持');
      }
      return;
    }
    if (acceptedFiles.length > 0) {
      send({ type: 'UPLOAD', file: acceptedFiles[0] });
    }
  }, [send]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'video/mp4': ['.mp4'],
      'video/quicktime': ['.mov'],
      'video/x-msvideo': ['.avi'],
      'video/webm': ['.webm']
    },
    multiple: false,
    maxSize: 10 * 1024 * 1024 * 1024 // 10GB
  } as any);

  const downloadAudio = () => {
    if (!context.audioUrl) return;
    const link = document.createElement('a');
    link.href = context.audioUrl;
    link.download = 'voiceover.wav';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    toast.success('下载已开始');
  };

  const copyScript = () => {
    if (!context.script) return;
    navigator.clipboard.writeText(context.script);
    toast.success('脚本已复制到剪贴板');
  };

  const Sidebar = () => {
    const menuItems = [
      { id: 'create', label: '创作', icon: Video, active: activeTab === 'create' },
      { id: 'history', label: '历史', icon: HistoryIcon, active: activeTab === 'history' },
    ];

    return (
      <div className="w-20 bg-black/40 border-r border-white/5 flex flex-col items-center py-8 gap-8 backdrop-blur-xl fixed left-0 top-0 bottom-0 z-50">
        <div className="w-12 h-12 bg-primary rounded-2xl flex items-center justify-center shadow-[0_0_20px_rgba(57,255,20,0.3)] mb-4">
          <Zap className="w-7 h-7 text-black" />
        </div>
        {menuItems.map((item) => (
          <button
            key={item.id}
            onClick={() => setActiveTab(item.id as any)}
            className={cn(
              "flex flex-col items-center gap-1 group transition-all",
              item.active ? "text-primary" : "text-muted-foreground hover:text-white"
            )}
          >
            <div className={cn(
              "w-12 h-12 rounded-2xl flex items-center justify-center transition-all",
              item.active ? "bg-primary/10" : "group-hover:bg-white/5"
            )}>
              <item.icon className="w-6 h-6" />
            </div>
            <span className="text-[10px] font-black uppercase tracking-widest">{item.label}</span>
          </button>
        ))}
        
        <div className="mt-auto flex flex-col gap-6">
          <button
            onClick={() => user ? handleLogout() : setActiveTab('auth')}
            className={cn(
              "flex flex-col items-center gap-1 group transition-all",
              activeTab === 'auth' ? "text-primary" : "text-muted-foreground hover:text-white"
            )}
          >
            <div className={cn(
              "w-12 h-12 rounded-2xl flex items-center justify-center transition-all",
              activeTab === 'auth' ? "bg-primary/10" : "group-hover:bg-white/5"
            )}>
              {user ? <LogOut className="w-6 h-6" /> : <UserIcon className="w-6 h-6" />}
            </div>
            <span className="text-[10px] font-black uppercase tracking-widest">{user ? '退出' : '登录'}</span>
          </button>
        </div>
      </div>
    );
  };

  const StepIndicator = () => {
    const steps = [
      { id: 1, label: '视频上传', active: state.matches('idle') || state.matches('uploading') },
      { id: 2, label: '参数配置', active: state.matches('configuring') },
      { id: 3, label: '内容生成', active: state.matches('analyzing') || state.matches('scripting') || state.matches('editing') || state.matches('generatingAudio') || state.matches('previewing') }
    ];

    return (
      <div className="flex items-center gap-8 mb-12 bg-white/[0.02] p-6 rounded-3xl border border-white/5 narrato-glass">
        {steps.map((step, idx) => (
          <React.Fragment key={step.id}>
            <div className="flex items-center gap-4">
              <div className={cn(
                "w-12 h-12 rounded-2xl flex items-center justify-center text-lg font-black transition-all",
                step.active ? "bg-primary text-black shadow-[0_0_30px_rgba(57,255,20,0.3)]" : "bg-white/5 text-muted-foreground"
              )}>
                {step.id}
              </div>
              <div className="flex flex-col">
                <span className={cn(
                  "text-xs uppercase tracking-widest font-bold opacity-50",
                  step.active ? "text-primary" : "text-muted-foreground"
                )}>Step {step.id}</span>
                <span className={cn(
                  "text-lg font-bold transition-colors",
                  step.active ? "text-white" : "text-muted-foreground"
                )}>
                  {step.label}
                </span>
              </div>
            </div>
            {idx < steps.length - 1 && (
              <div className="h-[1px] flex-1 bg-white/5" />
            )}
          </React.Fragment>
        ))}
      </div>
    );
  };

  const renderState = () => {
    if (activeTab === 'auth') {
      return (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="max-w-md mx-auto space-y-8 py-20">
          <div className="text-center space-y-4">
            <h2 className="text-4xl font-black tracking-tight">{authMode === 'login' ? '欢迎回来' : '创建账号'}</h2>
            <p className="text-muted-foreground">登录以管理您的 AI 视频创作任务</p>
          </div>
          <form onSubmit={handleAuth} className="space-y-6 bg-white/5 p-10 rounded-[2.5rem] border border-white/5">
            {authMode === 'register' && (
              <div className="space-y-2">
                <label className="text-xs font-bold uppercase tracking-widest text-muted-foreground">用户名</label>
                <input 
                  type="text" 
                  required
                  className="w-full bg-black/40 border border-white/10 rounded-2xl p-4 focus:border-primary outline-none transition-all"
                  value={authData.username}
                  onChange={e => setAuthData({...authData, username: e.target.value})}
                />
              </div>
            )}
            <div className="space-y-2">
              <label className="text-xs font-bold uppercase tracking-widest text-muted-foreground">邮箱</label>
              <input 
                type="email" 
                required
                className="w-full bg-black/40 border border-white/10 rounded-2xl p-4 focus:border-primary outline-none transition-all"
                value={authData.email}
                onChange={e => setAuthData({...authData, email: e.target.value})}
              />
            </div>
            <div className="space-y-2">
              <label className="text-xs font-bold uppercase tracking-widest text-muted-foreground">密码</label>
              <input 
                type="password" 
                required
                className="w-full bg-black/40 border border-white/10 rounded-2xl p-4 focus:border-primary outline-none transition-all"
                value={authData.password}
                onChange={e => setAuthData({...authData, password: e.target.value})}
              />
            </div>
            <Button type="submit" className="w-full bg-primary text-black font-black h-14 rounded-2xl shadow-[0_0_30px_rgba(57,255,20,0.2)]">
              {authMode === 'login' ? '立即登录' : '注册并开始'}
            </Button>
            <div className="text-center">
              <button 
                type="button"
                onClick={() => setAuthMode(authMode === 'login' ? 'register' : 'login')}
                className="text-sm text-muted-foreground hover:text-primary transition-colors"
              >
                {authMode === 'login' ? '没有账号？立即注册' : '已有账号？立即登录'}
              </button>
            </div>
          </form>
        </motion.div>
      );
    }

    if (activeTab === 'history') {
      return (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-8">
          <div className="flex justify-between items-center">
            <h2 className="text-4xl font-black tracking-tight">历史任务</h2>
            <Button variant="outline" onClick={() => api.getHistory().then(setHistory)} className="rounded-xl border-white/10">
              <RefreshCw className="w-4 h-4 mr-2" /> 刷新
            </Button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {history.map(job => (
              <Card key={job.task_id} className="bg-white/5 border-white/5 rounded-[2rem] overflow-hidden hover:border-primary/30 transition-all group">
                <CardHeader className="p-8">
                  <div className="flex justify-between items-start mb-4">
                    <Badge className={cn(
                      "font-bold px-3 py-1",
                      job.status === 'completed' ? "bg-green-500/20 text-green-500" :
                      job.status === 'failed' ? "bg-red-500/20 text-red-500" :
                      "bg-primary/20 text-primary"
                    )}>
                      {job.status.toUpperCase()}
                    </Badge>
                    <span className="text-[10px] text-muted-foreground font-mono">{new Date(job.created_at).toLocaleString()}</span>
                  </div>
                  <CardTitle className="text-xl font-black truncate">{job.type}</CardTitle>
                </CardHeader>
                <CardContent className="p-8 pt-0 space-y-6">
                  <div className="space-y-2">
                    <div className="flex justify-between text-xs font-bold uppercase tracking-widest text-muted-foreground">
                      <span>Progress</span>
                      <span>{job.progress}%</span>
                    </div>
                    <Progress value={job.progress} className="h-2 bg-white/5" />
                  </div>
                  {job.status === 'completed' && (
                    <Button variant="secondary" className="w-full rounded-xl font-bold bg-white/5 hover:bg-primary hover:text-black transition-all">
                      查看产物
                    </Button>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
        </motion.div>
      );
    }

    switch (true) {
      case state.matches('idle'):
        return (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            className="space-y-12"
          >
            <div className="flex justify-between items-end">
              <div className="space-y-4">
                <h2 className="text-6xl font-black tracking-tighter leading-none">
                  开始您的 <br />
                  <span className="text-primary">AI 创作之旅</span>
                </h2>
                <p className="text-muted-foreground text-xl max-w-lg">
                  上传视频，让 AI 为您生成专业级解说词与配音，开启高效创作模式。
                </p>
              </div>
              <div className="flex gap-4">
                <div className="bg-white/5 p-6 rounded-3xl border border-white/5 text-center min-w-[140px]">
                  <div className="text-3xl font-black text-primary">10GB</div>
                  <div className="text-[10px] uppercase tracking-widest text-muted-foreground font-bold mt-1">Max Size</div>
                </div>
                <div className="bg-white/5 p-6 rounded-3xl border border-white/5 text-center min-w-[140px]">
                  <div className="text-3xl font-black text-primary">4K</div>
                  <div className="text-[10px] uppercase tracking-widest text-muted-foreground font-bold mt-1">Resolution</div>
                </div>
              </div>
            </div>

            <StepIndicator />

            <div
              {...getRootProps()}
              className={cn(
                "w-full aspect-[21/9] border-2 border-dashed rounded-[3rem] transition-all cursor-pointer flex flex-col items-center justify-center gap-8 group relative overflow-hidden",
                isDragActive 
                  ? "border-primary bg-primary/5 scale-[1.01]" 
                  : "border-white/10 bg-white/[0.02] hover:border-primary/50 hover:bg-white/[0.04]"
              )}
            >
              <input {...getInputProps()} />
              
              {/* Decorative background glow */}
              <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-primary/5 blur-[120px] rounded-full pointer-events-none" />

              <div className="w-32 h-32 rounded-[2.5rem] bg-primary flex items-center justify-center group-hover:scale-110 transition-transform duration-500 shadow-[0_0_50px_rgba(57,255,20,0.2)]">
                <Upload className="w-12 h-12 text-black" />
              </div>
              <div className="text-center space-y-4 relative z-10">
                <h3 className="text-4xl font-black tracking-tight">点击或拖拽视频到此处</h3>
                <p className="text-muted-foreground text-xl">支持 MP4, MOV, AVI, WEBM 格式</p>
              </div>
              
              <div className="flex gap-4 relative z-10">
                <div className="flex items-center gap-2 bg-black/40 px-6 py-3 rounded-full border border-white/10 backdrop-blur-md">
                  <div className="w-2 h-2 rounded-full bg-primary animate-pulse" />
                  <span className="text-xs font-bold uppercase tracking-widest">本地安全处理</span>
                </div>
                <div className="flex items-center gap-2 bg-black/40 px-6 py-3 rounded-full border border-white/10 backdrop-blur-md">
                  <Zap className="w-4 h-4 text-primary" />
                  <span className="text-xs font-bold uppercase tracking-widest">极速 AI 分析</span>
                </div>
              </div>
            </div>
          </motion.div>
        );

      case state.matches('uploading'):
        return (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex flex-col items-center justify-center min-h-[600px] gap-16"
          >
            <div className="relative">
              <div className="absolute inset-0 animate-ping rounded-full bg-primary/20 scale-150" />
              <div className="relative w-48 h-48 rounded-[3rem] bg-primary flex items-center justify-center shadow-[0_0_80px_rgba(57,255,20,0.4)]">
                <Upload className="w-20 h-20 text-black animate-bounce" />
              </div>
            </div>
            <div className="text-center space-y-6">
              <h2 className="text-5xl font-black tracking-tighter">正在准备您的创作空间...</h2>
              <p className="text-muted-foreground text-xl max-w-md mx-auto">
                正在优化视频流以供 AI 深度分析，这通常只需要几秒钟。
              </p>
            </div>
            <div className="w-full max-w-2xl space-y-6">
              <div className="h-4 bg-white/5 rounded-full overflow-hidden border border-white/5 p-1">
                <motion.div 
                  initial={{ width: "0%" }}
                  animate={{ width: "100%" }}
                  transition={{ duration: 3, ease: "easeInOut" }}
                  className="h-full bg-primary rounded-full shadow-[0_0_15px_rgba(57,255,20,0.5)]"
                />
              </div>
              <div className="flex justify-between text-xs font-black text-primary uppercase tracking-[0.4em]">
                <span>Initializing Engine</span>
                <span className="animate-pulse">Optimizing Stream...</span>
              </div>
            </div>
          </motion.div>
        );

      case state.matches('configuring'):
        return (
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            className="space-y-12"
          >
            <div className="flex justify-between items-end">
              <div className="space-y-4">
                <h2 className="text-5xl font-black tracking-tighter leading-none">
                  配置 <span className="text-primary">创作参数</span>
                </h2>
                <p className="text-muted-foreground text-lg">
                  根据视频内容特点，选择合适的分析模式和参数，让 AI 更懂您的需求。
                </p>
              </div>
            </div>

            <StepIndicator />

            <div className="flex flex-col gap-8">
              <div className="space-y-8">
                <div className="narrato-glass rounded-[3rem] overflow-hidden">
                  <div className="p-10 space-y-12">
                    {/* Mode Selection */}
                    <div className="space-y-8">
                      <div className="flex items-center gap-4">
                        <div className="w-12 h-12 rounded-2xl bg-primary/10 flex items-center justify-center">
                          <Zap className="w-6 h-6 text-primary" />
                        </div>
                        <h4 className="text-2xl font-black tracking-tight">视频剪辑模式</h4>
                      </div>
                      <div className="grid grid-cols-3 gap-6">
                        {[
                          { id: 'commentary', label: '仅解说', desc: '解说覆盖全程，适合调节节奏' },
                          { id: 'original', label: '仅原片', desc: '保留视频原声，不额外添加解说' },
                          { id: 'smart', label: '智能穿插', desc: 'AI 智能判断原片与解说段落' }
                        ].map((m) => (
                          <button
                            key={m.id}
                            onClick={() => send({ type: 'SET_CONFIG', config: { mode: m.id as any } })}
                            className={cn(
                              "p-8 rounded-[2rem] border text-left transition-all space-y-4 relative group",
                              context.config.mode === m.id 
                                ? "border-primary bg-primary/5 shadow-[0_0_30px_rgba(57,255,20,0.1)]" 
                                : "border-white/5 bg-white/[0.02] hover:border-white/20"
                            )}
                          >
                            <div className={cn(
                              "w-4 h-4 rounded-full border-2 transition-all absolute top-6 right-6",
                              context.config.mode === m.id ? "border-primary bg-primary" : "border-white/20"
                            )} />
                            <div className="font-black text-xl">{m.label}</div>
                            <div className="text-sm text-muted-foreground leading-relaxed opacity-70">{m.desc}</div>
                          </button>
                        ))}
                      </div>
                    </div>

                    {/* Ratio Slider - Only show if mode is smart or original */}
                    {(context.config.mode === 'smart' || context.config.mode === 'original') && (
                      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="space-y-8">
                        <div className="flex justify-between items-center">
                          <div className="flex items-center gap-4">
                            <div className="w-12 h-12 rounded-2xl bg-primary/10 flex items-center justify-center">
                              <Play className="w-6 h-6 text-primary" />
                            </div>
                            <h4 className="text-2xl font-black tracking-tight">原片占比</h4>
                          </div>
                          <div className="px-6 py-2 bg-primary/10 rounded-full border border-primary/20">
                            <span className="text-primary font-black text-2xl">{context.config.originalRatio}%</span>
                          </div>
                        </div>
                        <div className="px-4">
                          <Slider 
                            value={[context.config.originalRatio]} 
                            onValueChange={(v) => {
                              const val = Array.isArray(v) ? v[0] : v;
                              send({ type: 'SET_CONFIG', config: { originalRatio: val } });
                            }}
                            max={100} 
                            step={1}
                            className="py-4"
                          />
                          <div className="flex justify-between text-[10px] font-black text-muted-foreground uppercase tracking-widest mt-4">
                            <span>20% Focus</span>
                            <span>Balanced</span>
                            <span>100% Original</span>
                          </div>
                        </div>
                      </motion.div>
                    )}

                    {/* Language Selection */}
                    <div className="grid grid-cols-2 gap-12">
                      <div className="space-y-6">
                        <div className="flex items-center gap-4">
                          <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center">
                            <Languages className="w-5 h-5 text-primary" />
                          </div>
                          <h4 className="text-xl font-black tracking-tight">视频原语言</h4>
                        </div>
                        <select 
                          className="w-full bg-white/[0.03] border border-white/5 rounded-2xl p-5 focus:outline-none focus:border-primary transition-all appearance-none cursor-pointer font-bold"
                          value={context.config.sourceLang}
                          onChange={(e) => send({ type: 'SET_CONFIG', config: { sourceLang: e.target.value } })}
                        >
                          <option value="zh-CN">简体中文</option>
                          <option value="en-US">English</option>
                          <option value="ja-JP">日本語</option>
                        </select>
                      </div>
                      <div className="space-y-6">
                        <div className="flex items-center gap-4">
                          <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center">
                            <Languages className="w-5 h-5 text-primary" />
                          </div>
                          <h4 className="text-xl font-black tracking-tight">解说语言</h4>
                        </div>
                        <select 
                          className="w-full bg-white/[0.03] border border-white/5 rounded-2xl p-5 focus:outline-none focus:border-primary transition-all appearance-none cursor-pointer font-bold"
                          value={context.config.targetLang}
                          onChange={(e) => send({ type: 'SET_CONFIG', config: { targetLang: e.target.value } })}
                        >
                          <option value="zh-CN">简体中文</option>
                          <option value="en-US">English</option>
                          <option value="ja-JP">日本語</option>
                        </select>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div className="space-y-8">
                <div className="narrato-glass rounded-[3rem] overflow-hidden">
                  <div className="p-8 space-y-8">
                    <div className="flex items-center gap-4">
                      <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center">
                        <Eye className="w-5 h-5 text-primary" />
                      </div>
                      <h4 className="text-xl font-black tracking-tight">人称视角</h4>
                    </div>
                    <div className="space-y-4">
                      {[
                        { id: 'first', label: '第一人称', desc: '“我看到...”，代入感强' },
                        { id: 'third', label: '第三人称', desc: '“他/她...”，客观叙述' }
                      ].map((p) => (
                        <button
                          key={p.id}
                          onClick={() => send({ type: 'SET_CONFIG', config: { perspective: p.id as any } })}
                          className={cn(
                            "w-full p-6 rounded-2xl border text-left transition-all space-y-1",
                            context.config.perspective === p.id 
                              ? "border-primary bg-primary/5" 
                              : "border-white/5 bg-white/[0.02] hover:border-white/20"
                          )}
                        >
                          <div className="font-black text-lg">{p.label}</div>
                          <div className="text-xs text-muted-foreground opacity-70">{p.desc}</div>
                        </button>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="narrato-glass rounded-[3rem] overflow-hidden">
                  <div className="p-8 space-y-8">
                    <div className="flex items-center gap-4">
                      <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center">
                        <Sparkles className="w-5 h-5 text-primary" />
                      </div>
                      <h4 className="text-xl font-black tracking-tight">解说风格</h4>
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      {[
                        '默认风格', '口语叙述', '高能白话', '胡说八道', '直播带货', '新闻联播'
                      ].map((s) => (
                        <button
                          key={s}
                          onClick={() => send({ type: 'SET_CONFIG', config: { style: s } })}
                          className={cn(
                            "w-full p-4 rounded-xl border text-sm font-bold transition-all",
                            context.config.style === s 
                              ? "border-primary bg-primary/10 text-primary" 
                              : "border-white/5 bg-white/[0.02] hover:border-white/20"
                          )}
                        >
                          {s}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div className="fixed bottom-0 left-20 right-0 p-8 bg-black/80 backdrop-blur-2xl border-t border-white/5 z-[105]">
              <div className="max-w-7xl mx-auto flex justify-between items-center">
                <Button 
                  variant="ghost" 
                  onClick={() => send({ type: 'RESET' })}
                  className="text-muted-foreground hover:text-white font-bold"
                >
                  <ArrowLeft className="w-4 h-4 mr-2" />
                  放弃修改
                </Button>
                <div className="flex gap-4">
                  <Button 
                    variant="outline" 
                    onClick={() => send({ type: 'RESET' })}
                    className="border-white/10 hover:bg-white/5 rounded-2xl px-8 h-14 font-bold"
                  >
                    <RefreshCw className="w-4 h-4 mr-2" />
                    重新上传
                  </Button>
                  <Button 
                    onClick={startJob}
                    className="bg-primary text-black font-black px-12 h-14 rounded-2xl shadow-[0_0_40px_rgba(57,255,20,0.3)] text-lg"
                  >
                    开始生成文案
                    <ChevronRight className="w-6 h-6 ml-2" />
                  </Button>
                </div>
              </div>
            </div>
          </motion.div>
        );

      case state.matches('analyzing'):
      case state.matches('scripting'):
        return (
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="flex flex-col items-center justify-center min-h-[600px] gap-16"
          >
            <div className="relative">
              <div className="absolute inset-0 animate-pulse rounded-full bg-primary/20 scale-[2]" />
              <div className="relative w-48 h-48 rounded-[3rem] bg-primary flex items-center justify-center shadow-[0_0_80px_rgba(57,255,20,0.4)]">
                <Sparkles className="w-20 h-20 text-black animate-spin-slow" />
              </div>
            </div>
            <div className="text-center space-y-6">
              <h2 className="text-5xl font-black tracking-tighter">
                {state.matches('analyzing') ? '正在深度分析视频...' : '正在创作精彩文案...'}
              </h2>
              <p className="text-muted-foreground text-xl max-w-md mx-auto">
                {state.matches('analyzing') ? 'AI 正在理解每一帧画面，捕捉精彩瞬间' : '正在为您量身定制最具感染力的解说词'}
              </p>
            </div>
            <div className="w-full max-w-2xl space-y-6">
              <div className="h-4 bg-white/5 rounded-full overflow-hidden border border-white/5 p-1">
                <motion.div 
                  initial={{ width: "0%" }}
                  animate={{ width: "100%" }}
                  transition={{ duration: 10, repeat: Infinity }}
                  className="h-full bg-primary rounded-full shadow-[0_0_15px_rgba(57,255,20,0.5)]"
                />
              </div>
              <div className="flex justify-between text-xs font-black text-primary uppercase tracking-[0.4em]">
                <span>Neural Processing</span>
                <span className="animate-pulse">Thinking...</span>
              </div>
            </div>
          </motion.div>
        );

      case state.matches('editing'):
        return (
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            className="space-y-12"
          >
            <div className="flex justify-between items-end">
              <div className="space-y-4">
                <h2 className="text-5xl font-black tracking-tighter leading-none">
                  精修 <span className="text-primary">AI 文案</span>
                </h2>
                <p className="text-muted-foreground text-lg">
                  您可以对 AI 生成的文案进行微调，确保每一句都符合您的创作意图。
                </p>
              </div>
            </div>

            <StepIndicator />

            <div className="flex flex-col gap-12">
              <div className="space-y-8">
                <div className="narrato-glass rounded-[3rem] overflow-hidden">
                  <div className="aspect-video bg-black flex items-center justify-center relative group">
                    {context.videoUrl && (
                      <video 
                        src={context.videoUrl} 
                        className="w-full h-full object-contain" 
                        controls 
                      />
                    )}
                  </div>
                  <div className="p-10 space-y-8">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center">
                          <Video className="w-5 h-5 text-primary" />
                        </div>
                        <span className="font-black text-lg">素材预览</span>
                      </div>
                      <Badge variant="outline" className="border-primary/30 text-primary font-mono px-4 py-1">01:26:43</Badge>
                    </div>
                    <div className="grid grid-cols-2 gap-6">
                      <div className="bg-white/[0.03] p-6 rounded-2xl border border-white/5">
                        <div className="text-[10px] uppercase tracking-widest text-muted-foreground font-bold mb-1">Resolution</div>
                        <div className="font-black text-xl">1920x1080</div>
                      </div>
                      <div className="bg-white/[0.03] p-6 rounded-2xl border border-white/5">
                        <div className="text-[10px] uppercase tracking-widest text-muted-foreground font-bold mb-1">Frame Rate</div>
                        <div className="font-black text-xl">30 FPS</div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div className="space-y-8">
                <div className="narrato-glass rounded-[3rem] overflow-hidden">
                  <div className="p-10 border-b border-white/5 flex items-center justify-between">
                    <div className="flex items-center gap-4">
                      <div className="w-12 h-12 rounded-2xl bg-primary/10 flex items-center justify-center">
                        <Edit3 className="w-6 h-6 text-primary" />
                      </div>
                      <h4 className="text-2xl font-black tracking-tight">字幕编辑器</h4>
                    </div>
                    <div className="flex gap-3">
                      <Button variant="ghost" size="icon" onClick={copyScript} className="w-12 h-12 rounded-xl hover:bg-primary/10 hover:text-primary transition-all">
                        <Save className="w-6 h-6" />
                      </Button>
                      <Button variant="ghost" size="icon" className="w-12 h-12 rounded-xl hover:bg-destructive/10 hover:text-destructive transition-all">
                        <Trash2 className="w-6 h-6" />
                      </Button>
                    </div>
                  </div>
                  <div className="p-10">
                    <ScrollArea className="h-[600px] pr-6">
                      <div className="space-y-8">
                        <div className="flex gap-8 group">
                          <div className="w-32 pt-6">
                            <div className="bg-primary/10 text-primary font-black text-xs px-4 py-2 rounded-full border border-primary/20 text-center">
                              0.1s - 1.7s
                            </div>
                          </div>
                          <div className="flex-1">
                            <Textarea
                              value={context.script || ''}
                              onChange={(e) => send({ type: 'UPDATE_SCRIPT', script: e.target.value })}
                              className="min-h-[500px] bg-white/[0.03] border-white/5 rounded-3xl p-8 text-xl leading-relaxed focus-visible:ring-primary resize-none font-medium"
                            />
                          </div>
                        </div>
                      </div>
                    </ScrollArea>
                  </div>
                </div>
              </div>
            </div>

            <div className="fixed bottom-0 left-20 right-0 p-8 bg-black/80 backdrop-blur-2xl border-t border-white/5 z-[105]">
              <div className="max-w-7xl mx-auto flex justify-between items-center">
                <Button 
                  variant="ghost" 
                  onClick={() => send({ type: 'RESET' })}
                  className="text-muted-foreground hover:text-white font-bold"
                >
                  <ArrowLeft className="w-4 h-4 mr-2" />
                  返回重配
                </Button>
                <div className="flex gap-4">
                  <Button 
                    variant="outline" 
                    onClick={() => send({ type: 'RESET' })}
                    className="border-white/10 hover:bg-white/5 rounded-2xl px-8 h-14 font-bold"
                  >
                    <RefreshCw className="w-4 h-4 mr-2" />
                    重新生成
                  </Button>
                  <Button 
                    onClick={() => send({ type: 'START_AUDIO_GEN' })}
                    className="bg-primary text-black font-black px-12 h-14 rounded-2xl shadow-[0_0_40px_rgba(57,255,20,0.3)] text-lg"
                  >
                    下一步: 配置配音
                    <ChevronRight className="w-6 h-6 ml-2" />
                  </Button>
                </div>
              </div>
            </div>
          </motion.div>
        );

      case state.matches('generatingAudio'):
        return (
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="flex flex-col items-center justify-center min-h-[500px] gap-12"
          >
            <div className="relative">
              <div className="absolute inset-0 animate-ping rounded-full bg-primary/20" />
              <div className="relative w-32 h-32 rounded-full bg-primary flex items-center justify-center shadow-[0_0_50px_rgba(57,255,20,0.4)]">
                <Mic className="w-12 h-12 text-black animate-pulse" />
              </div>
            </div>
            <div className="text-center space-y-4">
              <h2 className="text-4xl font-black tracking-tight">正在合成专业配音...</h2>
              <p className="text-muted-foreground text-xl">正在为您匹配最佳音色并生成音频流</p>
            </div>
            <div className="w-full max-w-xl space-y-4">
              <Progress value={undefined} className="h-3 bg-white/5" />
              <div className="flex justify-between text-sm font-mono text-primary uppercase tracking-widest">
                <span>TTS Synthesis</span>
                <span className="animate-pulse">Generating...</span>
              </div>
            </div>
          </motion.div>
        );

      case state.matches('previewing'):
        return (
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="space-y-12"
          >
            <div className="flex justify-between items-end">
              <div className="space-y-4">
                <h2 className="text-5xl font-black tracking-tighter leading-none">
                  配音 <span className="text-primary">制作完成</span>
                </h2>
                <p className="text-muted-foreground text-lg">
                  管理脚本内容，生成配音音频，校准时间戳，并进行视频合成。
                </p>
              </div>
            </div>

            <StepIndicator />

            <div className="space-y-12">
              <div className="narrato-glass rounded-[3rem] overflow-hidden">
                <div className="p-10 border-b border-white/5 flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <div className="w-12 h-12 rounded-2xl bg-primary/10 flex items-center justify-center">
                      <Mic className="w-6 h-6 text-primary" />
                    </div>
                    <h4 className="text-2xl font-black tracking-tight">音色选择</h4>
                  </div>
                  <div className="flex items-center gap-2 bg-black/40 p-1.5 rounded-full border border-white/5">
                    <Button variant="ghost" className="rounded-full px-8 h-10 bg-primary text-black font-bold hover:bg-primary/90">Basic (免费)</Button>
                    <Button variant="ghost" className="rounded-full px-8 h-10 text-muted-foreground font-bold hover:text-white">Premium (收费)</Button>
                  </div>
                </div>
                <div className="p-10 space-y-12">
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                    {[
                      { name: '齐静春', type: 'Basic', active: true },
                      { name: '磁性男声', type: 'Basic' },
                      { name: '贾小军', type: 'Basic' },
                      { name: '麦克阿瑟', type: 'Basic' },
                      { name: '顾我电影解说', type: 'Basic' },
                      { name: '温柔女声', type: 'Basic' },
                      { name: '历史解说', type: 'Basic' },
                      { name: '纪录片解说', type: 'Basic' }
                    ].map((v) => (
                      <div
                        key={v.name}
                        className={cn(
                          "p-8 rounded-[2rem] border transition-all relative group cursor-pointer",
                          v.active 
                            ? "border-primary bg-primary/5 shadow-[0_0_30px_rgba(57,255,20,0.1)]" 
                            : "border-white/5 bg-white/[0.02] hover:border-white/20"
                        )}
                      >
                        <div className="space-y-4">
                          <div className="font-black text-xl">{v.name}</div>
                          <Badge variant="secondary" className="bg-primary/20 text-primary border-none font-bold px-3 py-1">
                            {v.type}
                          </Badge>
                        </div>
                        <div className="absolute bottom-8 right-8 w-12 h-12 rounded-2xl bg-primary flex items-center justify-center opacity-0 group-hover:opacity-100 transition-all transform translate-y-2 group-hover:translate-y-0 shadow-[0_0_20px_rgba(57,255,20,0.4)]">
                          <Play className="w-6 h-6 text-black fill-current" />
                        </div>
                      </div>
                    ))}
                  </div>

                  <div className="grid grid-cols-2 gap-16">
                    <div className="space-y-8">
                      <div className="flex justify-between items-center">
                        <div className="flex items-center gap-4">
                          <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center">
                            <Zap className="w-5 h-5 text-primary" />
                          </div>
                          <h4 className="text-xl font-black tracking-tight">语速控制</h4>
                        </div>
                        <span className="text-primary font-black text-2xl">1.0x</span>
                      </div>
                      <Slider defaultValue={[1]} max={2} step={0.1} className="py-4" />
                    </div>
                    <div className="space-y-8">
                      <div className="flex justify-between items-center">
                        <div className="flex items-center gap-4">
                          <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center">
                            <Volume2 className="w-5 h-5 text-primary" />
                          </div>
                          <h4 className="text-xl font-black tracking-tight">音量控制</h4>
                        </div>
                        <span className="text-primary font-black text-2xl">1.0x</span>
                      </div>
                      <Slider defaultValue={[1]} max={2} step={0.1} className="py-4" />
                    </div>
                  </div>
                </div>
              </div>

              <div className="narrato-glass rounded-[3rem] overflow-hidden">
                <div className="p-10 border-b border-white/5 flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <div className="w-12 h-12 rounded-2xl bg-primary/10 flex items-center justify-center">
                      <FileText className="w-6 h-6 text-primary" />
                    </div>
                    <h4 className="text-2xl font-black tracking-tight">配音脚本</h4>
                  </div>
                  <div className="flex gap-4">
                    <Button className="bg-primary text-black font-black rounded-2xl h-14 px-10 shadow-[0_0_30px_rgba(57,255,20,0.3)]">
                      <Zap className="w-5 h-5 mr-2" />
                      生成全部音频
                    </Button>
                    <Button variant="outline" className="border-white/10 rounded-2xl h-14 px-8 font-bold hover:bg-white/5">
                      <Save className="w-5 h-5 mr-2" />
                      保存脚本
                    </Button>
                  </div>
                </div>
                <div className="w-full overflow-x-auto">
                  <table className="w-full text-left border-collapse">
                    <thead>
                      <tr className="bg-white/[0.03]">
                        <th className="p-8 font-black text-muted-foreground uppercase tracking-widest text-xs">序号</th>
                        <th className="p-8 font-black text-muted-foreground uppercase tracking-widest text-xs">时间轴</th>
                        <th className="p-8 font-black text-muted-foreground uppercase tracking-widest text-xs">解说词预览</th>
                        <th className="p-8 font-black text-muted-foreground uppercase tracking-widest text-xs">状态</th>
                        <th className="p-8 font-black text-muted-foreground uppercase tracking-widest text-xs">操作</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr className="border-b border-white/5 hover:bg-white/[0.01] transition-colors group">
                        <td className="p-8 font-black text-lg">01</td>
                        <td className="p-8">
                          <Badge variant="secondary" className="bg-primary/10 text-primary border-none font-mono font-bold px-4 py-1">
                            0.00s - 5.00s
                          </Badge>
                        </td>
                        <td className="p-8 text-muted-foreground font-medium italic">
                          {context.script?.slice(0, 60)}...
                        </td>
                        <td className="p-8">
                          <div className="flex items-center gap-2 text-primary font-bold">
                            <div className="w-2 h-2 rounded-full bg-primary animate-pulse" />
                            已就绪
                          </div>
                        </td>
                        <td className="p-8">
                          <div className="flex gap-3">
                            <Button variant="ghost" size="icon" className="w-10 h-10 rounded-xl hover:bg-primary/10 hover:text-primary"><RefreshCw className="w-5 h-5" /></Button>
                            <Button variant="ghost" size="icon" className="w-10 h-10 rounded-xl hover:bg-destructive/10 hover:text-destructive"><Trash2 className="w-5 h-5" /></Button>
                          </div>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            </div>

            <div className="fixed bottom-0 left-20 right-0 p-8 bg-black/80 backdrop-blur-2xl border-t border-white/5 z-[105]">
              <div className="max-w-7xl mx-auto flex justify-between items-center">
                <Button 
                  variant="ghost" 
                  onClick={() => send({ type: 'RESET' })}
                  className="text-muted-foreground hover:text-white font-bold"
                >
                  <ArrowLeft className="w-4 h-4 mr-2" />
                  返回编辑
                </Button>
                <div className="flex gap-4">
                  <Button 
                    variant="outline" 
                    onClick={downloadAudio}
                    className="border-white/10 hover:bg-white/5 rounded-2xl px-8 h-14 font-bold"
                  >
                    <Download className="w-4 h-4 mr-2" />
                    导出配音
                  </Button>
                  <Button 
                    onClick={() => send({ type: 'RESET' })}
                    className="bg-primary text-black font-black px-12 h-14 rounded-2xl shadow-[0_0_40px_rgba(57,255,20,0.3)] text-lg"
                  >
                    开始视频合成
                    <ChevronRight className="w-6 h-6 ml-2" />
                  </Button>
                </div>
              </div>
            </div>
          </motion.div>
        );

      case state.matches('error'):
        return (
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            className="flex flex-col items-center justify-center min-h-[600px] gap-12 text-center"
          >
            <div className="relative">
              <div className="absolute inset-0 animate-pulse rounded-full bg-destructive/20 scale-150" />
              <div className="relative w-32 h-32 rounded-[2rem] bg-destructive flex items-center justify-center shadow-[0_0_50px_rgba(239,68,68,0.3)]">
                <AlertCircle className="w-16 h-16 text-white" />
              </div>
            </div>
            <div className="space-y-6">
              <h2 className="text-5xl font-black tracking-tighter">处理过程中出现错误</h2>
              <p className="text-muted-foreground text-xl max-w-xl mx-auto leading-relaxed">
                {context.error || '发生未知错误，请检查您的网络连接或 API 密钥配置。'}
              </p>
            </div>
            <Button 
              onClick={() => send({ type: 'RESET' })} 
              className="bg-primary text-black font-black rounded-2xl px-16 h-16 text-xl shadow-[0_0_30px_rgba(57,255,20,0.3)]"
            >
              重新开始
            </Button>
          </motion.div>
        );

      default:
        return null;
    }
  };

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-white selection:bg-primary/30 font-sans">
      <Toaster theme="dark" position="top-center" />
      
      {/* Sidebar Navigation */}
      <aside className="fixed left-0 top-0 bottom-0 w-20 bg-[#0d0d0d] border-r border-white/5 flex flex-col items-center py-8 z-[110]">
        <div className="w-12 h-12 rounded-2xl bg-primary flex items-center justify-center shadow-[0_0_30px_rgba(57,255,20,0.2)] mb-12 cursor-pointer" onClick={() => send({ type: 'RESET' })}>
          <Mic className="w-7 h-7 text-black fill-current" />
        </div>
        
        <nav className="flex flex-col gap-6">
          {[
            { icon: Video, label: '素材', active: state.matches('idle') || state.matches('uploading') },
            { icon: Settings, label: '配置', active: state.matches('configuring') },
            { icon: FileText, label: '文案', active: state.matches('analyzing') || state.matches('scripting') || state.matches('editing') },
            { icon: Mic, label: '配音', active: state.matches('generatingAudio') || state.matches('previewing') },
          ].map((item, i) => (
            <div key={i} className="flex flex-col items-center gap-1 group cursor-pointer">
              <div className={cn(
                "w-12 h-12 rounded-xl flex items-center justify-center transition-all",
                item.active ? "bg-primary/10 text-primary" : "text-muted-foreground hover:bg-white/5 hover:text-white"
              )}>
                <item.icon className="w-6 h-6" />
              </div>
              <span className={cn("text-[10px] font-bold", item.active ? "text-primary" : "text-muted-foreground")}>{item.label}</span>
            </div>
          ))}
        </nav>

        <div className="mt-auto flex flex-col gap-6">
          <div className="w-12 h-12 rounded-xl flex items-center justify-center text-muted-foreground hover:bg-white/5 hover:text-white cursor-pointer">
            <Bell className="w-6 h-6" />
          </div>
          <div className="w-10 h-10 rounded-full bg-primary flex items-center justify-center text-black font-black shadow-[0_0_20px_rgba(57,255,20,0.2)] cursor-pointer">
            H
          </div>
        </div>
      </aside>

      {/* Header */}
      <header className="fixed top-0 left-20 right-0 h-20 border-b border-white/5 bg-black/50 backdrop-blur-xl z-[100] px-8 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <h1 className="text-xl font-black tracking-tight">
            {state.matches('idle') ? '新建项目' : context.videoFile?.name || '未命名项目'}
          </h1>
          <Badge variant="outline" className="border-primary/30 text-primary bg-primary/5">V1.0 Beta</Badge>
          {workspace && (
            <div className="flex items-center gap-2 text-[10px] text-muted-foreground font-mono bg-white/5 px-3 py-1 rounded-full">
              <Clock className="w-3 h-3" />
              {workspace.storage}
            </div>
          )}
        </div>
        
        <div className="flex items-center gap-4">
          <Button variant="ghost" className="text-muted-foreground hover:text-white">教程</Button>
          <Button variant="ghost" className="text-muted-foreground hover:text-white">反馈</Button>
          <Button className="bg-primary text-black font-bold rounded-full px-6 h-10 shadow-[0_0_20px_rgba(57,255,20,0.2)]">
            升级专业版
          </Button>
        </div>
      </header>

      {/* Main Content */}
      <main className="pl-20 pt-20 min-h-screen">
        <div className="max-w-7xl mx-auto p-12">
          <AnimatePresence mode="wait">
            <div key={state.value as string}>
              {renderState()}
            </div>
          </AnimatePresence>
        </div>
      </main>
    </div>
  );
}
