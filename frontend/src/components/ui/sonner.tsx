"use client";

import { Toaster as Sonner, type ToasterProps } from "sonner";

/**
 * theme="system" (not next-themes): this app has no theme toggle wired up
 * yet — dark: Tailwind classes rely on darkMode:"class" but nothing ever
 * sets that class — so we read prefers-color-scheme directly instead of
 * inheriting the app's (currently inert) dark mode state.
 */
export function Toaster(props: ToasterProps) {
  return (
    <Sonner
      theme="system"
      className="toaster group"
      position="bottom-right"
      toastOptions={{
        classNames: {
          toast:
            "group toast group-[.toaster]:bg-white group-[.toaster]:text-slate-900 group-[.toaster]:border-slate-200 group-[.toaster]:shadow-soft dark:group-[.toaster]:bg-slate-900 dark:group-[.toaster]:text-slate-100 dark:group-[.toaster]:border-slate-800",
          description: "group-[.toast]:text-slate-500 dark:group-[.toast]:text-slate-400",
          actionButton:
            "group-[.toast]:bg-rose-600 group-[.toast]:text-white",
          cancelButton:
            "group-[.toast]:bg-slate-100 group-[.toast]:text-slate-600",
          error:
            "group-[.toaster]:!bg-red-50 group-[.toaster]:!text-red-900 group-[.toaster]:!border-red-200 dark:group-[.toaster]:!bg-red-950/40 dark:group-[.toaster]:!text-red-200 dark:group-[.toaster]:!border-red-900",
        },
      }}
      {...props}
    />
  );
}
