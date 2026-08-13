"use client";

import { useEffect, useState } from "react";
import {
  getSettings,
  getMicrosoftAuthUrl,
  getGoogleAuthUrl,
  disconnectMicrosoft,
  disconnectGoogle,
} from "@/lib/api";
import { CheckCircle2, XCircle, Link2, Unlink, Shield, KeyRound, Loader2 } from "lucide-react";

type ConfigFlags = {
  llm: boolean;
  llm_provider: string;
  llm_model: string;
  microsoft_oauth: boolean;
  google_oauth: boolean;
  firecrawl: boolean;
  microsoft_scopes?: string[] | null;
  microsoft_scopes_missing?: string[] | null;
  microsoft_scopes_extra?: string[] | null;
  microsoft_token_expires_at?: string | null;
};

type SettingsData = {
  microsoft_connected: boolean;
  google_connected: boolean;
  dry_run: boolean;
  retention_days: number;
  environment: string;
  config?: ConfigFlags;
};

function Flag({ ok, missingLabel }: { ok: boolean; missingLabel?: string }) {
  return ok ? (
    <span className="inline-flex items-center gap-1 text-emerald-600 text-xs font-medium">
      <CheckCircle2 size={14} /> Ρυθμισμένο
    </span>
  ) : (
    <span className="inline-flex items-center gap-1 text-slate-400 text-xs font-medium">
      <XCircle size={14} /> {missingLabel || "Δεν έχει ρυθμιστεί"}
    </span>
  );
}

export default function SettingsPanel() {
  const [data, setData] = useState<SettingsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  async function load() {
    try {
      const s = await getSettings();
      setData(s);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function connectMs() {
    setActionLoading("ms");
    try {
      const { auth_url } = await getMicrosoftAuthUrl();
      window.location.href = auth_url;
    } catch (e: any) {
      alert(e.message);
    } finally {
      setActionLoading(null);
    }
  }

  async function connectGoogle() {
    setActionLoading("google");
    try {
      const { auth_url } = await getGoogleAuthUrl();
      window.location.href = auth_url;
    } catch (e: any) {
      alert(e.message);
    } finally {
      setActionLoading(null);
    }
  }

  async function disconnectMs() {
    setActionLoading("ms-disc");
    await disconnectMicrosoft();
    await load();
    setActionLoading(null);
  }

  async function disconnectGoogle() {
    setActionLoading("google-disc");
    await disconnectGoogle();
    await load();
    setActionLoading(null);
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="animate-spin text-rose-600" size={28} />
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto p-6 space-y-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Ρυθμίσεις</h1>
        <p className="text-slate-500 dark:text-slate-400 mt-1 text-sm">
          Σύνδεσε λογαριασμούς και διαχειρίσου τα δεδομένα σου (GDPR).
        </p>
      </div>

      {/* Status cards */}
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-5 shadow-soft">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-medium">Microsoft 365</h2>
            {data?.microsoft_connected ? (
              <CheckCircle2 className="text-emerald-500" size={20} />
            ) : (
              <XCircle className="text-slate-400" size={20} />
            )}
          </div>
          <p className="text-sm text-slate-500 mb-4">
            Outlook Mail & Calendar
          </p>
          {data?.microsoft_connected && data?.config?.microsoft_scopes && (
            <p className="text-xs text-slate-400 mb-3">
              Scopes: {data.config.microsoft_scopes.join(", ")}
            </p>
          )}
          {data?.microsoft_connected &&
            !!((data?.config?.microsoft_scopes_missing?.length ?? 0) +
              (data?.config?.microsoft_scopes_extra?.length ?? 0)) && (
              <p className="text-xs text-amber-600 mb-3">
                Τα παραχωρημένα δικαιώματα διαφέρουν από τα απαιτούμενα — κάνε
                Αποσύνδεση και ξανά Σύνδεση.
              </p>
            )}
          {data?.microsoft_connected ? (
            <button
              onClick={disconnectMs}
              disabled={actionLoading === "ms-disc"}
              className="inline-flex items-center gap-2 text-sm text-red-600 hover:text-red-700"
            >
              <Unlink size={16} /> Αποσύνδεση
            </button>
          ) : (
            <div>
              <button
                onClick={connectMs}
                disabled={!!actionLoading || data?.config?.microsoft_oauth === false}
                className="inline-flex items-center gap-2 rounded-lg bg-rose-600 hover:bg-rose-700 text-white text-sm px-4 py-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {actionLoading === "ms" ? (
                  <Loader2 className="animate-spin" size={16} />
                ) : (
                  <Link2 size={16} />
                )}
                Σύνδεση Microsoft
              </button>
              {data?.config && !data.config.microsoft_oauth && (
                <p className="mt-2 text-xs text-amber-600">
                  Λείπουν MS_CLIENT_ID / MS_CLIENT_SECRET στο backend (.env)
                </p>
              )}
            </div>
          )}
        </div>

        <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-5 shadow-soft">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-medium">Google Workspace</h2>
            {data?.google_connected ? (
              <CheckCircle2 className="text-emerald-500" size={20} />
            ) : (
              <XCircle className="text-slate-400" size={20} />
            )}
          </div>
          <p className="text-sm text-slate-500 mb-4">Gmail & Google Calendar</p>
          {data?.google_connected ? (
            <button
              onClick={disconnectGoogle}
              disabled={actionLoading === "google-disc"}
              className="inline-flex items-center gap-2 text-sm text-red-600 hover:text-red-700"
            >
              <Unlink size={16} /> Αποσύνδεση
            </button>
          ) : (
            <div>
              <button
                onClick={connectGoogle}
                disabled={!!actionLoading || data?.config?.google_oauth === false}
                className="inline-flex items-center gap-2 rounded-lg bg-rose-600 hover:bg-rose-700 text-white text-sm px-4 py-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {actionLoading === "google" ? (
                  <Loader2 className="animate-spin" size={16} />
                ) : (
                  <Link2 size={16} />
                )}
                Σύνδεση Google
              </button>
              {data?.config && !data.config.google_oauth && (
                <p className="mt-2 text-xs text-amber-600">
                  Λείπουν GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET στο backend (.env)
                </p>
              )}
            </div>
          )}
        </div>
      </div>

      {/* API keys / feature flags */}
      <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-5 shadow-soft">
        <div className="flex items-center gap-2 mb-4">
          <KeyRound className="text-rose-600" size={20} />
          <h2 className="font-medium">Διαθέσιμα κλειδιά (backend)</h2>
        </div>
        <dl className="space-y-3 text-sm">
          <div className="flex justify-between">
            <dt className="text-slate-500">
              LLM · {data?.config?.llm_provider} ({data?.config?.llm_model})
            </dt>
            <dd>
              <Flag ok={!!data?.config?.llm} />
            </dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-slate-500">Microsoft 365 OAuth</dt>
            <dd>
              <Flag ok={!!data?.config?.microsoft_oauth} />
            </dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-slate-500">Google OAuth</dt>
            <dd>
              <Flag ok={!!data?.config?.google_oauth} />
            </dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-slate-500">Firecrawl (web research)</dt>
            <dd>
              <Flag ok={!!data?.config?.firecrawl} missingLabel="Λείπει (προαιρετικό)" />
            </dd>
          </div>
        </dl>
        <p className="mt-4 text-xs text-slate-400 leading-relaxed">
          Τα flags δείχνουν μόνο αν υπάρχει ρύθμιση στο backend — οι τιμές των
          κλειδιών δεν αποκαλύπτονται ποτέ στο frontend.
        </p>
      </div>

      {/* GDPR & Privacy */}
      <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-5 shadow-soft">
        <div className="flex items-center gap-2 mb-4">
          <Shield className="text-rose-600" size={20} />
          <h2 className="font-medium">GDPR & Απορρήτο</h2>
        </div>
        <dl className="space-y-3 text-sm">
          <div className="flex justify-between">
            <dt className="text-slate-500">Περιβάλλον</dt>
            <dd className="font-medium">{data?.environment}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-slate-500">Dry-run mode</dt>
            <dd className="font-medium">
              {data?.dry_run ? (
                <span className="text-amber-600">Ενεργό (ασφαλές δοκιμές)</span>
              ) : (
                <span className="text-emerald-600">Απενεργοποιημένο</span>
              )}
            </dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-slate-500">Διατήρηση δεδομένων</dt>
            <dd className="font-medium">{data?.retention_days} ημέρες</dd>
          </div>
        </dl>
        <p className="mt-4 text-xs text-slate-400 leading-relaxed">
          Όλες οι ενέργειες εγγραφής (αποστολή email, δημιουργία ραντεβού) απαιτούν
          ρητή επιβεβαίωση. Σε dry-run mode δεν εκτελούνται πραγματικές αλλαγές.
          Μπορείς να ζητήσεις εξαγωγή ή διαγραφή των δεδομένων σου μέσω του chat.
        </p>
      </div>
    </div>
  );
}
