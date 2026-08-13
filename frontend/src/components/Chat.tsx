"use client";

import { useState, useRef, useEffect } from "react";
import { Send, Loader2, Bot, User, Check, X } from "lucide-react";
import { chat, resolveAction } from "@/lib/api";
import { cn } from "@/lib/utils";

type Message = {
  role: "user" | "assistant";
  content: string;
  pendingActionId?: string | null;
  actionResolved?: string;
};

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      content:
        "Γεια σου! Είμαι η Rafaela, η AI Executive Secretary σου. Πώς μπορώ να σε βοηθήσω σήμερα; Μπορώ να διαχειριστώ ημερολόγιο, emails, tasks και έρευνα – πάντα με σεβασμό στο GDPR και με επιβεβαίωση πριν από κάθε σημαντική ενέργεια.",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [resolving, setResolving] = useState<string | null>(null);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function handleSend(e?: React.FormEvent) {
    e?.preventDefault();
    const text = input.trim();
    if (!text || loading) return;

    const userMsg: Message = { role: "user", content: text };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const history = messages
        .filter((m) => m.role === "user" || m.role === "assistant")
        .map((m) => ({ role: m.role, content: m.content }));
      const data = await chat(text, history, conversationId);
      if (data.conversation_id) setConversationId(data.conversation_id);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: data.reply || "Δεν μπόρεσα να απαντήσω.",
          pendingActionId: data.pending_action_id || null,
        },
      ]);
    } catch (err: any) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: `Σφάλμα: ${err.message}. Βεβαιώσου ότι το backend τρέχει και έχει OPENAI_API_KEY.`,
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  async function handleResolve(actionId: string, approve: boolean, msgIndex: number) {
    setResolving(actionId);
    try {
      const result = await resolveAction(actionId, approve);
      setMessages((prev) => {
        const next = [...prev];
        const msg = { ...next[msgIndex] };
        msg.actionResolved = result.status;
        msg.pendingActionId = null;
        if (approve) {
          msg.content += `\n\n✅ Ενέργεια ${result.status === "executed" ? "εκτελέστηκε" : "εγκρίθηκε"}. ${result.result || ""}`;
        } else {
          msg.content += "\n\n❌ Ενέργεια απορρίφθηκε.";
        }
        next[msgIndex] = msg;
        return next;
      });
    } catch (err: any) {
      alert(err.message);
    } finally {
      setResolving(null);
    }
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto px-4 py-6 space-y-4">
        {messages.map((m, i) => (
          <div
            key={i}
            className={cn("flex gap-3 max-w-3xl", m.role === "user" ? "ml-auto flex-row-reverse" : "")}
          >
            <div
              className={cn(
                "flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center",
                m.role === "assistant" ? "bg-rose-600 text-white" : "bg-slate-200 dark:bg-slate-700"
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
                <p className="whitespace-pre-wrap">
                  {m.content.replace(/\[PENDING_ACTION:[a-f0-9\-]+\]\n?/g, "")}
                </p>
              </div>

              {m.pendingActionId && !m.actionResolved && (
                <div className="flex gap-2 pl-1">
                  <button
                    onClick={() => handleResolve(m.pendingActionId!, true, i)}
                    disabled={resolving === m.pendingActionId}
                    className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-medium px-3 py-1.5 transition-colors disabled:opacity-50"
                  >
                    {resolving === m.pendingActionId ? (
                      <Loader2 className="animate-spin" size={14} />
                    ) : (
                      <Check size={14} />
                    )}
                    Έγκριση
                  </button>
                  <button
                    onClick={() => handleResolve(m.pendingActionId!, false, i)}
                    disabled={resolving === m.pendingActionId}
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
        {loading && (
          <div className="flex gap-3 max-w-3xl">
            <div className="w-8 h-8 rounded-full bg-rose-600 text-white flex items-center justify-center">
              <Bot size={16} />
            </div>
            <div className="rounded-2xl px-4 py-3 bg-white dark:bg-slate-800 border border-slate-100 dark:border-slate-700">
              <Loader2 className="animate-spin text-rose-600" size={18} />
            </div>
          </div>
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
            <Send size={18} />
          </button>
        </form>
      </div>
    </div>
  );
}
