import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export interface User {
  user_id: string;
  name: string;
}

export interface ChatMessage {
  id: number | string;
  agent: string;
  query?: string;
  response: string;
  timestamp: string;
  author?: string; // for streaming chunks
  isQuizTrigger?: boolean;
  quizModule?: string;
  quizStatus?: 'loading' | 'ready' | 'completed' | 'abandoned';
  quizScore?: string;
  quizFeedback?: string;
}

interface AppState {
  user: User | null;
  activePath: string | null;
  chatHistory: ChatMessage[];
  modelMode: 'local' | 'online';
  
  // Quiz State
  quizActive: boolean;
  quizModule: string | null;
  quizPreloadedData: any | null;
  activeQuizMsgId: string | null;
  quizRequired: boolean;
  
  setUser: (user: User | null) => void;
  setActivePath: (sessionId: string | null) => void;
  setChatHistory: (history: ChatMessage[]) => void;
  addChatMessage: (msg: ChatMessage) => void;
  updateLastMessage: (content: string) => void;
  updateQuizTriggerMessage: (msgId: string, status: 'ready' | 'completed' | 'abandoned', preloadedData?: any, score?: string, feedback?: string) => void;
  setModelMode: (mode: 'local' | 'online') => void;
  setQuizState: (active: boolean, module: string | null, msgId?: string) => void;
  setQuizPreloadedData: (data: any) => void;
  setQuizRequired: (required: boolean) => void;
  removeEmptyLastMessage: () => void;
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      user: null,
      activePath: null,
      chatHistory: [],
      modelMode: 'local',
      quizActive: false,
      quizModule: null,
      quizPreloadedData: null,
      activeQuizMsgId: null,
      quizRequired: false,

      setUser: (user) => set({ user }),
      setActivePath: (activePath) => set({ 
        activePath,
        quizActive: false,
        quizModule: null,
        quizPreloadedData: null,
        activeQuizMsgId: null,
        quizRequired: false
      }),
      setChatHistory: (chatHistory) => set({ chatHistory }),
      addChatMessage: (msg) => set((state) => ({ chatHistory: [...state.chatHistory, msg] })),
      updateLastMessage: (content) => set((state) => {
        const history = [...state.chatHistory];
        if (history.length > 0) {
          const last = history[history.length - 1];
          history[history.length - 1] = { ...last, response: last.response + content };
        }
        return { chatHistory: history };
      }),
      updateQuizTriggerMessage: (msgId, status, preloadedData, score, feedback) => set((state) => {
        const history = state.chatHistory.map(msg => 
          msg.id === msgId ? { ...msg, quizStatus: status, quizScore: score, quizFeedback: feedback, response: status === 'completed' ? "Quiz completed!" : status === 'abandoned' ? "Quiz abandoned." : "Quiz created! Click to answer." } : msg
        );
        if (preloadedData) {
          return { chatHistory: history, quizPreloadedData: preloadedData };
        }
        return { chatHistory: history };
      }),
      setModelMode: (modelMode) => set({ modelMode }),
      setQuizState: (quizActive, quizModule, msgId) => set({ quizActive, quizModule, activeQuizMsgId: msgId || null }),
      setQuizPreloadedData: (quizPreloadedData) => set({ quizPreloadedData }),
      setQuizRequired: (quizRequired) => set({ quizRequired }),
      removeEmptyLastMessage: () => set((state) => {
        const history = [...state.chatHistory];
        if (history.length > 0) {
          const last = history[history.length - 1];
          // If the last message is from the system or assistant and is completely empty, remove it
          if (!last.response.trim() && !last.isQuizTrigger) {
            history.pop();
          }
        }
        return { chatHistory: history };
      })
    }),
    {
      name: 'ai-tutor-storage',
      partialize: (state) => ({ 
        user: state.user, 
        activePath: state.activePath, 
        modelMode: state.modelMode 
      }), // only persist user and path
    }
  )
);
