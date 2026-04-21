import { MarketingLayout } from '@/components/layout/MarketingLayout';

const SECTIONS = [
  {
    title: '1. 我们收集的信息',
    body:
      'AIVideoGPT 仅收集你创建账户、创建项目、生成视频过程中必需的信息，包括邮箱、昵称、上传的素材文件以及运行日志。我们不会收集任何与视频内容无关的个人身份信息。',
  },
  {
    title: '2. 信息的使用',
    body:
      '收集的信息仅用于：提供视频脚本生成与配音合成服务、保障账户安全、改进模型效果。我们不会出售、出租或以其他形式与无关第三方共享你的数据。',
  },
  {
    title: '3. 数据存储',
    body:
      '素材文件与中间产物默认加密存储在中国大陆机房。专业版及以上用户可以选择 VPC 私有化部署，数据完全存储在自有环境中。',
  },
  {
    title: '4. Cookie 与本地存储',
    body:
      '我们使用少量必要的 Cookie 与本地存储用于登录保持、偏好设置和性能监控。你可以在浏览器中随时清除。',
  },
  {
    title: '5. 用户权利',
    body:
      '你有权随时访问、更正或删除自己的账户与项目数据。发送邮件至 privacy@aivideogpt.dev 即可行使上述权利，我们将在 15 个工作日内回复。',
  },
  {
    title: '6. 政策更新',
    body:
      '本隐私政策将不定期更新。重大变更时我们会通过邮件或站内信通知；继续使用即表示接受更新后的政策。',
  },
];

export default function PrivacyPolicyPage() {
  return (
    <MarketingLayout>
      <section className="container-page py-20">
        <h1 className="text-4xl font-extrabold mb-3">隐私政策</h1>
        <p className="text-sm text-white/55 mb-10">最后更新：{new Date().toLocaleDateString()}</p>
        <div className="space-y-8 max-w-3xl">
          {SECTIONS.map((s) => (
            <section key={s.title}>
              <h2 className="text-lg font-semibold mb-2">{s.title}</h2>
              <p className="text-sm text-white/65 leading-relaxed">{s.body}</p>
            </section>
          ))}
        </div>
      </section>
    </MarketingLayout>
  );
}
