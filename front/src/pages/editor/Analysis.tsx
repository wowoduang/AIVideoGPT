import { useEffect, useState } from 'react';
import { useNavigate, useOutletContext, useParams } from 'react-router-dom';
import { ArrowLeft, Plus, RefreshCcw, Sparkles, Trash2, Wand2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Checkbox } from '@/components/ui/checkbox';
import {
  type Project,
  type ScriptItem,
  updateProject,
} from '@/lib/projects-store';
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

  if (!id || !project) {
    return (
      <div className="container-page py-20 text-center text-white/60">项目不存在。</div>
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
  const removeSelected = () => {
    const ids = Object.entries(selected).filter(([, v]) => v).map(([k]) => k);
    if (ids.length === 0) {
      toast.error('请先选择要删除的行');
      return;
    }
    persist(items.filter((x) => !ids.includes(x.id)));
    setSelected({});
  };

  const regenerate = () => {
    navigate(`/projects/${id}/material`);
  };

  return (
    <div className="container-page py-8">
      <header className="flex items-start justify-between mb-6 flex-wrap gap-4">
        <div>
          <h2 className="text-2xl font-bold">剪辑脚本编辑</h2>
          <p className="text-sm text-white/55 mt-1">项目：{project.name}</p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            onClick={regenerate}
            className="border-white/15 bg-transparent text-white hover:bg-white/5"
          >
            <RefreshCcw className="w-4 h-4 mr-1" /> 重新生成
          </Button>
        </div>
      </header>

      <section className="rounded-2xl border border-white/[0.06] bg-white/[0.02]">
        <div className="flex items-center justify-between px-5 py-4 border-b border-white/5">
          <div className="flex items-center gap-3">
            <h3 className="font-semibold">剪辑脚本</h3>
            <span className="text-xs text-white/45">共 {items.length} 项</span>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={removeSelected}
              className="text-white/60 hover:text-red-400"
            >
              <Trash2 className="w-4 h-4 mr-1" /> 批量删除
            </Button>
            <Button size="sm" onClick={add} className="bg-[#46ec13] hover:bg-[#37c00c] text-[#060a07] font-semibold">
              <Plus className="w-4 h-4 mr-1" /> 添加
            </Button>
          </div>
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
              点击"重新生成"按钮返回素材页面，重新生成 AI 脚本；或手动点击下方按钮添加第一项。
            </p>
            <div className="flex gap-2">
              <Button size="sm" onClick={add} variant="outline" className="border-white/15 bg-transparent text-white hover:bg-white/5">
                <Plus className="w-4 h-4 mr-1" /> 添加第一项
              </Button>
              <Button size="sm" onClick={regenerate} className="bg-indigo-500 hover:bg-indigo-600 text-white">
                <Wand2 className="w-4 h-4 mr-1" /> 重新生成
              </Button>
            </div>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm min-w-[960px]">
              <thead className="bg-white/[0.03] text-white/55 text-left">
                <tr>
                  <th className="px-4 py-3 font-normal w-10">
                    <Checkbox
                      checked={items.length > 0 && items.every((i) => selected[i.id])}
                      onCheckedChange={(v) => {
                        const next: Record<string, boolean> = {};
                        if (v) items.forEach((i) => (next[i.id] = true));
                        setSelected(next);
                      }}
                    />
                  </th>
                  <th className="px-4 py-3 font-normal w-12">序号</th>
                  <th className="px-4 py-3 font-normal w-40">开始时间</th>
                  <th className="px-4 py-3 font-normal w-40">结束时间</th>
                  <th className="px-4 py-3 font-normal">原始字幕</th>
                  <th className="px-4 py-3 font-normal">解说词</th>
                  <th className="px-4 py-3 font-normal w-20 text-right">操作</th>
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
                    <td className="px-4 py-3 text-white/70">{idx + 1}</td>
                    <td className="px-4 py-3">
                      <Input
                        value={row.startTime}
                        onChange={(e) => patch(row.id, { startTime: e.target.value })}
                        className="bg-[#0f1611] border-white/10 h-8 text-xs font-mono"
                      />
                    </td>
                    <td className="px-4 py-3">
                      <Input
                        value={row.endTime}
                        onChange={(e) => patch(row.id, { endTime: e.target.value })}
                        className="bg-[#0f1611] border-white/10 h-8 text-xs font-mono"
                      />
                    </td>
                    <td className="px-4 py-3">
                      <Textarea
                        value={row.originalSubtitle}
                        onChange={(e) => patch(row.id, { originalSubtitle: e.target.value })}
                        rows={2}
                        className="bg-[#0f1611] border-white/10"
                      />
                    </td>
                    <td className="px-4 py-3">
                      <Textarea
                        value={row.narration}
                        onChange={(e) => patch(row.id, { narration: e.target.value })}
                        rows={2}
                        className="bg-[#0f1611] border-white/10"
                      />
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        type="button"
                        onClick={() => remove(row.id)}
                        className="text-white/45 hover:text-red-400"
                        aria-label="删除"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <div className="mt-6 flex items-center justify-between">
        <Button
          variant="ghost"
          onClick={() => navigate(`/projects/${id}/material`)}
          className="text-white/60 hover:text-white"
        >
          <ArrowLeft className="w-4 h-4 mr-1" /> 返回素材
        </Button>
        <Button
          onClick={() => navigate(`/projects/${id}/dubbing`)}
          disabled={items.length === 0}
          className="bg-[#46ec13] hover:bg-[#37c00c] text-[#060a07] font-semibold disabled:opacity-40 disabled:pointer-events-none"
        >
          下一步：配音合成
        </Button>
      </div>
    </div>
  );
}
