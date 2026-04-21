# AIVideoGPT Modern UI - Development Plan

## Design Guidelines

### Design References (Primary Inspiration)
- **narratoai.cn**: Clean, modern, gradient-heavy design with dark theme
- **Style**: Modern Minimalism + Dark Mode + Gradient Accents + Glassmorphism

### Color Palette
- Primary Background: #0A0A0F (Deep Dark)
- Secondary Background: #12121A (Card/Panel Dark)
- Accent Gradient: from #6366F1 (Indigo) via #8B5CF6 (Violet) to #A855F7 (Purple)
- Accent Secondary: #3B82F6 (Blue)
- Text Primary: #F8FAFC (White)
- Text Secondary: #94A3B8 (Slate-400)
- Text Muted: #64748B (Slate-500)
- Border: #1E293B (Slate-800)
- Success: #10B981 (Emerald)
- Warning: #F59E0B (Amber)
- Error: #EF4444 (Red)
- Card BG: rgba(255,255,255,0.03) with backdrop-blur

### Typography
- Heading1: Inter font-weight 800 (48px-56px)
- Heading2: Inter font-weight 700 (32px-36px)
- Heading3: Inter font-weight 600 (20px-24px)
- Body: Inter font-weight 400 (14px-16px)
- Caption: Inter font-weight 500 (12px)

### Key Component Styles
- **Buttons**: Gradient bg (indigo-to-purple), white text, rounded-xl, hover:brightness-110, shadow-lg
- **Cards**: Dark glass bg with subtle border, rounded-2xl, hover:lift with shadow
- **Sidebar**: Dark panel with icon nav, active item has gradient left border
- **Inputs**: Dark bg (#1E1E2E), subtle border, focus:ring with accent color
- **Sliders**: Custom gradient track, accent thumb

### Layout & Spacing
- Landing: Full-width sections, 120px vertical padding
- Workspace: Sidebar (280px) + Main content area
- Grid: 12-column with 24px gaps
- Card padding: 24px
- Section max-width: 1280px centered

### Images to Generate
1. **hero-ai-video-generation.jpg** - Futuristic AI video creation scene with holographic interface, dark background, purple/blue glow (Style: photorealistic, dark mood)
2. **feature-smart-script.jpg** - Abstract visualization of AI analyzing video frames with text overlays, dark theme (Style: 3d, dark mood)
3. **feature-ai-voice.jpg** - Sound wave visualization with AI neural network pattern, purple gradient (Style: abstract, dark mood)
4. **use-case-content-creator.jpg** - Content creator workspace with multiple screens and video editing, modern dark setup (Style: photorealistic, dark mood)

---

## Development Tasks

1. **todo.md** - This file with design guidelines
2. **src/pages/Index.tsx** - Landing page: hero, features, process steps, use cases, CTA, footer
3. **src/pages/Workspace.tsx** - Workspace dashboard with sidebar + main content area
4. **src/components/layout/Sidebar.tsx** - Sidebar navigation with icons and sections
5. **src/components/workspace/ScriptPanel.tsx** - Script configuration (mode, video file, subtitle source, generate button)
6. **src/components/workspace/AudioPanel.tsx** - Audio settings (TTS engine, voice, BGM, volume controls)
7. **src/components/workspace/VideoPanel.tsx** - Video settings (aspect ratio, quality, volume)
8. **src/components/workspace/SubtitlePanel.tsx** - Subtitle settings (font, position, style, enable toggle)