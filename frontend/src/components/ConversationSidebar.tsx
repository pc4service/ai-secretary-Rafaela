"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { listConversations, deleteConversation, isUnauthorized } from "@/lib/api";
import { MessageSquarePlus, Trash2, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
  DialogClose,
} from "@/components/ui/dialog";

type Conv = {
  id: string;
  title?: string | null;
  updated_at?: string | null;
};

type Props = {
  activeId: string | null;
  onSelect: (id: string | null) => void;
  refreshKey?: number;
};

export default function ConversationSidebar({
  activeId,
  onSelect,
  refreshKey = 0,
}: Props) {
  const router = useRouter();
  const [items, setItems] = useState<Conv[]>([]);
  const [loading, setLoading] = useState(true);
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  async function load() {
    try {
      const data = await listConversations();
      setItems(Array.isArray(data) ? data : []);
    } catch (e) {
      if (isUnauthorized(e)) {
        router.replace("/login");
        return;
      }
      setItems([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [refreshKey]);

  function onDeleteClick(id: string, e: React.MouseEvent) {
    e.stopPropagation();
    setPendingDeleteId(id);
  }

  async function confirmDelete() {
    if (!pendingDeleteId) return;
    setDeleting(true);
    try {
      await deleteConversation(pendingDeleteId);
      if (activeId === pendingDeleteId) onSelect(null);
      await load();
      setPendingDeleteId(null);
    } catch (err: any) {
      if (isUnauthorized(err)) {
        router.replace("/login");
        return;
      }
      toast.error(err.message);
    } finally {
      setDeleting(false);
    }
  }

  return (
    <div className="flex flex-col h-full border-r border-slate-200 dark:border-slate-800 bg-slate-50/80 dark:bg-slate-950/40 w-full md:w-56">
      <div className="p-3 border-b border-slate-200 dark:border-slate-800">
        <button
          type="button"
          onClick={() => onSelect(null)}
          className="w-full flex items-center justify-center gap-2 rounded-lg bg-rose-600 hover:bg-rose-700 text-white text-xs py-2"
        >
          <MessageSquarePlus size={14} /> Νέα συνομιλία
        </button>
      </div>
      <div className="flex-1 overflow-y-auto p-2 space-y-1">
        {loading && (
          <div className="flex justify-center py-6 text-slate-400">
            <Loader2 size={16} className="animate-spin" />
          </div>
        )}
        {!loading && items.length === 0 && (
          <p className="text-[11px] text-slate-400 text-center px-2 py-4">
            Δεν υπάρχουν ακόμη συνομιλίες
          </p>
        )}
        {items.map((c) => (
          <div
            key={c.id}
            role="button"
            tabIndex={0}
            onClick={() => onSelect(c.id)}
            onKeyDown={(e) => e.key === "Enter" && onSelect(c.id)}
            className={cn(
              "group flex items-start gap-1 rounded-lg px-2 py-2 text-left text-xs cursor-pointer",
              activeId === c.id
                ? "bg-rose-50 dark:bg-rose-950/40 text-rose-800 dark:text-rose-200"
                : "hover:bg-white dark:hover:bg-slate-900 text-slate-600"
            )}
          >
            <span className="flex-1 line-clamp-2 leading-snug">
              {c.title || "Χωρίς τίτλο"}
            </span>
            <button
              type="button"
              onClick={(e) => onDeleteClick(c.id, e)}
              className="opacity-0 group-hover:opacity-100 p-0.5 text-slate-400 hover:text-red-500"
              aria-label="Διαγραφή"
            >
              <Trash2 size={12} />
            </button>
          </div>
        ))}
      </div>

      <Dialog
        open={!!pendingDeleteId}
        onOpenChange={(open) => !open && setPendingDeleteId(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Διαγραφή συνομιλίας;</DialogTitle>
            <DialogDescription>
              Η ενέργεια αυτή δεν αναιρείται.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <DialogClose asChild>
              <button
                type="button"
                className="rounded-lg px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
              >
                Άκυρο
              </button>
            </DialogClose>
            <button
              type="button"
              onClick={confirmDelete}
              disabled={deleting}
              className="inline-flex items-center gap-1.5 rounded-lg bg-red-600 hover:bg-red-700 text-white text-sm px-3 py-1.5 disabled:opacity-50"
            >
              {deleting && <Loader2 className="animate-spin" size={14} />}
              Διαγραφή
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
