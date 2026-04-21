import { useState } from 'react';
import { Mic, Video, Save, Play, ChevronLeft, ChevronRight, Clock, Type, User, Sparkles, Wand2, FileText, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';

export type EditMode = 'commentary_only' | 'original_only' | 'smart_insert';
export type NarrationStyle = 'default' | 'casual' | 'high_energy' | 'nonsense' | 'live' | 'news' | 'guided' | 'roast';
export type PersonPerspective = 'first' | 'third';
export type ScriptType = 'standard' | 'rewrite' | 'continue';

export interface ConfigFormValue {
  // 基础配置
  editMode: EditMode;
  originalRatio: number;
  videoLanguage: string;
  narrationLanguage: string;
  
  // 解说配置
  generationMode: 'auto' | 'manual';
  speechSpeed: 'slow' | 'comfortable' | 'standard' | 'moderate' | 'fast' | 'compact' | 'extreme';
  wordCount: string;
  perspective: PersonPerspective;
  narrationStyle: NarrationStyle;
  
  // 高级选项
  scriptType: ScriptType;
  temperature: number;
  
  // 后端现有参数映射
  ttsEngine: string;
  voiceRole: string;
  speed: number;
  aspectRatio: string;
  videoQuality: string;
  subtitleFont: string;
  subtitleSize: number;
  subtitleEnabled: boolean;
}

interface ConfigStepProps {
  projectType: string;
  value: ConfigFormValue;
  onChange: (next: ConfigFormValue) => void;
  onGenerate: () => void;
  generating: boolean;
  onBack?: () => void;
  onReupload?: () => void;
}

// 视频剪辑模式
const editModes: { key: EditMode; label: string; desc: string; tag?: string }[] = [
  { key: 'commentary_only', label: '仅解说', desc: '解说覆盖全程，适合强调节奏与信息密度的内容。', tag: '声音统一，节奏可控' },
  { key: 'original_only', label: '仅原片', desc: '保留视频原声，不额外添加解说，突出画面氛围。', tag: '保留现场氛围' },
  { key: 'smart_insert', label: '智能穿插', desc: 'AI智能判断原片与解说段落，混合呈现精彩镜头。', tag: '自动平衡画面与解说' },
];

// 语速选项
const speechSpeeds: { key: ConfigFormValue['speechSpeed']; label: string }[] = [
  { key: 'slow', label: '慢速' },
  { key: 'comfortable', label: '舒适' },
  { key: 'standard', label: '标准' },
  { key: 'moderate', label: '适中' },
  { key: 'fast', label: '快速' },
  { key: 'compact', label: '紧凑' },
  { key: 'extreme', label: '极速' },
];

// 文案字数选项
const wordCountOptions: { key: string; label: string; desc: string }[] = [
  { key: 'default', label: '默认字数 / 可自行调整', desc: '800-1000字' },
  { key: '500-800', label: '500-800 字', desc: '短视频 / 高速节奏' },
  { key: '800-1200', label: '800-1200 字', desc: '常规节奏 / 资讯类' },
  { key: '1200-1800', label: '1200-1800 字', desc: '剧情解说 / 信息更丰富' },
  { key: '1800-2500', label: '1800-2500 字', desc: '电影解析 / 长内容' },
  { key: '2500-3500', label: '2500-3500 字', desc: '深度解析 / 长视频' },
];

// 解说风格
const narrationStyles: { key: NarrationStyle; label: string; desc: string; version?: string }[] = [
  { key: 'default', label: '默认风格（智能穿插）', desc: '文案要求，先将整个视频最吸引人的部分放开头，偏口语化表达支持解说与原片智能穿插。', version: '1.0.0' },
  { key: 'casual', label: '口语化叙述（智能穿插）', desc: '接地气的口语化表达，不使用排比句和总结内容支持解说与原片智能穿插。', version: '1.0.0' },
  { key: 'high_energy', label: '高能白话（智能穿插）', desc: '视频开头直接上最炸裂的画面，用跟兄弟聊天的口气支持解说与原片智能穿插。', version: '1.0.0' },
  { key: 'nonsense', label: '胡说八道（智能穿插）', desc: '知识渊博但脑洞大开的伪专家风格，一本正经地胡说八道支持解说与原片智能穿插。', version: '1.0.0' },
  { key: 'live', label: '直播带货（智能穿插）', desc: '建立对主播的信任，提炼产品价值，使用"向导"口吻支持解说与原片智能穿插。', version: '1.0.0' },
  { key: 'news', label: '新闻联播（智能穿插）', desc: '新闻播报风格，以"据报道"、"据新华社"等词开头支持解说与原片智能穿插。', version: '1.0.0' },
  { key: 'guided', label: '引导式开头（智能穿插）', desc: '情感引导，直接切入普通人都会有的痛点支持解说与原片智能穿插。', version: '1.0.0' },
  { key: 'roast', label: '吐槽式开头（智能穿插）', desc: '风趣幽默、犀利的吐槽或评论，各种玩梗支持解说与原片智能穿插。', version: '1.0.0' },
];

// 文案类型
const scriptTypes: { key: ScriptType; label: string; desc: string }[] = [
  { key: 'standard', label: '标准解说文案', desc: 'AI根据视频内容自动生成解说文案' },
  { key: 'rewrite', label: '参考改写', desc: '提供参考文案，AI基于此进行改写优化' },
  { key: 'continue', label: '根据剧情提要生成后续解说', desc: '基于前情提要，生成后续剧情的解说' },
];

export default function ConfigStep({ 
  projectType, 
  value, 
  onChange, 
  onGenerate, 
  generating,
  onBack,
  onReupload 
}: ConfigStepProps) {
  const [showAdvanced, setShowAdvanced] = useState(false);
  
  const setField = <K extends keyof ConfigFormValue>(key: K, fieldValue: ConfigFormValue[K]) => {
    onChange({ ...value, [key]: fieldValue });
  };

  return (
    <div className="h-full flex flex-col bg-[#0a0a0a]">
      {/* 主内容区 - 可滚动 */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-4xl mx-auto px-6 py-8 space-y-8">
          {/* 标题 */}
          <div>
            <h2 className="text-xl font-semibold text-white mb-2">配置解说参数</h2>
          </div>

          {/* 基础配置 */}
          <section>
            <h3 className="text-sm font-medium text-white mb-1">基础配置</h3>
            <p className="text-xs text-slate-500 mb-4">视频剪辑模式</p>
            
            <div className="grid grid-cols-3 gap-3">
              {editModes.map((mode) => {
                const isSelected = value.editMode === mode.key;
                return (
                  <button
                    key={mode.key}
                    onClick={() => setField('editMode', mode.key)}
                    className={`p-4 rounded-xl border text-left transition-all ${
                      isSelected
                        ? 'bg-[#4ADE80]/10 border-[#4ADE80]/50'
                        : 'bg-[#1a1a1a] border-white/[0.06] hover:border-white/[0.12]'
                    }`}
                  >
                    <div className="flex items-start justify-between mb-2">
                      <h4 className={`text-sm font-medium ${isSelected ? 'text-[#4ADE80]' : 'text-white'}`}>
                        {mode.label}
                      </h4>
                      {mode.tag && (
                        <span className="text-[10px] px-2 py-0.5 rounded-full bg-white/[0.06] text-slate-400">
                          {mode.tag}
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-slate-500 leading-relaxed">{mode.desc}</p>
                  </button>
                );
              })}
            </div>
          </section>

          {/* 原片占比滑块 */}
          <section className="bg-[#1a1a1a] rounded-xl p-4 border border-white/[0.06]">
            <div className="flex items-center justify-between mb-4">
              <span className="text-sm text-white">原片占比</span>
              <span className="text-sm font-medium text-[#4ADE80]">{value.originalRatio}%</span>
            </div>
            <input
              type="range"
              min="20"
              max="60"
              step="5"
              value={value.originalRatio}
              onChange={(e) => setField('originalRatio', parseInt(e.target.value))}
              className="w-full h-2 rounded-full appearance-none bg-white/[0.06] cursor-pointer"
              style={{
                background: `linear-gradient(to right, #4ADE80 0%, #4ADE80 ${(value.originalRatio - 20) / 40 * 100}%, rgba(255,255,255,0.06) ${(value.originalRatio - 20) / 40 * 100}%, rgba(255,255,255,0.06) 100%)`
              }}
            />
            <div className="flex justify-between mt-2 text-[10px] text-slate-500">
              <span>20%</span>
              <span>25%</span>
              <span>30%</span>
              <span>35%</span>
              <span>40%</span>
              <span>45%</span>
              <span>50%</span>
              <span>55%</span>
              <span>60%</span>
            </div>
            <p className="text-xs text-slate-500 mt-3">
              原片占比越高，保留的原声越多；降低比例可以让解说更连贯。
            </p>
          </section>

          {/* 语言选择 */}
          <section className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-white mb-2">视频原语言</label>
              <select
                value={value.videoLanguage}
                onChange={(e) => setField('videoLanguage', e.target.value)}
                className="w-full px-4 py-3 rounded-xl bg-[#1a1a1a] border border-white/[0.06] text-sm text-white focus:outline-none focus:border-[#4ADE80]/50 appearance-none cursor-pointer"
              >
                <option value="zh">简体中文</option>
                <option value="en">English</option>
                <option value="ja">日本語</option>
                <option value="ko">한국어</option>
              </select>
            </div>
            <div>
              <label className="block text-sm text-white mb-2">解说语言</label>
              <select
                value={value.narrationLanguage}
                onChange={(e) => setField('narrationLanguage', e.target.value)}
                className="w-full px-4 py-3 rounded-xl bg-[#1a1a1a] border border-white/[0.06] text-sm text-white focus:outline-none focus:border-[#4ADE80]/50 appearance-none cursor-pointer"
              >
                <option value="zh">简体中文</option>
                <option value="en">English</option>
                <option value="ja">日本語</option>
                <option value="ko">한국어</option>
              </select>
            </div>
          </section>

          {/* 解说配置 */}
          <section>
            <h3 className="text-sm font-medium text-white mb-4">解说配置</h3>
            
            {/* 文案生成方式 */}
            <p className="text-xs text-slate-500 mb-3">文案生成方式</p>
            <div className="grid grid-cols-2 gap-3 mb-6">
              <button
                onClick={() => setField('generationMode', 'auto')}
                className={`p-4 rounded-xl border text-left transition-all ${
                  value.generationMode === 'auto'
                    ? 'bg-[#4ADE80]/10 border-[#4ADE80]/50'
                    : 'bg-[#1a1a1a] border-white/[0.06] hover:border-white/[0.12]'
                }`}
              >
                <h4 className={`text-sm font-medium mb-1 ${value.generationMode === 'auto' ? 'text-[#4ADE80]' : 'text-white'}`}>
                  AI 自动生成
                </h4>
                <p className="text-xs text-slate-500">由智能模型生成文案，完成后可继续匹配画面。</p>
              </button>
              <button
                onClick={() => setField('generationMode', 'manual')}
                className={`p-4 rounded-xl border text-left transition-all ${
                  value.generationMode === 'manual'
                    ? 'bg-[#4ADE80]/10 border-[#4ADE80]/50'
                    : 'bg-[#1a1a1a] border-white/[0.06] hover:border-white/[0.12]'
                }`}
              >
                <h4 className={`text-sm font-medium mb-1 ${value.generationMode === 'manual' ? 'text-[#4ADE80]' : 'text-white'}`}>
                  手动输入文案
                </h4>
                <p className="text-xs text-slate-500">跳过文案生成，直接粘贴现有文案后匹配画面。</p>
              </button>
            </div>

            {/* 语速 */}
            <div className="grid grid-cols-2 gap-6 mb-6">
              <div>
                <label className="block text-xs text-slate-400 mb-3">推荐语速 (5字/秒)</label>
                <div className="flex flex-wrap gap-2">
                  {speechSpeeds.map((speed) => (
                    <button
                      key={speed.key}
                      onClick={() => setField('speechSpeed', speed.key)}
                      className={`px-3 py-1.5 rounded-lg text-xs transition-all ${
                        value.speechSpeed === speed.key
                          ? 'bg-[#4ADE80] text-black font-medium'
                          : 'bg-[#1a1a1a] text-slate-400 border border-white/[0.06] hover:border-white/[0.12]'
                      }`}
                    >
                      {speed.label}
                    </button>
                  ))}
                </div>
              </div>
              
              {/* 文案字数 */}
              <div>
                <label className="block text-xs text-slate-400 mb-3">文案字数</label>
                <div className="flex flex-wrap gap-2">
                  {wordCountOptions.slice(0, 4).map((opt) => (
                    <button
                      key={opt.key}
                      onClick={() => setField('wordCount', opt.key)}
                      className={`px-3 py-1.5 rounded-lg text-xs transition-all ${
                        value.wordCount === opt.key
                          ? 'bg-[#4ADE80] text-black font-medium'
                          : 'bg-[#1a1a1a] text-slate-400 border border-white/[0.06] hover:border-white/[0.12]'
                      }`}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
                <p className="text-xs text-slate-500 mt-2">
                  默认字数为 800-1000 字，适配大多数快速推流场景。
                </p>
              </div>
            </div>

            {/* 人称视角 */}
            <div className="grid grid-cols-2 gap-3">
              <button
                onClick={() => setField('perspective', 'first')}
                className={`p-4 rounded-xl border text-left transition-all ${
                  value.perspective === 'first'
                    ? 'bg-[#1a1a1a] border-[#4ADE80]/50'
                    : 'bg-[#1a1a1a] border-white/[0.06] hover:border-white/[0.12]'
                }`}
              >
                <h4 className={`text-sm font-medium mb-1 ${value.perspective === 'first' ? 'text-[#4ADE80]' : 'text-white'}`}>
                  第一人称
                </h4>
                <p className="text-xs text-slate-500">"我看到..."，代入感强</p>
              </button>
              <button
                onClick={() => setField('perspective', 'third')}
                className={`p-4 rounded-xl border text-left transition-all ${
                  value.perspective === 'third'
                    ? 'bg-[#4ADE80]/10 border-[#4ADE80]/50'
                    : 'bg-[#1a1a1a] border-white/[0.06] hover:border-white/[0.12]'
                }`}
              >
                <h4 className={`text-sm font-medium mb-1 ${value.perspective === 'third' ? 'text-[#4ADE80]' : 'text-white'}`}>
                  第三人称
                </h4>
                <p className="text-xs text-slate-500">"他/她..."，客观叙述</p>
              </button>
            </div>
          </section>

          {/* 解说风格 */}
          <section>
            <h3 className="text-sm font-medium text-white mb-4">解说风格</h3>
            <div className="grid grid-cols-3 gap-3">
              {narrationStyles.map((style) => (
                <button
                  key={style.key}
                  onClick={() => setField('narrationStyle', style.key)}
                  className={`p-4 rounded-xl border text-left transition-all ${
                    value.narrationStyle === style.key
                      ? 'bg-[#4ADE80]/10 border-[#4ADE80]/50'
                      : 'bg-[#1a1a1a] border-white/[0.06] hover:border-white/[0.12]'
                  }`}
                >
                  <div className="flex items-start justify-between mb-2">
                    <h4 className={`text-sm font-medium ${value.narrationStyle === style.key ? 'text-[#4ADE80]' : 'text-white'}`}>
                      {style.label}
                    </h4>
                    {style.version && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/[0.06] text-slate-500">
                        {style.version}
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-slate-500 leading-relaxed">{style.desc}</p>
                </button>
              ))}
            </div>
          </section>

          {/* 高级选项 */}
          <section>
            <button
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="flex items-center gap-2 text-sm text-white hover:text-[#4ADE80] transition-colors"
            >
              <span>高级选项</span>
              <ChevronRight className={`w-4 h-4 transition-transform ${showAdvanced ? 'rotate-90' : ''}`} />
            </button>
            
            {showAdvanced && (
              <div className="mt-4 space-y-4">
                {/* 文案类型 */}
                <div>
                  <p className="text-xs text-slate-500 mb-3">文案类型</p>
                  <div className="grid grid-cols-3 gap-3">
                    {scriptTypes.map((type) => (
                      <button
                        key={type.key}
                        onClick={() => setField('scriptType', type.key)}
                        className={`p-3 rounded-xl border text-left transition-all ${
                          value.scriptType === type.key
                            ? 'bg-[#4ADE80]/10 border-[#4ADE80]/50'
                            : 'bg-[#1a1a1a] border-white/[0.06] hover:border-white/[0.12]'
                        }`}
                      >
                        <h4 className={`text-sm font-medium mb-1 ${value.scriptType === type.key ? 'text-[#4ADE80]' : 'text-white'}`}>
                          {type.label}
                        </h4>
                        <p className="text-xs text-slate-500">{type.desc}</p>
                      </button>
                    ))}
                  </div>
                </div>
                
                {/* 辅助说明 */}
                <div>
                  <label className="block text-xs text-slate-400 mb-2">辅助说明（可选）</label>
                  <textarea
                    placeholder="输入额外的创作要求或背景信息..."
                    className="w-full h-24 px-4 py-3 rounded-xl bg-[#1a1a1a] border border-white/[0.06] text-sm text-white placeholder:text-slate-600 focus:outline-none focus:border-[#4ADE80]/50 resize-none"
                  />
                </div>
              </div>
            )}
          </section>

          {/* 底部操作栏 - 固定在内容底部 */}
          <div className="flex items-center justify-between pt-6 pb-2">
            <div className="flex items-center gap-3">
              <Button
                variant="outline"
                size="sm"
                onClick={onBack}
                className="border-white/[0.08] text-slate-400 hover:text-white hover:bg-white/[0.04]"
              >
                <ChevronLeft className="w-4 h-4 mr-1" />返回
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={onReupload}
                className="border-white/[0.08] text-slate-400 hover:text-white hover:bg-white/[0.04]"
              >
                <RefreshCw className="w-4 h-4 mr-1" />重新上传
              </Button>
            </div>
            <div className="flex items-center gap-3">
              <Button
                variant="outline"
                size="sm"
                className="border-[#4ADE80]/30 text-[#4ADE80] hover:bg-[#4ADE80]/10"
              >
                <Save className="w-4 h-4 mr-1.5" />保存配置
              </Button>
              <Button
                size="sm"
                onClick={onGenerate}
                disabled={generating}
                className="bg-[#4ADE80] hover:bg-[#4ADE80]/90 text-black font-medium"
              >
                <Play className="w-4 h-4 mr-1.5" />
                {generating ? '生成中...' : '开始生成文案'}
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}


