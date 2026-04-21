import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  LayoutGrid,
  Plus,
  Search,
  Table as TableIcon,
  Trash2,
  Edit3,
  MoreVertical,
} from 'lucide-react';
import { AppLayout } from '@/components/layout/AppLayout';
import { RequireAuth } from '@/components/layout/RequireAuth';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import {
  createProject,
  deleteProject,
  listProjects,
  seedSampleProjectsIfEmpty,
  type Project,
  type ProjectStatus,
} from '@/lib/projects-store';
import { cn } from '@/lib/utils';
import { formatDate, formatDistanceToNow } from '@/lib/time';
import { toast } from 'sonner';

const STATUS_TABS: { key: 'all' | ProjectStatus; label: string }[] = [
  { key: 'all', label: '全部' },
  { key: 'draft', label: '草稿' },
  { key: 'completed', label: '已完成' },
  { key: 'exported', label: '已导出' },
];

const STATUS_LABEL: Record<ProjectStatus, string> = {
  draft: '草稿',
  completed: '已完成',
  exported: '已导出',
};

const STATUS_COLOR: Record<ProjectStatus, string> = {
  draft: 'text-yellow-300 bg-yellow-300/10 border-yellow-300/20',
  completed: 'text-[#46ec13] bg-[#46ec13]/12 border-[#46ec13]/30',
  exported: 'text-indigo-300 bg-indigo-300/10 border-indigo-300/20',
};

type SortKey = 'updated_at' | 'name' | 'status';

function ProjectsInner() {
  const navigate = useNavigate();
  const [projects, setProjects] = useState<Project[]>([]);
  const [query, setQuery] = useState('');
  const [tab, setTab] = useState<'all' | ProjectStatus>('all');
  const [sortKey, setSortKey] = useState<SortKey>('updated_at');
  const [view, setView] = useState<'card' | 'table'>('card');
  const [createOpen, setCreateOpen] = useState(false);
  const [newName, setNewName] = useState('');

  const reload = () => setProjects(listProjects());

  useEffect(() => {
    seedSampleProjectsIfEmpty();
    reload();
    const onChange = () => reload();
    window.addEventListener('aivideogpt:projects', onChange);
    return () => window.removeEventListener('aivideogpt:projects', onChange);
  }, []);

  const filtered = useMemo(() => {
    let list = projects.slice();
    if (tab !== 'all') list = list.filter((p) => p.status === tab);
    const q = query.trim().toLowerCase();
    if (q) list = list.filter((p) => p.name.toLowerCase().includes(q));
    list.sort((a, b) => {
      if (sortKey === 'name') return a.name.localeCompare(b.name, 'zh');
      if (sortKey === 'status') return a.status.localeCompare(b.status);
      return b.updatedAt.localeCompare(a.updatedAt);
    });
    return list;
  }, [projects, query, tab, sortKey]);

  const handleCreate = () => {
    if (!newName.trim()) {
      toast.error('请输入项目名称');
      return;
    }
    const p = createProject(newName);
    setCreateOpen(false);
    setNewName('');
    navigate(`/projects/${p.id}/material`);
  };

  const handleDelete = (id: string) => {
    if (!window.confirm('确定删除该项目？')) return;
    deleteProject(id);
    toast.success('项目已删除');
  };

  return (
    <AppLayout>
      <div className="container-page py-10">
        <header className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-3xl font-bold">我的项目</h1>
            <p className="text-sm text-white/55 mt-1">管理你创建的所有视频项目</p>
          </div>
          <Button
            onClick={() => setCreateOpen(true)}
            className="bg-[#46ec13] hover:bg-[#37c00c] text-[#060a07] font-semibold rounded-lg"
          >
            <Plus className="w-4 h-4 mr-1" /> 新建项目
          </Button>
        </header>

        <div className="flex flex-col lg:flex-row gap-3 mb-4">
          <div className="relative flex-1">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-white/40" />
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="搜索项目..."
              className="pl-9 bg-[#0c120e] border-white/10 focus-visible:ring-[#46ec13]/30"
            />
          </div>
          <div className="flex items-center gap-2">
            <div className="inline-flex items-center rounded-lg border border-white/10 bg-white/[0.03] p-1">
              <button
                type="button"
                onClick={() => setView('card')}
                title="卡片视图"
                className={cn(
                  'px-2.5 py-1.5 rounded-md',
                  view === 'card'
                    ? 'bg-[#46ec13] text-[#060a07]'
                    : 'text-white/60 hover:text-white'
                )}
              >
                <LayoutGrid className="w-4 h-4" />
              </button>
              <button
                type="button"
                onClick={() => setView('table')}
                title="表格视图"
                className={cn(
                  'px-2.5 py-1.5 rounded-md',
                  view === 'table'
                    ? 'bg-[#46ec13] text-[#060a07]'
                    : 'text-white/60 hover:text-white'
                )}
              >
                <TableIcon className="w-4 h-4" />
              </button>
            </div>
            <Select value={sortKey} onValueChange={(v) => setSortKey(v as SortKey)}>
              <SelectTrigger className="w-40 bg-[#0c120e] border-white/10">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="bg-[#0b110d] border-white/10 text-white">
                <SelectItem value="updated_at">按日期排序</SelectItem>
                <SelectItem value="name">按名称排序</SelectItem>
                <SelectItem value="status">按状态排序</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        <nav className="flex items-center gap-5 border-b border-white/5 mb-6">
          {STATUS_TABS.map((t) => (
            <button
              key={t.key}
              type="button"
              onClick={() => setTab(t.key)}
              className={cn(
                'relative pb-3 text-sm transition',
                tab === t.key ? 'text-[#46ec13]' : 'text-white/60 hover:text-white'
              )}
            >
              {t.label}
              {tab === t.key ? (
                <span className="absolute left-0 right-0 -bottom-px h-0.5 bg-[#46ec13] rounded" />
              ) : null}
            </button>
          ))}
        </nav>

        {filtered.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-white/10 p-16 text-center text-white/50">
            没有找到匹配的项目。
          </div>
        ) : view === 'card' ? (
          <div className="grid gap-5 md:grid-cols-2 lg:grid-cols-3">
            {filtered.map((p) => (
              <div
                key={p.id}
                className="group rounded-2xl overflow-hidden bg-white/[0.03] border border-white/[0.06] hover:border-[#46ec13]/40 transition"
              >
                <Link
                  to={`/projects/${p.id}/material`}
                  className="block relative aspect-[16/9] bg-white/[0.04] flex items-center justify-center overflow-hidden"
                >
                  {p.thumbnailUrl ? (
                    <img
                      src={p.thumbnailUrl}
                      alt={p.name}
                      className="w-full h-full object-cover group-hover:scale-105 transition"
                      loading="lazy"
                    />
                  ) : (
                    <div className="flex flex-col items-center gap-2 text-white/45">
                      <Edit3 className="w-6 h-6" />
                      <span className="text-xs">草稿</span>
                    </div>
                  )}
                  <span
                    className={cn(
                      'absolute top-3 right-3 text-[11px] px-2 py-0.5 rounded-md border backdrop-blur',
                      STATUS_COLOR[p.status]
                    )}
                  >
                    {STATUS_LABEL[p.status]}
                  </span>
                </Link>
                <div className="p-4">
                  <div className="flex items-start justify-between gap-2">
                    <Link to={`/projects/${p.id}/material`} className="font-semibold text-sm hover:text-[#46ec13]">
                      {p.name}
                    </Link>
                    <button
                      type="button"
                      onClick={() => handleDelete(p.id)}
                      className="text-white/40 hover:text-red-400"
                      title="删除"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                  <div className="text-xs text-white/45 mt-1">
                    {formatDistanceToNow(p.updatedAt)}最后编辑 · {formatDate(p.updatedAt)}
                  </div>
                  <div className="mt-3 flex items-center justify-between text-xs">
                    <Link
                      to={`/projects/${p.id}/material`}
                      className="text-[#46ec13] hover:underline"
                    >
                      编辑项目
                    </Link>
                    <span className="text-white/40">{STATUS_LABEL[p.status]}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="rounded-2xl border border-white/[0.06] overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-white/[0.03] text-white/60">
                <tr>
                  <th className="text-left px-4 py-3 font-normal">项目名称</th>
                  <th className="text-left px-4 py-3 font-normal">状态</th>
                  <th className="text-left px-4 py-3 font-normal">最后编辑</th>
                  <th className="text-left px-4 py-3 font-normal">创建时间</th>
                  <th className="text-right px-4 py-3 font-normal">操作</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((p) => (
                  <tr key={p.id} className="border-t border-white/5 hover:bg-white/[0.02]">
                    <td className="px-4 py-3">
                      <Link to={`/projects/${p.id}/material`} className="font-medium hover:text-[#46ec13]">
                        {p.name}
                      </Link>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={cn(
                          'text-[11px] px-2 py-0.5 rounded-md border',
                          STATUS_COLOR[p.status]
                        )}
                      >
                        {STATUS_LABEL[p.status]}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-white/55">{formatDistanceToNow(p.updatedAt)}前</td>
                    <td className="px-4 py-3 text-white/55">{formatDate(p.createdAt)}</td>
                    <td className="px-4 py-3 text-right">
                      <Link
                        to={`/projects/${p.id}/material`}
                        className="text-[#46ec13] hover:underline mr-4"
                      >
                        编辑
                      </Link>
                      <button
                        type="button"
                        onClick={() => handleDelete(p.id)}
                        className="text-white/50 hover:text-red-400"
                      >
                        <MoreVertical className="w-4 h-4 inline" /> 删除
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="bg-[#0b110d] border-white/10 text-white">
          <DialogHeader>
            <DialogTitle>新建项目</DialogTitle>
            <DialogDescription className="text-white/55">
              为你的新视频项目起一个名称，稍后可以在编辑页面上传视频素材。
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            <Label htmlFor="newname" className="text-xs text-white/70">项目名称</Label>
            <Input
              id="newname"
              autoFocus
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="例如：大明王朝开场解说"
              className="bg-[#0f1611] border-white/10 focus-visible:ring-[#46ec13]/30"
            />
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setCreateOpen(false)}>
              取消
            </Button>
            <Button
              onClick={handleCreate}
              className="bg-[#46ec13] hover:bg-[#37c00c] text-[#060a07] font-semibold"
            >
              创建并进入编辑
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </AppLayout>
  );
}

export default function Projects() {
  return (
    <RequireAuth>
      <ProjectsInner />
    </RequireAuth>
  );
}
