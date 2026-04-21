import { useState } from 'react';
import { X, Film, Scissors, Clapperboard } from 'lucide-react';
import { Button } from '@/components/ui/button';

type ProjectType = 'movie_review' | 'drama_mix' | 'drama_review';

interface CreateProjectModalProps {
  open: boolean;
  onClose: () => void;
  onCreate: (name: string, type: ProjectType) => void;
}

const projectTypes: {
  key: ProjectType;
  icon: React.ReactNode;
  label: string;
  desc: string;
}[] = [
  {
    key: 'movie_review',
    icon: <Film className="w-5 h-5" />,
    label: '影视解说',
    desc: '自动分析影视内容，生成解说脚本与配音',
  },
  {
    key: 'drama_mix',
    icon: <Scissors className="w-5 h-5" />,
    label: '短剧混剪',
    desc: '智能剪辑短剧片段，自动拼接精彩画面',
  },
  {
    key: 'drama_review',
    icon: <Clapperboard className="w-5 h-5" />,
    label: '短剧解说',
    desc: '短剧内容深度解说，自动生成叙事脚本',
  },
];

export default function CreateProjectModal({ open, onClose, onCreate }: CreateProjectModalProps) {
  const [projectName, setProjectName] = useState('');
  const [projectType, setProjectType] = useState<ProjectType>('movie_review');

  if (!open) return null;

  const handleCreate = () => {
    if (projectName.trim()) {
      onCreate(projectName.trim(), projectType);
      setProjectName('');
      setProjectType('movie_review');
    }
  };

  const handleClose = () => {
    setProjectName('');
    setProjectType('movie_review');
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={handleClose} />
      <div className="relative w-full max-w-md bg-[#0B0B12] border border-white/[0.08] rounded-2xl shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/[0.06]">
          <h2 className="text-lg font-semibold text-white">创建新项目</h2>
          <button
            onClick={handleClose}
            className="text-slate-400 hover:text-white transition-colors p-1 rounded-lg hover:bg-white/[0.05]"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="px-6 py-5 space-y-5">
          {/* Project Name */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              项目名称 <span className="text-indigo-400">*</span>
            </label>
            <input
              type="text"
              value={projectName}
              onChange={(e) => setProjectName(e.target.value)}
              placeholder="输入项目名称"
              className="w-full px-4 py-2.5 rounded-xl bg-white/[0.04] border border-white/[0.08] text-white placeholder-slate-500 text-sm focus:outline-none focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/20 transition-all"
            />
          </div>

          {/* Project Type */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-3">创作模式</label>
            <div className="space-y-2">
              {projectTypes.map((type) => {
                const isSelected = projectType === type.key;
                return (
                  <button
                    key={type.key}
                    onClick={() => setProjectType(type.key)}
                    className={`w-full flex items-center gap-3 p-3 rounded-xl border text-left transition-all duration-200 ${
                      isSelected
                        ? 'bg-indigo-500/10 border-indigo-500/50'
                        : 'bg-white/[0.02] border-white/[0.06] hover:border-white/[0.12]'
                    }`}
                  >
                    <div className={`shrink-0 ${isSelected ? 'text-indigo-400' : 'text-slate-400'}`}>
                      {type.icon}
                    </div>
                    <div className="flex-1 min-w-0">
                      <h4 className={`text-sm font-medium ${isSelected ? 'text-white' : 'text-slate-300'}`}>
                        {type.label}
                      </h4>
                      <p className="text-xs text-slate-500 truncate">{type.desc}</p>
                    </div>
                    <div
                      className={`w-4 h-4 rounded-full border-2 flex items-center justify-center shrink-0 ${
                        isSelected ? 'border-indigo-500' : 'border-slate-600'
                      }`}
                    >
                      {isSelected && <div className="w-2 h-2 rounded-full bg-indigo-500" />}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-white/[0.06] flex items-center justify-end gap-3">
          <Button
            variant="ghost"
            size="sm"
            onClick={handleClose}
            className="text-slate-400 hover:text-white"
          >
            取消
          </Button>
          <Button
            size="sm"
            onClick={handleCreate}
            disabled={!projectName.trim()}
            className="gradient-bg hover:brightness-110 text-white rounded-lg disabled:opacity-40"
          >
            创建
          </Button>
        </div>
      </div>
    </div>
  );
}