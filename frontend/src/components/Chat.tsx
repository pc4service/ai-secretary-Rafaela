"use client";

import { useState, useRef, useEffect } from "react";
import { Send, Loader2, Bot, User, Check, X } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  streamChat,
  resolveAction,
  getConversationMessages,
} from "@/lib/api";
import { cn } from "@/lib/utils";
import ConversationSidebar from "@/components/ConversationSidebar";

type Message = {
  role: "user" | "assistant";
  content: string;
  pendingActionId?: string | null;
  actionResolved?: string;
  streaming?: boolean;
};

type Props = {
  /** Controlled conversation from parent; if omitted, local state is used */
  conversationId?: string | null;
  onConversationId?: (id: string | null) => void;
  showSidebar?: boolean;
  /** Fired when a HITL pending action is created or resolved (sidebar badge). */
  onPendingChange?: () => void;
};

export default function Chat({
  conversationId: controlledId,
  onConversationId,
  showSidebar = true,
  onPendingChange,
}: Props) {
  const [localConvId, setLocalConvId] = useState<string | null>(null);
  const conversationId =
    controlledId !== undefined ? controlledId : localConvId;

  function setConversationId(id: string | null) {
    if (onConversationId) onConversationId(id);
    else setLocalConvId(id);
  }

  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      content:
        "Γεια σου! Είμαι η Rafaela, η AI Executive Secretary σου. Πώς μπορώ να σε βοηθήσω σήμερα; Μπορώ να διαχειριστώ ημερολόγιο, emails, tasks και έρευνα – πάντα με σεβασμό στο GDPR και με επιβεβαίωση πριν από κάθε σημαντική ενέργεια.",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [resolving, setResolving] = useState<string | null>(null);
  const [sidebarKey, setSidebarKey] = useState(0);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, status]);

  // Load history when selecting an existing conversation
  useEffect(() => {
    if (!conversationId) return;
    let cancelled = false;
    (async () => {
      try {
        const rows = await getConversationMessages(conversationId);
        if (cancelled || !Array.isArray(rows) || rows.length === 0) return;
        setMessages(
          rows.map((m: any) => ({
            role: m.role === "assistant" ? "assistant" : "user",
            content: m.content,
            pendingActionId: m.pending_action_id || null,
          }))
        );
      } catch {
        /* keep welcome */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [conversationId]);

  async function handleSend(e?: React.FormEvent) {
    e?.preventDefault();
    const text = input.trim();
    if (!text || loading) return;

    const userMsg: Message = { role: "user", content: text };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);
    setStatus("Σύνδεση…");

    // Placeholder assistant bubble for streaming
    setMessages((prev) => [
      ...prev,
      { role: "assistant", content: "", streaming: true },
    ]);

    const history = messages
      .filter((m) => m.role === "user" || m.role === "assistant")
      .map((m) => ({ role: m.role, content: m.content }));

    try {
      await streamChat(text, history, conversationId, {
        onStatus: (msg) => setStatus(msg),
        onDelta: (chunk) => {
          setStatus(null);
          setMessages((prev) => {
            const next = [...prev];
            const last = next[next.length - 1];
            if (last?.role === "assistant" && last.streaming) {
              next[next.length - 1] = {
                ...last,
                content: last.content + chunk,
              };
            }
            return next;
          });
        },
        onDone: (data) => {
          if (data.conversation_id) {
            setConversationId(data.conversation_id);
            setSidebarKey((k) => k + 1);
          }
          setMessages((prev) => {
            const next = [...prev];
            const last = next[next.length - 1];
            if (last?.role === "assistant") {
              next[next.length - 1] = {
                role: "assistant",
                content:
                  data.reply || last.content || "Δεν μπόρεσα να απαντήσω.",
                pendingActionId: data.pending_action_id || null,
                streaming: false,
              };
            }
            return next;
          });
          if (data.pending_action_id) onPendingChange?.();
          setStatus(null);
        },
        onError: (message) => {
          setMessages((prev) => {
            const next = [...prev];
            const last = next[next.length - 1];
            if (last?.role === "assistant" && last.streaming) {
              next[next.length - 1] = {
                role: "assistant",
                content: `Σφάλμα: ${message}`,
                streaming: false,
              };
            } else {
              next.push({
                role: "assistant",
                content: `Σφάλμα: ${message}`,
              });
            }
            return next;
          });
          setStatus(null);
        },
      });
    } catch (err: any) {
      setMessages((prev) => {
        const next = [...prev];
        const last = next[next.length - 1];
        if (last?.role === "assistant" && last.streaming) {
          next[next.length - 1] = {
            role: "assistant",
            content: `Σφάλμα: ${err.message}. Βεβαιώσου ότι το backend τρέχει και έχει OPENAI_API_KEY.`,
            streaming: false,
          };
        } else {
          next.push({
            role: "assistant",
            content: `Σφάλμα: ${err.message}`,
          });
        }
        return next;
      });
      setStatus(null);
    } finally {
      setLoading(false);
    }
  }

  async function handleResolve(
    actionId: string,
    approve: boolean,
    msgIndex: number
  ) {
    setResolving(actionId);
    try {
      const result = await resolveAction(actionId, approve);
      const resultText = String(result.result || "");
      const isDryRun = /dry[_-]?run/i.test(resultText) || /Would create|Would send/i.test(resultText);
      setMessages((prev) => {
        const next = [...prev];
        const msg = { ...next[msgIndex] };
        msg.actionResolved = result.status;
        msg.pendingActionId = null;
        if (approve) {
          const verb =
            result.status === "executed"
              ? isDryRun
                ? "προσομοιώθηκε (DRY_RUN)"
                : "εκτελέστηκε"
              : "εγκρίθηκε";
          msg.content += `\n\n✅ Ενέργεια ${verb}. ${resultText}`;
        } else {
          msg.content += "\n\n❌ Ενέργεια απορρίφθηκε.";
        }
        next[msgIndex] = msg;
        return next;
      });
      onPendingChange?.();
    } catch (err: any) {
      alert(err.message);
    } finally {
      setResolving(null);
    }
  }

  function onSelectConversation(id: string | null) {
    setConversationId(id);
    if (id === null) {
      setMessages([
        {
          role: "assistant",
          content: "Νέα συνομιλία. Πώς μπορώ να σε βοηθήσω;",
        },
      ]);
    }
  }

  return (
    <div className="flex h-full min-h-0">
      {showSidebar && (
        <div className="hidden sm:flex flex-shrink-0">
          <ConversationSidebar
            activeId={conversationId}
            onSelect={onSelectConversation}
            refreshKey={sidebarKey}
          />
        </div>
      )}

      <div className="flex flex-col h-full flex-1 min-w-0">
        <div className="flex-1 overflow-y-auto px-4 py-6 space-y-4">
          {messages.map((m, i) => (
            <div
              key={i}
              className={cn(
                "flex gap-3 max-w-3xl",
                m.role === "user" ? "ml-auto flex-row-reverse" : ""
              )}
            >
              <div
                className={cn(
                  "flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center",
                  m.role === "assistant"
                    ? "bg-rose-600 text-white"
                    : "bg-slate-200 dark:bg-slate-700"
                )}
              >
                {m.role === "assistant" ? <Bot size={16} /> : <User size={16} />}
              </div>
              <div className="space-y-2">
                <div
                  className={cn(
                    "rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-soft",
                    m.role === "assistant"
                      ? "bg-white dark:bg-slate-800 border border-slate-100 dark:border-slate-700"
                      : "bg-rose-600 text-white"
                  )}
                >
                  {m.role === "assistant" ? (
                    m.streaming ? (
                      <p className="whitespace-pre-wrap">
                        {m.content.replace(
                          /\[PENDING_ACTION:[a-f0-9\-]+\]\n?/g,
                          ""
                        )}
                        <span className="inline-block w-1.5 h-4 ml-0.5 bg-rose-500 animate-pulse align-middle" />
                      </p>
                    ) : (
                      <div className="prose prose-sm dark:prose-invert max-w-none prose-p:my-2 prose-ul:my-2 prose-ol:my-2 prose-li:my-0.5 prose-headings:mt-4 prose-headings:mb-2 prose-pre:bg-slate-100 dark:prose-pre:bg-slate-900 prose-pre:rounded-lg prose-code:text-rose-600 dark:prose-code:text-rose-400 prose-table:text-xs prose-a:text-rose-600">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                          {m.content.replace(
                            /\[PENDING_ACTION:[a-f0-9\-]+\]\n?/g,
                            ""
                          )}
                        </ReactMarkdown>
                      </div>
                    )
                  ) : (
                    <p className="whitespace-pre-wrap">{m.content}</p>
                  )}
                </div>
                {m.pendingActionId && !m.actionResolved && (
                  <div className="flex gap-2 pl-1">
                    <button
                      type="button"
                      disabled={resolving === m.pendingActionId}
                      onClick={() =>
                        handleResolve(m.pendingActionId!, true, i)
                      }
                      className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-medium px-3 py-1.5 transition-colors disabled:opacity-50"
                    >
                      {resolving === m.pendingActionId ? (
                        <Loader2 size={14} className="animate-spin" />
                      ) : (
                        <Check size={14} />
                      )}
                      Έγκριση
                    </button>
                    <button
                      type="button"
                      disabled={resolving === m.pendingActionId}
                      onClick={() =>
                        handleResolve(m.pendingActionId!, false, i)
                      }
                      className="inline-flex items-center gap-1.5 rounded-lg bg-slate-200 hover:bg-slate-300 dark:bg-slate-700 dark:hover:bg-slate-600 text-slate-800 dark:text-slate-100 text-xs font-medium px-3 py-1.5 transition-colors disabled:opacity-50"
                    >
                      <X size={14} />
                      Απόρριψη
                    </button>
                  </div>
                )}
              </div>
            </div>
          ))}
          {status && (
            <p className="text-xs text-slate-400 flex items-center gap-2 px-2">
              <Loader2 size={12} className="animate-spin" /> {status}
            </p>
          )}
          <div ref={bottomRef} />
        </div>

        <div className="border-t border-slate-200 dark:border-slate-800 bg-white/80 dark:bg-slate-900/80 backdrop-blur p-4">
          <form onSubmit={handleSend} className="flex gap-3 max-w-3xl mx-auto">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Γράψε μήνυμα… (π.χ. «Στείλε email στον Γιάννη» ή «Τι έχω αύριο;»)"
              className="flex-1 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-rose-500 focus:border-transparent"
              disabled={loading}
            />
            <button
              type="submit"
              disabled={loading || !input.trim()}
              className="rounded-xl bg-rose-600 hover:bg-rose-700 disabled:opacity-50 text-white px-4 py-3 transition-colors"
            >
              {loading ? (
                <Loader2 size={18} className="animate-spin" />
              ) : (
                <Send size={18} />
              )}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
