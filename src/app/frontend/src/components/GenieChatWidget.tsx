import { Send, Sparkles } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { api } from '../lib/api';

type AskResponse = Awaited<ReturnType<typeof api.genieAsk>>;

type Msg =
  | { role: 'user'; content: string; ts: number }
  | { role: 'assistant'; content: string; sql?: string | null;
      result?: AskResponse['query_result']; error?: string | null; ts: number };

const FALLBACK_QUESTIONS: string[] = [
  '¿Cuál es la disponibilidad en anaquel por categoría?',
  '¿Qué puntos de venta tienen la peor ejecución esta hora?',
  '¿Cuál es el share of shelf de nuestras marcas por país?',
  '¿Qué SKUs están agotados en más puntos de venta?',
  '¿Cómo se compara nuestro índice de precio con la competencia por cadena?',
];

export default function GenieChatWidget() {
  // A aba Genie é sempre utilizável: 'live' fala com uma sala real; 'demo' usa
  // respostas pré-configuradas (sem precisar de Genie Space).
  const [mode, setMode] = useState<'demo' | 'live'>('demo');
  const [questions, setQuestions] = useState<string[]>(FALLBACK_QUESTIONS);
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [convId, setConvId] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.genieSpace()
      .then((r) => {
        setMode(r.mode ?? (r.space_id ? 'live' : 'demo'));
        if (r.suggested_questions?.length) setQuestions(r.suggested_questions);
      })
      .catch(() => setMode('demo'));
  }, []);

  // Autoscroll to bottom when new messages arrive
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, busy]);

  async function send(q?: string) {
    const content = (q ?? input).trim();
    if (!content || busy) return;
    setInput('');
    setMessages((m) => [...m, { role: 'user', content, ts: Date.now() }]);
    setBusy(true);
    try {
      const resp = await api.genieAsk(content, convId ?? undefined);
      if (!convId) setConvId(resp.conversation_id);
      setMessages((m) => [...m, {
        role: 'assistant',
        content: resp.text || (resp.error ? '' : 'Genie respondió pero sin texto.'),
        sql: resp.sql,
        result: resp.query_result,
        error: resp.error,
        ts: Date.now(),
      }]);
    } catch (e: any) {
      setMessages((m) => [...m, {
        role: 'assistant',
        content: '',
        error: e?.message ?? String(e),
        ts: Date.now(),
      }]);
    } finally {
      setBusy(false);
    }
  }

  function newConversation() {
    setMessages([]);
    setConvId(null);
    setInput('');
  }

  return (
    <>
      {/* Floating button */}
      <button
        onClick={() => setOpen((o) => !o)}
        aria-label={open ? 'Cerrar Genie' : 'Abrir Genie'}
        className={[
          'fixed z-50 bottom-6 right-6 w-14 h-14 rounded-full',
          'flex items-center justify-center',
          'shadow-[0_8px_30px_-4px_rgba(51,189,238,0.55),0_0_0_1px_rgba(51,189,238,0.4)]',
          'bg-gradient-to-br from-amber-400 to-orange-500 text-black',
          'hover:scale-105 active:scale-95 transition-transform',
        ].join(' ')}
      >
        {open ? '×' : <Sparkles className="w-6 h-6" strokeWidth={2} />}
      </button>

      {/* Panel */}
      {open && (
        <>
          <div
            className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm"
            onClick={() => setOpen(false)}
          />
          <div
            className={[
              'fixed z-50 bottom-24 right-6',
              'w-[min(620px,94vw)] h-[min(760px,82vh)]',
              'bg-nieve border border-marco rounded-2xl',
              'shadow-[0_30px_80px_-20px_rgba(0,0,0,0.7)]',
              'overflow-hidden flex flex-col',
              'animate-slide-in-right',
            ].join(' ')}
          >
            {/* Header */}
            <header className="flex items-center justify-between px-4 py-3 border-b border-marco bg-nieve">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg flex items-center justify-center bg-gradient-to-br from-amber-400 to-orange-500 text-black">
                  <Sparkles className="w-4 h-4" strokeWidth={2.5} />
                </div>
                <div className="leading-tight">
                  <div className="text-sm font-bold text-tinta flex items-center gap-2">
                    Genie · dichter & neira
                    {mode === 'demo' && (
                      <span className="text-[9px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded bg-dn-400/15 text-dn-600 border border-dn-400/30">
                        modo demostración
                      </span>
                    )}
                  </div>
                  <div className="text-[10px] uppercase tracking-widest text-humo">
                    pregunta en español · NL → SQL
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-1">
                {messages.length > 0 && (
                  <button
                    onClick={newConversation}
                    className="text-[11px] text-humo hover:text-tinta px-2 py-1"
                    disabled={busy}
                  >
                    nueva conversación
                  </button>
                )}
                <button
                  onClick={() => setOpen(false)}
                  className="text-humo hover:text-grafito text-xl leading-none w-8 h-8 flex items-center justify-center"
                  aria-label="Cerrar"
                >
                  ×
                </button>
              </div>
            </header>

            {/* Messages */}
            <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
              {messages.length === 0 && (
                <div>
                  <div className="text-center py-6">
                    <div className="text-xl font-semibold text-tinta mb-1">
                      Pregunta sobre la operación
                    </div>
                    <div className="text-[11px] text-humo">
                      {mode === 'demo'
                        ? 'modo demostración · respuestas preconfiguradas en español'
                        : 'las respuestas vienen del data lake en vivo · en español'}
                    </div>
                  </div>
                  <div className="text-[10px] uppercase tracking-widest text-humo mb-2 px-1">
                    Sugerencias
                  </div>
                  <div className="space-y-2">
                    {questions.map((q) => (
                      <button
                        key={q}
                        onClick={() => send(q)}
                        className="w-full text-left px-3 py-2 rounded-lg bg-white hover:bg-white border border-marco hover:border-marco text-[13px] text-tinta transition-colors"
                      >
                        {q}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {messages.map((m, i) => <MessageBubble key={i} msg={m} />)}

              {busy && (
                <div className="flex items-center gap-2 text-[12px] text-humo px-2">
                  <span className="inline-block w-2 h-2 rounded-full bg-dn-400 animate-pulse" />
                  Genie está consultando…
                </div>
              )}
            </div>

            {/* Input */}
            <div className="border-t border-marco p-3 bg-nieve">
              <form
                onSubmit={(e) => { e.preventDefault(); send(); }}
                className="flex items-center gap-2"
              >
                <input
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder={busy ? 'esperando respuesta…' : 'pregunta en español…'}
                  disabled={busy}
                  className="flex-1 bg-white border border-marco rounded-lg px-3 py-2 text-[13px] text-tinta placeholder:text-humo focus:border-dn-400 focus:outline-none disabled:opacity-50"
                />
                <button
                  type="submit"
                  disabled={busy || !input.trim()}
                  className="w-10 h-10 rounded-lg bg-dn-400 text-black flex items-center justify-center hover:bg-amber-300 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                  aria-label="Enviar"
                >
                  <Send className="w-4 h-4" strokeWidth={2.5} />
                </button>
              </form>
            </div>
          </div>
        </>
      )}
    </>
  );
}

// ---- MessageBubble ----------------------------------------------------------
function MessageBubble({ msg }: { msg: Msg }) {
  if (msg.role === 'user') {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] rounded-2xl rounded-br-md bg-dn-400 text-black px-3.5 py-2 text-[13px] whitespace-pre-wrap">
          {msg.content}
        </div>
      </div>
    );
  }
  return (
    <div className="flex justify-start">
      <div className="max-w-[88%] space-y-2">
        {msg.content && (
          <div className="rounded-2xl rounded-bl-md bg-white border border-marco text-tinta px-3.5 py-2.5 text-[13px] leading-relaxed whitespace-pre-wrap">
            {msg.content}
          </div>
        )}
        {msg.error && (
          <div className="rounded-lg bg-red-500/10 border border-red-500/30 text-red-600 text-[12px] px-3 py-2">
            ⚠ {msg.error}
          </div>
        )}
        {msg.sql && <SqlBlock sql={msg.sql} />}
        {msg.result && <QueryResultBlock result={msg.result} />}
      </div>
    </div>
  );
}

function SqlBlock({ sql }: { sql: string }) {
  const [open, setOpen] = useState(false);
  return (
    <details open={open} onToggle={(e) => setOpen((e.target as HTMLDetailsElement).open)}
             className="rounded-lg bg-lienzo border border-marco">
      <summary className="text-[10px] uppercase tracking-widest text-humo px-3 py-1.5 cursor-pointer hover:text-grafito list-none flex items-center justify-between">
        <span>SQL generado</span>
        <span className="text-humo">{open ? '▴' : '▾'}</span>
      </summary>
      <pre className="text-[11px] font-mono text-grafito px-3 pb-3 pt-1 overflow-x-auto whitespace-pre">
        {sql}
      </pre>
    </details>
  );
}

type QueryResult = NonNullable<AskResponse['query_result']>;

function QueryResultBlock({ result }: { result: QueryResult }) {
  if (!result || !result.columns?.length) return null;
  const rows = result.rows ?? [];
  return (
    <div className="rounded-lg bg-lienzo border border-marco overflow-hidden">
      <div className="text-[10px] uppercase tracking-widest text-humo px-3 py-1.5 border-b border-marco flex items-center justify-between">
        <span>Resultado</span>
        <span className="text-humo tabular-nums">{result.row_count} fila{result.row_count !== 1 ? 's' : ''}{result.truncated && ' (50 mostradas)'}</span>
      </div>
      <div className="overflow-x-auto max-h-[280px] overflow-y-auto">
        <table className="w-full text-[12px]">
          <thead className="bg-nieve sticky top-0">
            <tr>
              {result.columns.map((c: string) => (
                <th key={c} className="text-left text-[10px] uppercase tracking-widest text-humo px-3 py-1.5 font-medium">
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row: any[], i: number) => (
              <tr key={i} className="border-t border-marco">
                {row.map((cell: any, j: number) => (
                  <td key={j} className="px-3 py-1.5 text-tinta tabular-nums whitespace-nowrap">
                    {formatCell(cell)}
                  </td>
                ))}
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={result.columns.length} className="px-3 py-4 text-center text-humo text-[12px]">
                  sin filas
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function formatCell(v: any): string {
  if (v == null) return '—';
  if (typeof v === 'number') return v.toLocaleString('es-CO');
  // try to format ISO timestamps
  if (typeof v === 'string' && /^\d{4}-\d{2}-\d{2}T/.test(v)) {
    try {
      const d = new Date(v);
      return d.toLocaleString('es-CO', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
    } catch { return v; }
  }
  return String(v);
}
