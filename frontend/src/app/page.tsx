"use client";

import { useState, useEffect, useCallback, Suspense } from "react";
import { useRouter } from "next/navigation";
import Chat from "@/components/Chat";
import SettingsPanel from "@/components/Settings";
import PendingActionsPanel from "@/components/PendingActions";
import OnboardingWizard, {
  isOnboardingDone,
} from "@/components/OnboardingWizard";
import {
  MessageSquare,
  Settings,
  Bot,
  ClipboardList,
  LogOut,
  Loader2,
  Shield,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { getMe, logout, type AuthUser } from "@/lib/auth";
import { getPendingActions, getSettings } from "@/lib/api";

type Tab = "chat" | "actions" | "settings";

export default function Home() {
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("chat");
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [pendingCount, setPendingCount] = useState(0);
  const [dryRun, setDryRun] = useState(true);
  const [environment, setEnvironment] = useState<string>("");

  const refreshMeta = useCallback(async () => {
    try {
      const [pending, settings] = await Promise.all([
        getPendingActions("pending").catch(() => []),
        getSettings().catch(() => null),
      ]);
      setPendingCount(Array.isArray(pending) ? pending.length : 0);
      if (settings) {
        setDryRun(!!settings.dry_run);
        setEnvironment(settings.environment || "");
      }
    } catch {
      /* non-fatal */
    }
  }, []);

  useEffect(() => {
    if (typeof window !== "undefined") {
      const params = new URLSearchParams(window.location.search);
      const t = params.get("tab");
      if (t === "settings" || t === "actions" || t === "chat") setTab(t);
      if (!isOnboardingDone()) setShowOnboarding(true);
    }
    (async () => {
      try {
        const me = await getMe();
        if (!me.authenticated) {
          router.replace("/login");
          return;
        }
        setUser(me);
        await refreshMeta();
      } catch {
        router.replace("/login");
      } finally {
        setLoading(false);
      }
    })();
  }, [router, refreshMeta]);

  // Keep the actions badge fresh while the user is in the app.
  useEffect(() => {
    if (loading) return;
    const id = window.setInterval(() => {
      void refreshMeta();
    }, 30_000);
    return () => window.clearInterval(id);
  }, [loading, refreshMeta]);

  useEffect(() => {
    if (tab === "actions") void refreshMeta();
  }, [tab, refreshMeta]);

  async function onLogout() {
    await logout();
    router.replace("/login");
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 dark:bg-slate-950">
        <Loader2 className="animate-spin text-rose-600" size={32} />
      </div>
    );
  }

  return (
    <div className="flex h-screen">
      {showOnboarding && (
        <OnboardingWizard
          onComplete={() => setShowOnboarding(false)}
          onGoSettings={() => {
            setShowOnboarding(false);
            setTab("settings");
          }}
        />
      )}

      <aside className="w-16 md:w-56 flex-shrink-0 border-r border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 flex flex-col">
        <div className="p-4 flex items-center gap-3 border-b border-slate-100 dark:border-slate-800">
          <div className="w-9 h-9 rounded-xl bg-rose-600 text-white flex items-center justify-center flex-shrink-0">
            <Bot size={20} />
          </div>
          <div className="hidden md:block min-w-0">
            <p className="font-semibold text-sm leading-tight">Rafaela</p>
            <p className="text-xs text-slate-500 truncate">
              {user?.name || user?.email || "AI Secretary"}
            </p>
          </div>
        </div>

        <nav className="flex-1 p-2 space-y-1">
          <button
            onClick={() => setTab("chat")}
            className={cn(
              "w-full flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors",
              tab === "chat"
                ? "bg-rose-50 dark:bg-rose-950/40 text-rose-700 dark:text-rose-300"
                : "text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800"
            )}
          >
            <MessageSquare size={18} />
            <span className="hidden md:inline">Chat</span>
          </button>
          <button
            onClick={() => setTab("actions")}
            className={cn(
              "w-full flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors",
              tab === "actions"
                ? "bg-rose-50 dark:bg-rose-950/40 text-rose-700 dark:text-rose-300"
                : "text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800"
            )}
          >
            <span className="relative">
              <ClipboardList size={18} />
              {pendingCount > 0 && (
                <span className="absolute -top-1.5 -right-1.5 min-w-[16px] h-4 px-1 rounded-full bg-amber-500 text-white text-[10px] font-semibold flex items-center justify-center">
                  {pendingCount > 9 ? "9+" : pendingCount}
                </span>
              )}
            </span>
            <span className="hidden md:inline flex-1 text-left">Ενέργειες</span>
            {pendingCount > 0 && (
              <span className="hidden md:inline-flex items-center justify-center min-w-[20px] h-5 px-1.5 rounded-full bg-amber-500 text-white text-[11px] font-semibold">
                {pendingCount}
              </span>
            )}
          </button>
          <button
            onClick={() => setTab("settings")}
            className={cn(
              "w-full flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors",
              tab === "settings"
                ? "bg-rose-50 dark:bg-rose-950/40 text-rose-700 dark:text-rose-300"
                : "text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800"
            )}
          >
            <Settings size={18} />
            <span className="hidden md:inline">Ρυθμίσεις</span>
          </button>
        </nav>

        <div className="p-2 border-t border-slate-100 dark:border-slate-800 space-y-1">
          {dryRun && (
            <div
              className="hidden md:flex items-start gap-2 rounded-lg bg-amber-50 dark:bg-amber-950/40 border border-amber-200/80 dark:border-amber-900 px-2.5 py-2 mb-1"
              title="Οι εγκεκριμένες εγγραφές προσομοιώνονται μέχρι να απενεργοποιηθεί το DRY_RUN"
            >
              <Shield size={14} className="text-amber-600 mt-0.5 flex-shrink-0" />
              <div className="min-w-0">
                <p className="text-[11px] font-semibold text-amber-800 dark:text-amber-200">
                  DRY_RUN ενεργό
                </p>
                <p className="text-[10px] text-amber-700/80 dark:text-amber-300/80 leading-snug">
                  HITL OK · χωρίς πραγματικά writes
                  {environment ? ` · ${environment}` : ""}
                </p>
              </div>
            </div>
          )}
          <button
            onClick={onLogout}
            className="w-full flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800"
          >
            <LogOut size={18} />
            <span className="hidden md:inline">Αποσύνδεση</span>
          </button>
          <button
            type="button"
            onClick={() => {
              localStorage.removeItem("rafaela_onboarding_done");
              setShowOnboarding(true);
            }}
            className="hidden md:block w-full text-[10px] text-slate-400 hover:text-slate-600 text-center py-1"
          >
            Επανάληψη onboarding
          </button>
          <p className="hidden md:block text-[10px] text-slate-400 text-center pt-1">
            GDPR · HITL
          </p>
        </div>
      </aside>

      <main className="flex-1 flex flex-col overflow-hidden">
        {tab === "chat" && (
          <Chat
            conversationId={conversationId}
            onConversationId={setConversationId}
            showSidebar
            onPendingChange={() => void refreshMeta()}
          />
        )}
        {tab === "actions" && (
          <PendingActionsPanel onChange={() => void refreshMeta()} />
        )}
        {tab === "settings" && (
          <Suspense
            fallback={
              <div className="flex justify-center py-16">
                <Loader2 className="animate-spin text-rose-600" size={28} />
              </div>
            }
          >
            <SettingsPanel />
          </Suspense>
        )}
      </main>
    </div>
  );
}
