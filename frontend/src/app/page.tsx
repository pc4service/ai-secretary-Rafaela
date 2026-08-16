"use client";

import { useState, useEffect } from "react";
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
} from "lucide-react";
import { cn } from "@/lib/utils";
import { getMe, logout, type AuthUser } from "@/lib/auth";

type Tab = "chat" | "actions" | "settings";

export default function Home() {
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("chat");
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);

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
      } catch {
        router.replace("/login");
      } finally {
        setLoading(false);
      }
    })();
  }, [router]);

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
            <ClipboardList size={18} />
            <span className="hidden md:inline">Ενέργειες</span>
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
            GDPR · Streaming chat
          </p>
        </div>
      </aside>

      <main className="flex-1 flex flex-col overflow-hidden">
        {tab === "chat" && (
          <Chat
            conversationId={conversationId}
            onConversationId={setConversationId}
            showSidebar
          />
        )}
        {tab === "actions" && <PendingActionsPanel />}
        {tab === "settings" && <SettingsPanel />}
      </main>
    </div>
  );
}
