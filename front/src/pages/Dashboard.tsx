import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  Film,
  FolderOpen,
  Plus,
  Rocket,
  MessageSquare,
  PenLine,
  ArrowRight,
} from 'lucide-react';
import { AppLayout } from '@/components/layout/AppLayout';
import { RequireAuth } from '@/components/layout/RequireAuth';
import { Button } from '@/components/ui/button';
import {
  listProjects,
  listActivities,
  seedSampleProjectsIfEmpty,
  createProject,
  type Project,
  type Activity,
} from '@/lib/projects-store';
import { formatDistanceToNow } from '@/lib/time';

const ACTIVITY_ICONS: Record<Activity['kind'], typeof Rocket> = {
  publish: Rocket,
  comment: MessageSquare,
  update: PenLine,
};

function DashboardInner() {
  const navigate = useNavigate();
  const [projects, setProjects] = useState<Project[]>([]);
  const [activities, setActivities] = useState<Activity[]>([]);

  useEffect(() => {
    seedSampleProjectsIfEmpty();
    const load = () => {
      setProjects(listProjects().slice(0, 3));
      setActivities(listActivities());
    };
    load();
    window.addEventListener('aivideogpt:projects', load);
    return () => window.removeEventListener('aivideogpt:projects', load);
  }, []);

  const quickCreate = () => {
    const name = window.prompt('请输入新项目名称', `新项目 ${new Date().toLocaleString()}`);
    if (!name) return;
    const p = createProject(name);
    navigate(`/projects/${p.id}/material`);
  };

  return (
    <AppLayout>
      <div className="container-page py-10">
        <header className="mb-10">
          <h1 className="text-3xl font-bold">仪表盘</h1>
          <p className="text-sm text-white/55 mt-1">欢迎回来。这里是您最近活动的快照。</p>
        </header>

        <section className="mb-10">
          <h2 className="text-base font-semibold mb-4">最近项目</h2>
          <div className="grid md:grid-cols-3 gap-5">
            {projects.length === 0 ? (
              <div className="col-span-full rounded-2xl border border-dashed border-white/10 p-10 text-center text-white/50">
                还没有项目，立即创建你的第一个视频项目。
              </div>
            ) : (
              projects.map((p) => (
                <Link
                  key={p.id}
                  to={`/projects/${p.id}/material`}
                  className="group rounded-2xl overflow-hidden bg-white/[0.03] border border-white/[0.06] hover:border-[#46ec13]/40 transition"
                >
                  <div className="aspect-[16/9] bg-white/[0.04] flex items-center justify-center overflow-hidden">
                    {p.thumbnailUrl ? (
                      <img
                        src={p.thumbnailUrl}
                        alt={p.name}
                        className="w-full h-full object-cover group-hover:scale-105 transition"
                        loading="lazy"
                      />
                    ) : (
                      <span className="text-white/40 text-sm">无预览图</span>
                    )}
                  </div>
                  <div className="p-4">
                    <div className="font-semibold text-sm">{p.name}</div>
                    <div className="text-xs text-white/45 mt-1">
                      {formatDistanceToNow(p.updatedAt)}最后编辑
                    </div>
                  </div>
                </Link>
              ))
            )}
          </div>
        </section>

        <div className="grid md:grid-cols-2 gap-8">
          <section>
            <h2 className="text-base font-semibold mb-4">快速操作</h2>
            <div className="flex gap-3 flex-wrap">
              <Button
                onClick={quickCreate}
                className="bg-[#46ec13] hover:bg-[#37c00c] text-[#060a07] font-semibold rounded-full px-5"
              >
                <Plus className="w-4 h-4 mr-1" /> 创建项目
              </Button>
              <Link to="/projects">
                <Button variant="outline" className="rounded-full px-5 border-white/15 bg-white/[0.03] text-white hover:bg-white/10">
                  <FolderOpen className="w-4 h-4 mr-1" /> 查看所有项目
                </Button>
              </Link>
              <Link to="/pricing">
                <Button variant="ghost" className="rounded-full px-5 text-white/70 hover:text-white">
                  <Film className="w-4 h-4 mr-1" /> 升级套餐
                </Button>
              </Link>
            </div>
          </section>

          <section>
            <h2 className="text-base font-semibold mb-4">动态消息</h2>
            <ul className="space-y-3">
              {activities.map((a) => {
                const Icon = ACTIVITY_ICONS[a.kind] || Rocket;
                return (
                  <li
                    key={a.id}
                    className="flex items-start gap-3 rounded-xl p-3 bg-white/[0.03] border border-white/[0.06]"
                  >
                    <div
                      className="w-9 h-9 rounded-full flex items-center justify-center shrink-0"
                      style={{ background: 'rgba(70,236,19,0.12)', color: '#46ec13' }}
                    >
                      <Icon className="w-4 h-4" />
                    </div>
                    <div className="flex-1">
                      <div className="text-sm">{a.title}</div>
                      <div className="text-xs text-white/45 mt-0.5">{a.at}</div>
                    </div>
                    <ArrowRight className="w-4 h-4 text-white/30 mt-2" />
                  </li>
                );
              })}
            </ul>
          </section>
        </div>
      </div>
    </AppLayout>
  );
}

export default function Dashboard() {
  return (
    <RequireAuth>
      <DashboardInner />
    </RequireAuth>
  );
}
