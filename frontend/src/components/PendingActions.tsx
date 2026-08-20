"use client";

import { useEffect, useState, useCallback } from "react";
import { getPendingActions, getActionHistory, resolveAction } from "@/lib/api";
import { Check, X, Loader2, Clock, CheckCircle2, XCircle, AlertCircle, RefreshCw } from "lucide-react";
import { cn } from "@/lib/utils";

type Action = {
  id: string;
  action_type: string;
  description: string;
  status: string;
  result?: string | null;
  created_at?: string | null;
  resolved_at?: string | null;
};

const statusConfig: Record<string, { label: string; color: string; icon: typeof Clock }> = {
  pending: { label: "Σε αναμονή", color: "text-amber-600 bg-amber-50 dark:bg-amber-950/40", icon: Clock },
  approved: { label: "Εγκρίθηκε", color: "text-blue-600 bg-blue-50 dark:bg-blue-950/40", icon: CheckCircle2 },
  executed: { label: "Εκτελέστηκε", color: "text-emerald-600 bg-emerald-50 dark:bg-emerald-950/40", icon: CheckCircle2 },
  rejected: { label: "Απορρίφθηκε", color: "text-slate-500 bg-slate-100 dark:bg-slate-800", icon: XCircle },
  failed: { label: "Απέτυχε", color: "text-red-600 bg-red-50 dark:bg-red-950/40", icon: AlertCircle },
};

function formatDate(iso?: string | null) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("el-GR", {
      day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function actionTypeLabel(t: string) {
  const map: Record<string, string> = {
    ms_send_email: "Outlook · Αποστολή email",
    ms_create_event: "Outlook · Δημιουργία ραντεβού",
    google_send_email: "Gmail · Αποστολή email",
    google_create_event: "Google Calendar · Ραντεβού",
    knowledge_save_page: "Knowledge · Αποθήκευση σελίδας",
  };
  return map[t] || t;
}

export default function PendingActionsPanel() {
  const [pending, setPending] = useState<Action[]>([]);
  const [history, setHistory] = useState<Action[]>([]);
  const [loading, setLoading] = useState(true);
  const [resolving, setResolving] = useState<string | null>(null);
  const [tab, setTab] = useState<"pending" | "history">("pending");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [p, h] = await Promise.all([getPendingActions("pending"), getActionHistory()]);
      setPending(p);
      setHistory(h);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function handleResolve(id: string, approve: boolean) {
    setResolving(id);
    try {
      await resolveAction(id, approve);
      await load();
    } catch (e: any) {
      alert(e.message);
    } finally {
      setResolving(null);
    }
  }

  const list = tab === "pending" ? pending : history;

  return (
    <div className="max-w-3xl mx-auto p-6 space-y-6 h-full overflow-y-auto">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Ενέργειες</h1>
          <p className="text-slate-500 dark:text-slate-400 mt-1 text-sm">
            Έγκριση ή απόρριψη προτεινόμενων ενεργειών (Human-in-the-loop)
          </p>
        </div>
        <button
          onClick={load}
          className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-500"
          title="Ανανέωση"
        >
          <RefreshCw size={18} className={loading ? "animate-spin" : ""} />
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 p-1 bg-slate-100 dark:bg-slate-800 rounded-xl w-fit">
        <button
          onClick={() => setTab("pending")}
          className={cn(
            "px-4 py-1.5 rounded-lg text-sm font-medium transition-colors",
            tab === "pending"
              ? "bg-white dark:bg-slate-900 shadow-sm text-rose-700 dark:text-rose-300"
              : "text-slate-500 hover:text-slate-700"
          )}
        >
          Σε αναμονή {pending.length > 0 && (
            <span className="ml-1.5 inline-flex items-center justify-center w-5 h-5 text-xs rounded-full bg-amber-500 text-white">
              {pending.length}
            </span>
          )}
        </button>
        <button
          onClick={() => setTab("history")}
          className={cn(
            "px-4 py-1.5 rounded-lg text-sm font-medium transition-colors",
            tab === "history"
              ? "bg-white dark:bg-slate-900 shadow-sm text-rose-700 dark:text-rose-300"
              : "text-slate-500 hover:text-slate-700"
          )}
        >
          Ιστορικό
        </button>
      </div>

      {loading && list.length === 0 ? (
        <div className="flex justify-center py-16">
          <Loader2 className="animate-spin text-rose-600" size={28} />
        </div>
      ) : list.length === 0 ? (
        <div className="text-center py-16 text-slate-400">
          <Clock size={40} className="mx-auto mb-3 opacity-40" />
          <p className="text-sm">
            {tab === "pending"
              ? "Δεν υπάρχουν ενέργειες σε αναμονή."
              : "Δεν υπάρχει ιστορικό ενεργειών ακόμα."}
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {list.map((a) => {
            const cfg = statusConfig[a.status] || statusConfig.pending;
            const Icon = cfg.icon;
            return (
              <div
                key={a.id}
                className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-5 shadow-soft"
              >
                <div className="flex items-start justify-between gap-3 mb-3">
                  <div>
                    <p className="text-xs font-medium text-slate-400 uppercase tracking-wide">
                      {actionTypeLabel(a.action_type)}
                    </p>
                    <p className="text-xs text-slate-400 mt-0.5">{formatDate(a.created_at)}</p>
                  </div>
                  <span className={cn("inline-flex items-center gap-1 text-xs font-medium px-2.5 py-1 rounded-full", cfg.color)}>
                    <Icon size={12} />
                    {cfg.label}
                  </span>
                </div>

                <pre className="text-sm whitespace-pre-wrap text-slate-700 dark:text-slate-300 mb-3 font-sans">
                  {a.description}
                </pre>

                {a.result && a.status !== "pending" && (
                  <p className="text-xs text-slate-400 mb-3 border-t border-slate-100 dark:border-slate-800 pt-2">
                    Αποτέλεσμα: {a.result}
                  </p>
                )}

                {a.status === "pending" && (
                  <div className="flex gap-2 pt-1">
                    <button
                      onClick={() => handleResolve(a.id, true)}
                      disabled={resolving === a.id}
                      className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-medium px-3 py-1.5 transition-colors disabled:opacity-50"
                    >
                      {resolving === a.id ? <Loader2 className="animate-spin" size={14} /> : <Check size={14} />}
                      Έγκριση
                    </button>
                    <button
                      onClick={() => handleResolve(a.id, false)}
                      disabled={resolving === a.id}
                      className="inline-flex items-center gap-1.5 rounded-lg bg-slate-200 hover:bg-slate-300 dark:bg-slate-700 dark:hover:bg-slate-600 text-slate-800 dark:text-slate-100 text-xs font-medium px-3 py-1.5 transition-colors disabled:opacity-50"
                    >
                      <X size={14} />
                      Απόρριψη
                    </button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
