import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useOutletContext, useParams } from 'react-router-dom';
import {
  ArrowDown,
  ArrowRight,
  ArrowUp,
  Copy,
  Download,
  Plus,
  RefreshCcw,
  Sparkles,
  Trash2,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Checkbox } from '@/components/ui/checkbox';
import {
  type Project,
  type ScriptItem,
  updateProject,
} from '@/lib/projects-store';
import { cn } from '@/lib/utils';
import { toast } from 'sonner';

type Ctx = { project?: Project };

function newItem(): ScriptItem {
  return {
    id: `s-${Date.now()}`,
    startTime: '00:00:00,000',
    endTime: '00:00:05,000',
    originalSubtitle: '',
    narration: '',
  };
}

export default function AnalysisPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { project } = useOutletContext<Ctx>();
  const [items, setItems] = useState<ScriptItem[]>(project?.scriptItems ?? []);
  const [selected, setSelected] = useState<Record<string, boolean>>({});

  useEffect(() => {
    setItems(project?.scriptItems ?? []);
  }, [project?.id, project?.scriptItems]);

  const stats = useMemo(() => {
    const total = items.length;
    const narrated = items.filter((i) => i.narration.trim().length > 0).length;
    return { total, narrated };
  }, [items]);

  if (!id || !project) {
    return (
      <div className="container-page py-20 text-center text-white/60">
        项目不存在。
      </div>
    );
  }

  const persist = (next: ScriptItem[]) => {
    setItems(next);
    updateProject(id, { scriptItems: next });
  };

  const add = () => persist([...items, newItem()]);
  const remove = (rowId: string) => persist(items.filter((x) => x.id !== rowId));
  const patch = (rowId: string, patchObj: Partial<ScriptItem>) =>
    persist(items.map((x) => (x.id === rowId ? { ...x, ...patchObj } : x)));

  const copyRow = (rowId: string) => {
    const idx = items.findIndex((x) => x.id === rowId);
    if (idx === -1) return;
    const clone: ScriptItem = { ...items[idx], id: `s-${Date.now()}` };
    const next = [...items];
    next.splice(idx + 1, 0, clone);
    persist(next);
  };

  const moveRow = (rowId: string, dir: -1 | 1) => {
    const idx = items.findIndex((x) => x.id === rowId);
    const target = idx + dir;
    if (idx === -1 || target < 0 || target >= items.length) return;
    const next = [...items];
    [next[idx], next[target]] = [next[target], next[idx]];
    persist(next);
  };

  const exportJson = () => {
    const payload = items.map((s, i) => ({
      序号: i + 1,
      开始时间: s.startTime,
      结束时间: s.endTime,
      原始字幕: s.originalSubtitle,
      解说词: s.narration,
    }));
    const blob = new Blob([JSON.stringify(payload, null, 2)], {
      type: 'application/json',
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${project.name || 'script'}.json`;
    a.click();
    URL.revokeObjectURL(url);
    toast.success('脚本已导出');
  };

  const regenerate = () => {
    navigate(`/projects/${id}/material`);
  };

  const next = () => {
    navigate(`/projects/${id}/dubbing`);
  };

  return (
    <div className="container-page py-8">
      <header className="flex items-start justify-between mb-6 flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold">剪辑脚本编辑</h1>
          <p className="text-sm text-white/55 mt-1">项目：{project.name}</p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <Button
            size="sm"
            variant="outline"
            onClick={exportJson}
            className="border-white/15 bg-transparent text-white hover:bg-white/5"
          >
            <Download className="w-4 h-4 mr-1" /> 导出
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={regenerate}
            className="border-white/15 bg-transparent text-white hover:bg-white/5"
          >
            <RefreshCcw className="w-4 h-4 mr-1" /> 重新生成
          </Button>
          <Button
            size="sm"
            onClick={next}
            disabled={items.length === 0}
            className="bg-[#46ec13] hover:bg-[#37c00c] text-[#060a07] font-semibold disabled:opacity-40 disabled:pointer-events-none"
          >
            下一步 <ArrowRight className="w-4 h-4 ml-1" />
          </Button>
        </div>
      </header>

      <section className="rounded-2xl border border-white/[0.06] bg-white/[0.02]">
        <div className="flex items-center justify-between px-5 py-4 border-b border-white/5 flex-wrap gap-3">
          <div className="flex items-center gap-3">
            <h3 className="font-semibold">剪辑脚本</h3>
            <div className="text-xs text-white/50 flex items-center gap-2">
              <span>共 {stats.total} 项</span>
              {stats.total > 0 ? (
                <>
                  <span className="text-white/20">|</span>
                  <span className="text-[#46ec13]">已填解说 {stats.narrated}</span>
                </>
              ) : null}
            </div>
          </div>
          <Button
            size="sm"
            onClick={add}
            variant="ghost"
            className="text-white/70 hover:text-white hover:bg-white/5"
          >
            <Plus className="w-4 h-4 mr-1" /> 添加
          </Button>
        </div>

        {items.length === 0 ? (
          <div className="py-16 flex flex-col items-center justify-center gap-4 text-sm">
            <div
              className="w-14 h-14 rounded-full flex items-center justify-center"
              style={{ background: 'rgba(70,236,19,0.12)', color: '#46ec13' }}
            >
              <Sparkles className="w-6 h-6" />
            </div>
            <div className="font-semibold">还没有脚本数据</div>
            <p className="text-white/50 max-w-md text-center">
              点击「重新生成」返回素材页面重新生成 AI 脚本，或点击下方按钮手动添加第一项。
            </p>
            <div className="flex gap-2">
              <Button
                size="sm"
                onClick={add}
                variant="outline"
                className="border-white/15 bg-transparent text-white hover:bg-white/5"
              >
                <Plus className="w-4 h-4 mr-1" /> 添加第一项
              </Button>
              <Button
                size="sm"
                onClick={regenerate}
                className="bg-[#46ec13] hover:bg-[#37c00c] text-[#060a07] font-semibold"
              >
                <RefreshCcw className="w-4 h-4 mr-1" /> 重新生成
              </Button>
            </div>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm min-w-[1000px]">
              <thead className="bg-white/[0.03] text-white/55 text-left">
                <tr>
                  <th className="px-4 py-3 font-normal w-10">
                    <Checkbox
                      checked={items.length > 0 && items.every((i) => selected[i.id])}
                      onCheckedChange={(v) => {
                        const nextSel: Record<string, boolean> = {};
                        if (v) items.forEach((i) => (nextSel[i.id] = true));
                        setSelected(nextSel);
                      }}
                    />
                  </th>
                  <th className="px-3 py-3 font-normal w-12">序号</th>
                  <th className="px-3 py-3 font-normal w-32">开始时间</th>
                  <th className="px-3 py-3 font-normal w-32">结束时间</th>
                  <th className="px-3 py-3 font-normal">原始字幕</th>
                  <th className="px-3 py-3 font-normal">解说词</th>
                  <th className="px-3 py-3 font-normal w-32 text-right">操作</th>
                </tr>
              </thead>
              <tbody>
                {items.map((row, idx) => (
                  <tr key={row.id} className="border-t border-white/5 align-top">
                    <td className="px-4 py-3">
                      <Checkbox
                        checked={!!selected[row.id]}
                        onCheckedChange={(v) =>
                          setSelected((s) => ({ ...s, [row.id]: Boolean(v) }))
                        }
                      />
                    </td>
                    <td className="px-3 py-3 text-white/70">{idx + 1}</td>
                    <td className="px-3 py-3">
                      <Input
                        value={row.startTime}
                        onChange={(e) => patch(row.id, { startTime: e.target.value })}
                        className="bg-[#0f1611] border-white/10 h-8 text-xs font-mono"
                      />
                    </td>
                    <td className="px-3 py-3">
                      <Input
                        value={row.endTime}
                        onChange={(e) => patch(row.id, { endTime: e.target.value })}
                        className="bg-[#0f1611] border-white/10 h-8 text-xs font-mono"
                      />
                    </td>
                    <td className="px-3 py-3">
                      <Input
                        value={row.originalSubtitle}
                        onChange={(e) => patch(row.id, { originalSubtitle: e.target.value })}
                        placeholder="（可留空）"
                        className="bg-[#0f1611] border-white/10 h-8 text-xs"
                      />
                    </td>
                    <td className="px-3 py-3">
                      <Input
                        value={row.narration}
                        onChange={(e) => patch(row.id, { narration: e.target.value })}
                        placeholder="新解说词"
                        className="bg-[#0f1611] border-white/10 h-8 text-xs"
                      />
                    </td>
                    <td className="px-3 py-3">
                      <div className="flex items-center justify-end gap-1">
                        <RowIcon title="复制行" onClick={() => copyRow(row.id)}>
                          <Copy className="w-3.5 h-3.5" />
                        </RowIcon>
                        <RowIcon
                          title="上移"
                          disabled={idx === 0}
                          onClick={() => moveRow(row.id, -1)}
                        >
                          <ArrowUp className="w-3.5 h-3.5" />
                        </RowIcon>
                        <RowIcon
                          title="下移"
                          disabled={idx === items.length - 1}
                          onClick={() => moveRow(row.id, 1)}
                        >
                          <ArrowDown className="w-3.5 h-3.5" />
                        </RowIcon>
                        <RowIcon
                          title="删除"
                          danger
                          onClick={() => remove(row.id)}
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </RowIcon>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

function RowIcon({
  onClick,
  title,
  disabled,
  danger,
  children,
}: {
  onClick: () => void;
  title: string;
  disabled?: boolean;
  danger?: boolean;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      title={title}
      className={cn(
        'w-7 h-7 rounded-md flex items-center justify-center transition',
        disabled
          ? 'text-white/20 cursor-not-allowed'
          : danger
            ? 'text-white/55 hover:text-red-400 hover:bg-white/5'
            : 'text-white/55 hover:text-white hover:bg-white/5'
      )}
    >
      {children}
    </button>
  );
}
