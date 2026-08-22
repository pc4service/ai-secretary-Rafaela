"use client";

import { useState } from "react";
import { toast } from "sonner";
import {
  Bot,
  Calendar,
  Shield,
  MessageSquare,
  ChevronRight,
  ChevronLeft,
  Check,
  X,
} from "lucide-react";
import { getMicrosoftAuthUrl, getGoogleAuthUrl } from "@/lib/api";

const STORAGE_KEY = "rafaela_onboarding_done";

export function isOnboardingDone(): boolean {
  if (typeof window === "undefined") return true;
  return localStorage.getItem(STORAGE_KEY) === "1";
}

export function markOnboardingDone() {
  localStorage.setItem(STORAGE_KEY, "1");
}

type Props = {
  onComplete: () => void;
  onGoSettings?: () => void;
};

const STEPS = [
  {
    id: "welcome",
    title: "Καλώς ήρθες στη Rafaela",
    body: "Είμαι η AI Executive Secretary σου. Βοηθάω με ημερολόγιο, email, πρότυπα και έρευνα — πάντα με GDPR και επιβεβαίωση πριν από κάθε σημαντική ενέργεια.",
    icon: Bot,
  },
  {
    id: "privacy",
    title: "Ιδιωτικότητα & HITL",
    body: "Οι ενέργειες εγγραφής (αποστολή email, νέο ραντεβού) περνούν από Human-in-the-loop: προτείνω → εσύ εγκρίνεις ή απορρίπτεις. Σε dry-run mode δεν γίνονται πραγματικές αλλαγές.",
    icon: Shield,
  },
  {
    id: "connect",
    title: "Σύνδεσε ημερολόγιο / email",
    body: "Προαιρετικά σύνδεσε Microsoft 365 ή Google για πραγματικά δεδομένα. Μπορείς να το κάνεις και αργότερα από τις Ρυθμίσεις.",
    icon: Calendar,
  },
  {
    id: "ready",
    title: "Έτοιμη για την πρώτη συνομιλία",
    body: "Δοκίμασε π.χ. «Ποια ραντεβού έχω αύριο;» ή «Ετοίμασε follow-up email μετά από meeting». Οι απαντήσεις εμφανίζονται με streaming.",
    icon: MessageSquare,
  },
];

export default function OnboardingWizard({ onComplete, onGoSettings }: Props) {
  const [step, setStep] = useState(0);
  const [connecting, setConnecting] = useState<string | null>(null);
  const current = STEPS[step];
  const Icon = current.icon;
  const isLast = step === STEPS.length - 1;

  async function connect(provider: "microsoft" | "google") {
    setConnecting(provider);
    try {
      const data =
        provider === "microsoft"
          ? await getMicrosoftAuthUrl()
          : await getGoogleAuthUrl();
      if (data.auth_url) window.location.href = data.auth_url;
    } catch (e: any) {
      toast.error(e.message || "Αποτυχία σύνδεσης — μπορείς να συνεχίσεις χωρίς.");
    } finally {
      setConnecting(null);
    }
  }

  function finish() {
    markOnboardingDone();
    onComplete();
  }

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-900/50 backdrop-blur-sm p-4">
      <div className="w-full max-w-lg rounded-2xl bg-white dark:bg-slate-900 shadow-xl border border-slate-200 dark:border-slate-700 overflow-hidden">
        <div className="flex items-center justify-between px-5 py-3 border-b border-slate-100 dark:border-slate-800">
          <p className="text-xs text-slate-500">
            Βήμα {step + 1} / {STEPS.length}
          </p>
          <button
            type="button"
            onClick={finish}
            className="text-slate-400 hover:text-slate-600 p-1"
            aria-label="Παράλειψη"
          >
            <X size={18} />
          </button>
        </div>

        <div className="px-6 py-8 text-center space-y-4">
          <div className="mx-auto w-14 h-14 rounded-2xl bg-rose-600 text-white flex items-center justify-center">
            <Icon size={28} />
          </div>
          <h2 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
            {current.title}
          </h2>
          <p className="text-sm text-slate-600 dark:text-slate-400 leading-relaxed">
            {current.body}
          </p>

          {current.id === "connect" && (
            <div className="flex flex-col sm:flex-row gap-2 justify-center pt-2">
              <button
                type="button"
                disabled={!!connecting}
                onClick={() => connect("microsoft")}
                className="rounded-lg border border-slate-200 dark:border-slate-700 px-4 py-2 text-sm hover:bg-slate-50 dark:hover:bg-slate-800"
              >
                {connecting === "microsoft" ? "…" : "Microsoft 365"}
              </button>
              <button
                type="button"
                disabled={!!connecting}
                onClick={() => connect("google")}
                className="rounded-lg border border-slate-200 dark:border-slate-700 px-4 py-2 text-sm hover:bg-slate-50 dark:hover:bg-slate-800"
              >
                {connecting === "google" ? "…" : "Google"}
              </button>
              <button
                type="button"
                onClick={() => onGoSettings?.()}
                className="rounded-lg text-slate-500 text-sm px-4 py-2 hover:underline"
              >
                Αργότερα στις Ρυθμίσεις
              </button>
            </div>
          )}
        </div>

        <div className="flex items-center justify-between px-5 py-4 border-t border-slate-100 dark:border-slate-800 bg-slate-50 dark:bg-slate-950/50">
          <button
            type="button"
            disabled={step === 0}
            onClick={() => setStep((s) => s - 1)}
            className="flex items-center gap-1 text-sm text-slate-600 disabled:opacity-30"
          >
            <ChevronLeft size={16} /> Πίσω
          </button>
          <div className="flex gap-1.5">
            {STEPS.map((_, i) => (
              <span
                key={i}
                className={`h-1.5 w-6 rounded-full ${
                  i === step ? "bg-rose-600" : "bg-slate-200 dark:bg-slate-700"
                }`}
              />
            ))}
          </div>
          {isLast ? (
            <button
              type="button"
              onClick={finish}
              className="flex items-center gap-1 rounded-lg bg-rose-600 hover:bg-rose-700 text-white text-sm px-4 py-2"
            >
              <Check size={16} /> Ξεκίνα
            </button>
          ) : (
            <button
              type="button"
              onClick={() => setStep((s) => s + 1)}
              className="flex items-center gap-1 text-sm text-rose-700 font-medium"
            >
              Επόμενο <ChevronRight size={16} />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
