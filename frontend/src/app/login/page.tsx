"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  getLoginProviders,
  startGoogleLogin,
  startMicrosoftLogin,
  loginDemo,
  getMe,
} from "@/lib/auth";
import { Bot, Loader2 } from "lucide-react";
import { toast } from "sonner";

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const error = searchParams.get("error");
  const [providers, setProviders] = useState({
    google: false,
    microsoft: false,
    demo: true,
  });
  const [loading, setLoading] = useState<string | null>(null);
  const [checking, setChecking] = useState(true);
  const [onLoopbackIp, setOnLoopbackIp] = useState(false);

  useEffect(() => {
    setOnLoopbackIp(window.location.hostname === "127.0.0.1");
    (async () => {
      try {
        const me = await getMe();
        if (me.authenticated) {
          router.replace("/");
          return;
        }
        const p = await getLoginProviders();
        setProviders(p);
      } finally {
        setChecking(false);
      }
    })();
  }, [router]);

  async function onGoogle() {
    setLoading("google");
    try {
      window.location.href = await startGoogleLogin();
    } catch (e: any) {
      toast.error(e.message);
      setLoading(null);
    }
  }

  async function onMicrosoft() {
    setLoading("microsoft");
    try {
      window.location.href = await startMicrosoftLogin();
    } catch (e: any) {
      toast.error(e.message);
      setLoading(null);
    }
  }

  async function onDemo() {
    setLoading("demo");
    try {
      await loginDemo();
      router.replace("/");
    } catch (e: any) {
      toast.error(e.message);
      setLoading(null);
    }
  }

  if (checking) {
    return (
      <div className="flex justify-center py-16">
        <Loader2 className="animate-spin text-rose-600" size={32} />
      </div>
    );
  }

  return (
    <div className="w-full max-w-md rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-soft p-8">
      <div className="flex flex-col items-center mb-8">
        <div className="w-14 h-14 rounded-2xl bg-rose-600 text-white flex items-center justify-center mb-4">
          <Bot size={28} />
        </div>
        <h1 className="text-xl font-semibold tracking-tight">Rafaela</h1>
        <p className="text-sm text-slate-500 mt-1 text-center">
          AI Executive Secretary — σύνδεση λογαριασμού
        </p>
        {onLoopbackIp && (
            <p className="mt-3 text-xs text-amber-700 dark:text-amber-300 text-center leading-relaxed max-w-sm">
              Άνοιξε την εφαρμογή από{" "}
              <a className="underline font-medium" href="http://localhost:3000/login">
                http://localhost:3000
              </a>{" "}
              — το Microsoft login δεν κρατά session στο 127.0.0.1.
            </p>
          )}
      </div>

      {error && (
        <div className="mb-4 rounded-lg bg-red-50 dark:bg-red-950/40 text-red-700 dark:text-red-300 text-sm px-3 py-2">
          Αποτυχία σύνδεσης ({error}). Δοκίμασε ξανά.
        </div>
      )}

      <div className="space-y-3">
        {!providers.google && !providers.microsoft && !providers.demo && (
          <div className="rounded-xl border border-amber-200 dark:border-amber-900 bg-amber-50 dark:bg-amber-950/40 px-3 py-3 text-sm text-amber-900 dark:text-amber-100 space-y-2">
            <p className="font-medium">Δεν υπάρχει διαθέσιμος τρόπος σύνδεσης</p>
            <p className="text-xs leading-relaxed opacity-90">
              Το API δεν επέστρεψε Google / Microsoft / Demo. Σε local production
              χρειάζονται <code className="text-[11px]">MS_CLIENT_*</code> στο{" "}
              <code className="text-[11px]">.env.prod</code> και CORS προς{" "}
              <code className="text-[11px]">http://localhost:3000</code>. Έλεγξε ότι το
              frontend χτυπάει το σωστό API (<code className="text-[11px]">NEXT_PUBLIC_API_URL</code>).
            </p>
          </div>
        )}

        {providers.google && (
          <button
            onClick={onGoogle}
            disabled={!!loading}
            className="w-full flex items-center justify-center gap-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 hover:bg-slate-50 px-4 py-3 text-sm font-medium disabled:opacity-50"
          >
            {loading === "google" ? <Loader2 className="animate-spin" size={18} /> : null}
            Σύνδεση με Google
          </button>
        )}

        {providers.microsoft && (
          <button
            onClick={onMicrosoft}
            disabled={!!loading}
            className="w-full flex items-center justify-center gap-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 hover:bg-slate-50 px-4 py-3 text-sm font-medium disabled:opacity-50"
          >
            {loading === "microsoft" ? <Loader2 className="animate-spin" size={18} /> : null}
            Σύνδεση με Microsoft
          </button>
        )}

        {providers.demo && (
          <>
            <div className="relative my-4">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-slate-200 dark:border-slate-700" />
              </div>
              <div className="relative flex justify-center text-xs">
                <span className="bg-white dark:bg-slate-900 px-2 text-slate-400">ή</span>
              </div>
            </div>
            <button
              onClick={onDemo}
              disabled={!!loading}
              className="w-full rounded-xl bg-rose-600 hover:bg-rose-700 text-white px-4 py-3 text-sm font-medium disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {loading === "demo" && <Loader2 className="animate-spin" size={18} />}
              Συνέχεια ως Demo (trial)
            </button>
          </>
        )}
      </div>

      <p className="mt-6 text-xs text-slate-400 text-center leading-relaxed">
        Η σύνδεση ταυτοποιεί τον λογαριασμό (OpenID). Gmail/Outlook για email & ημερολόγιο
        συνδέονται ξεχωριστά από τις Ρυθμίσεις.
      </p>
    </div>
  );
}

export default function LoginPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 dark:bg-slate-950 p-4">
      <Suspense
        fallback={
          <Loader2 className="animate-spin text-rose-600" size={32} />
        }
      >
        <LoginForm />
      </Suspense>
    </div>
  );
}
