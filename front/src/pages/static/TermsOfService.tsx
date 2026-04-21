import { MarketingLayout } from '@/components/layout/MarketingLayout';

const SECTIONS = [
  {
    title: '1. 协议概述',
    body:
      '欢迎使用 AIVideoGPT。你使用本服务即表示已阅读、理解并同意本服务条款。若不同意，请停止使用本服务。',
  },
  {
    title: '2. 账号与责任',
    body:
      '你需对所注册账号的安全负责，妥善保管密码并及时更新。账号下的一切活动将视为你本人的行为。',
  },
  {
    title: '3. 内容规范',
    body:
      '严禁使用 AIVideoGPT 生成涉黄涉赌、侵犯他人权益、违反法律法规的视频内容。我们有权随时下架违规内容并暂停相关账号。',
  },
  {
    title: '4. 订阅与退款',
    body:
      '订阅自动续费，你可以随时在控制台取消后续扣费。退款政策详见《定价》页及付款页面的说明。',
  },
  {
    title: '5. 责任限制',
    body:
      'AIVideoGPT 按"现状"提供服务。对因不可抗力、网络故障、第三方 API 变更造成的损失，我们在法律允许范围内不承担赔偿责任。',
  },
  {
    title: '6. 争议解决',
    body:
      '本条款适用中华人民共和国法律。如发生争议，双方应先友好协商；协商不成的提交服务提供方所在地人民法院诉讼解决。',
  },
];

export default function TermsOfServicePage() {
  return (
    <MarketingLayout>
      <section className="container-page py-20">
        <h1 className="text-4xl font-extrabold mb-3">服务条款</h1>
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
