import { createMachine, assign } from 'xstate';

export interface VideoConfig {
  mode: 'commentary' | 'original' | 'smart';
  originalRatio: number;
  sourceLang: string;
  targetLang: string;
  speed: string;
  wordCount: string;
  perspective: 'first' | 'third';
  style: string;
}

export interface VideoContext {
  videoFile: File | null;
  videoUrl: string | null;
  config: VideoConfig;
  taskId: string | null;
  analysis: string | null;
  script: string | null;
  audioUrl: string | null;
  error: string | null;
  progress: number;
}

export type VideoEvent =
  | { type: 'UPLOAD'; file: File }
  | { type: 'SET_CONFIG'; config: Partial<VideoConfig> }
  | { type: 'START_PROCESS' }
  | { type: 'TASK_CREATED'; taskId: string }
  | { type: 'ANALYSIS_COMPLETE'; analysis: string }
  | { type: 'SCRIPT_COMPLETE'; script: string }
  | { type: 'UPDATE_SCRIPT'; script: string }
  | { type: 'START_AUDIO_GEN' }
  | { type: 'AUDIO_COMPLETE'; audioUrl: string }
  | { type: 'RESET' }
  | { type: 'ERROR'; message: string }
  | { type: 'SET_PROGRESS'; progress: number };

export const videoMachine = createMachine(
  {
    id: 'videoProcessor',
    initial: 'idle',
    context: {
      videoFile: null,
      videoUrl: null,
      config: {
        mode: 'smart',
        originalRatio: 45,
        sourceLang: 'zh-CN',
        targetLang: 'zh-CN',
        speed: 'standard',
        wordCount: '500-800',
        perspective: 'third',
        style: 'default',
      },
      taskId: null,
      analysis: null,
      script: null,
      audioUrl: null,
      error: null,
      progress: 0,
    } as VideoContext,
    states: {
      idle: {
        on: {
          UPLOAD: {
            target: 'uploading',
            actions: assign({
              videoFile: ({ event }) => event.file,
              videoUrl: ({ event }) => URL.createObjectURL(event.file),
              error: null,
              progress: 0,
            }),
          },
        },
      },
      uploading: {
        after: {
          1000: 'configuring',
        },
        on: {
          ERROR: 'error',
        },
      },
      configuring: {
        on: {
          SET_CONFIG: {
            actions: assign({
              config: ({ context, event }) => ({ ...context.config, ...event.config }),
            }),
          },
          TASK_CREATED: {
            target: 'analyzing',
            actions: assign({ taskId: ({ event }) => event.taskId }),
          },
          RESET: 'idle',
        },
      },
      analyzing: {
        on: {
          SET_PROGRESS: {
            actions: assign({ progress: ({ event }) => event.progress }),
          },
          ANALYSIS_COMPLETE: {
            target: 'scripting',
            actions: assign({ analysis: ({ event }) => event.analysis, taskId: null, progress: 0 }),
          },
          ERROR: 'error',
        },
      },
      scripting: {
        on: {
          SET_PROGRESS: {
            actions: assign({ progress: ({ event }) => event.progress }),
          },
          SCRIPT_COMPLETE: {
            target: 'editing',
            actions: assign({ script: ({ event }) => event.script, taskId: null, progress: 0 }),
          },
          ERROR: 'error',
        },
      },
      editing: {
        on: {
          UPDATE_SCRIPT: {
            actions: assign({ script: ({ event }) => event.script }),
          },
          TASK_CREATED: {
            target: 'generatingAudio',
            actions: assign({ taskId: ({ event }) => event.taskId }),
          },
          RESET: 'idle',
        },
      },
      generatingAudio: {
        on: {
          SET_PROGRESS: {
            actions: assign({ progress: ({ event }) => event.progress }),
          },
          AUDIO_COMPLETE: {
            target: 'previewing',
            actions: assign({ audioUrl: ({ event }) => event.audioUrl, taskId: null, progress: 0 }),
          },
          ERROR: 'error',
        },
      },
      previewing: {
        on: {
          RESET: 'idle',
        },
      },
      error: {
        on: {
          RESET: 'idle',
        },
      },
    },
  }
);
