import { useState, useEffect } from 'react';
import { useAppStore } from '../store/store';
import { Loader2, X, CheckCircle2, XCircle, AlertTriangle } from 'lucide-react';
 
interface Question {
  question: string;
  type: 'mcq' | 'short_answer';
  options?: string[];
  topic: string;
}
 
interface QuizState {
  status: 'loading' | 'active' | 'evaluating' | 'complete';
  currentQuestion?: Question;
  history: any[];
  finalReview?: {
    score: string;
    feedback: string;
    needs_remedial: boolean;
    remedial_topic?: string;
    wrong_topics?: string[];
    syllabus_updated?: boolean;
  };
  evaluationFeedback?: string;
  evaluationIsCorrect?: boolean;
}
 
export default function QuizOverlay() {
  const { user, activePath, quizActive, quizModule, quizPreloadedData, setQuizState, activeQuizMsgId, updateQuizTriggerMessage } = useAppStore();
  const [state, setState] = useState<QuizState>({ status: 'loading', history: [] });
  const [answer, setAnswer] = useState('');
 
  useEffect(() => {
    if (quizActive && state.status === 'loading') {
      if (quizPreloadedData) {
        setState({
          status: 'active',
          currentQuestion: quizPreloadedData as Question,
          history: []
        });
      } else if (activePath && user) {
        // Fallback fetch if somehow preloaded data is missing
        fetch('/api/quiz/start', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ user_id: user.user_id, session_id: activePath })
        })
        .then(res => res.json())
        .then(data => {
          setState({
            status: 'active',
            currentQuestion: data as Question,
            history: []
          });
        })
        .catch(err => {
          console.error(err);
          setQuizState(false, null);
        });
      }
    }
  }, [quizActive, quizPreloadedData, activePath, user, state.status, setQuizState]);
 
  if (!quizActive) return null;
 
  const handleSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!answer.trim() || state.status !== 'active' || !state.currentQuestion) return;
 
    setState(prev => ({ ...prev, status: 'evaluating' }));
 
    const updatedHistory = [
      ...state.history,
      {
        question: state.currentQuestion.question,
        user_answer: answer,
        is_correct: null,
        correct_answer: null
      }
    ];
 
    try {
      const res = await fetch('/api/quiz/answer', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: user?.user_id,
          session_id: activePath,
          history: updatedHistory,
          answer: answer,
          module_name: quizModule
        })
      });
      const result = await res.json();
 
      const enrichedHistory = updatedHistory.map((h, i) =>
        i === updatedHistory.length - 1
          ? { ...h, is_correct: result.is_correct, correct_answer: result.correct_answer }
          : h
      );
 
      setState(prev => ({
        ...prev,
        status: result.status === 'complete' ? 'complete' : 'active',
        currentQuestion: result.next_question,
        history: enrichedHistory,
        finalReview: result.final_review,
        evaluationFeedback: result.evaluation,
        evaluationIsCorrect: result.is_correct
      }));
      setAnswer('');
      
      // Dispatch events for the UI to catch
      if (result.status === 'complete') {
        if (activeQuizMsgId) {
          updateQuizTriggerMessage(
            activeQuizMsgId, 
            'completed', 
            null, 
            result.final_review?.score, 
            result.final_review?.feedback
          );
        }
        window.dispatchEvent(new CustomEvent('quiz_completed', { 
          detail: { 
            module: quizModule,
            wrongTopics: result.final_review?.wrong_topics || [],
            score: result.final_review?.score || 'N/A'
          } 
        }));
        window.dispatchEvent(new CustomEvent('path_updated'));
      }
      
      // Clear evaluation message after 3 seconds if continuing
      if (result.status === 'ongoing') {
        setTimeout(() => {
          setState(prev => ({ ...prev, evaluationFeedback: undefined }));
        }, 3000);
      }
    } catch (err) {
      console.error(err);
      setState(prev => ({ ...prev, status: 'active' }));
    }
  };
 
  const handleClose = () => {
    // Quiz can only be closed after completion
    setQuizState(false, null);
    useAppStore.getState().setQuizRequired(false);
  };
 
  return (
    <div className="fixed inset-0 z-[150] bg-black/60 backdrop-blur-md p-6 flex flex-col items-center justify-center animate-in fade-in duration-200">
      <div className="w-full max-w-3xl bg-zinc-950 border border-zinc-800 rounded-3xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-8 py-6 border-b border-zinc-800 bg-zinc-900/50">
          <div>
            <h3 className="text-xl font-semibold text-zinc-100 flex items-center gap-3">
              Module Assessment
            </h3>
            <p className="text-sm text-zinc-400 mt-1">{quizModule || 'Dynamic Generation'}</p>
          </div>
          {state.status === 'complete' && (
            <button 
              onClick={handleClose}
              className="p-2 hover:bg-zinc-800 rounded-xl text-zinc-400 hover:text-zinc-100 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          )}
        </div>
 
        {/* Body */}
        <div className="p-8 overflow-y-auto flex-1 custom-scrollbar relative bg-zinc-950">
          {state.status === 'loading' && (
            <div className="flex flex-col items-center justify-center py-20 space-y-4">
              <Loader2 className="w-8 h-8 text-indigo-500 animate-spin" />
              <p className="text-zinc-400">Loading your personalized quiz...</p>
            </div>
          )}
 
          {state.evaluationFeedback && state.status !== 'complete' && (
            <div className={`mb-8 p-5 rounded-2xl flex gap-4 text-base border ${state.evaluationIsCorrect ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' : 'bg-rose-500/10 border-rose-500/20 text-rose-400'}`}>
              {state.evaluationIsCorrect ? <CheckCircle2 className="w-6 h-6 shrink-0" /> : <XCircle className="w-6 h-6 shrink-0" />}
              <p>{state.evaluationFeedback}</p>
            </div>
          )}
 
          {state.status !== 'loading' && state.status !== 'complete' && state.currentQuestion && (
            <div className="space-y-8">
              <div>
                <span className="text-xs font-bold tracking-widest uppercase text-indigo-400 mb-3 block">
                  Question {state.history.length + 1}
                </span>
                <h4 className="text-zinc-100 font-medium text-xl leading-relaxed">
                  {state.currentQuestion.question}
                </h4>
              </div>
 
              {state.currentQuestion.type === 'mcq' && state.currentQuestion.options ? (
                <div className="space-y-3">
                  {state.currentQuestion.options.map((opt, idx) => (
                    <button
                      key={idx}
                      onClick={() => setAnswer(opt)}
                      className={`w-full text-left p-5 rounded-2xl border-2 transition-all ${
                        answer === opt 
                          ? 'bg-indigo-500/10 border-indigo-500 text-indigo-300 shadow-[0_0_15px_rgba(99,102,241,0.15)]' 
                          : 'bg-zinc-900 border-zinc-800 text-zinc-300 hover:border-zinc-700 hover:bg-zinc-800'
                      }`}
                    >
                      <span className="text-base">{opt}</span>
                    </button>
                  ))}
                </div>
              ) : (
                <textarea
                  value={answer}
                  onChange={(e) => setAnswer(e.target.value)}
                  placeholder="Type your detailed answer here..."
                  className="w-full bg-zinc-900 border-2 border-zinc-800 rounded-2xl p-5 text-base text-zinc-200 focus:outline-none focus:border-indigo-500 transition-colors h-48 resize-none"
                />
              )}
            </div>
          )}
 
          {state.status === 'complete' && state.finalReview && (
            <div className="space-y-8 text-center py-10">
              <div className="w-24 h-24 bg-indigo-500/10 rounded-full flex items-center justify-center mx-auto border-2 border-indigo-500/20">
                <span className="text-3xl font-bold text-indigo-400">{state.finalReview.score}</span>
              </div>
              <div className="max-w-xl mx-auto">
                <h3 className="text-2xl font-bold text-zinc-100">Quiz Completed</h3>
                <p className="text-base text-zinc-400 mt-4 leading-relaxed">
                  {state.finalReview.feedback}
                </p>
              </div>
              {state.finalReview.wrong_topics && state.finalReview.wrong_topics.length > 0 && (
                <div className="bg-amber-500/10 border-2 border-amber-500/20 rounded-2xl p-6 text-left max-w-xl mx-auto">
                  <p className="text-sm font-bold text-amber-500 uppercase tracking-widest mb-3 flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4" /> Remedial Topics Added
                  </p>
                  <p className="text-sm text-amber-400/80 mb-3">The following topics have been added to your syllabus for review:</p>
                  <ul className="space-y-2">
                    {state.finalReview.wrong_topics.map((topic: string, idx: number) => (
                      <li key={idx} className="flex items-center gap-2 text-base text-amber-400/90">
                        <span className="w-1.5 h-1.5 rounded-full bg-amber-400 shrink-0"></span>
                        <span>{topic}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {/* Question-by-question review */}
              <div className="text-left max-w-xl mx-auto w-full space-y-3">
                <h4 className="text-zinc-300 font-semibold text-base uppercase tracking-widest mb-2">Question Review</h4>
                {state.history.map((h, idx) => (
                  <div key={idx} className={`p-4 rounded-2xl border-2 ${h.is_correct ? 'border-emerald-500/30 bg-emerald-500/5' : 'border-rose-500/30 bg-rose-500/5'}`}>
                    <p className="text-zinc-300 font-medium text-sm mb-2">Q{idx + 1}: {h.question}</p>
                    <p className="text-sm">
                      Your answer: <span className={h.is_correct ? 'text-emerald-400 font-medium' : 'text-rose-400 font-medium'}>{h.user_answer}</span>
                      {h.is_correct ? <CheckCircle2 className="inline w-4 h-4 ml-1 text-emerald-400" /> : <XCircle className="inline w-4 h-4 ml-1 text-rose-400" />}
                    </p>
                    {!h.is_correct && h.correct_answer && (
                      <p className="text-sm text-emerald-400 mt-1">✅ Correct answer: <span className="font-medium">{h.correct_answer}</span></p>
                    )}
                  </div>
                ))}
              </div>
 
              {state.finalReview.needs_remedial && (!state.finalReview.wrong_topics || state.finalReview.wrong_topics.length === 0) && (
                <div className="bg-amber-500/10 border-2 border-amber-500/20 rounded-2xl p-6 text-left max-w-xl mx-auto">
                  <p className="text-sm font-bold text-amber-500 uppercase tracking-widest mb-2 flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4" /> Adaptive Syllabus Update
                  </p>
                  <p className="text-base text-amber-400/90 leading-relaxed">
                    Added a remedial module on <strong className="text-amber-300">"{state.finalReview.remedial_topic}"</strong> to your learning path to help strengthen your foundation.
                  </p>
                </div>
              )}
            </div>
          )}
        </div>
 
        {/* Footer */}
        <div className="p-6 border-t border-zinc-800 bg-zinc-900/50 flex justify-end">
          {state.status === 'complete' ? (
            <button
              onClick={() => {
                handleClose();
                window.dispatchEvent(new CustomEvent('path_updated'));
              }}
              className="px-8 py-3.5 bg-zinc-100 hover:bg-white text-zinc-900 text-base font-semibold rounded-xl transition-colors shadow-lg"
            >
              Done & Continue Learning
            </button>
          ) : (
            <button
              onClick={() => handleSubmit()}
              disabled={!answer || state.status === 'evaluating'}
              className="px-8 py-3.5 bg-indigo-600 hover:bg-indigo-500 disabled:bg-zinc-800 disabled:text-zinc-500 text-white text-base font-semibold rounded-xl transition-all shadow-[0_0_15px_rgba(99,102,241,0.3)] hover:shadow-[0_0_25px_rgba(99,102,241,0.5)] disabled:shadow-none flex items-center gap-3"
            >
              {state.status === 'evaluating' ? (
                <>Evaluating <Loader2 className="w-5 h-5 animate-spin" /></>
              ) : (
                'Submit Answer'
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
