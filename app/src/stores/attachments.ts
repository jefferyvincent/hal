import { create } from "zustand";
import type { Attachment } from "@/types";

const MAX_TEXT_BYTES = 200 * 1024;
const MAX_IMAGE_BYTES = 4 * 1024 * 1024;
const MAX_COUNT = 50;

interface AttachmentState {
  items: Attachment[];
  error: string | null;
  add: (file: File, displayName?: string) => Promise<void>;
  addImage: (name: string, base64: string) => void;
  remove: (index: number) => void;
  clear: () => void;
  flashError: (msg: string) => void;
}

function readAsText(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(String(r.result ?? ""));
    r.onerror = () => reject(r.error);
    r.readAsText(file);
  });
}

function readAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(String(r.result ?? ""));
    r.onerror = () => reject(r.error);
    r.readAsDataURL(file);
  });
}

export const useAttachments = create<AttachmentState>((set, get) => ({
  items: [],
  error: null,

  flashError(msg) {
    set({ error: msg });
    setTimeout(() => {
      if (get().error === msg) set({ error: null });
    }, 4000);
  },

  async add(file, displayName) {
    if (get().items.length >= MAX_COUNT) {
      get().flashError("Attachment limit reached");
      return;
    }
    const name = displayName || file.name || "unnamed";
    const isImage = (file.type || "").startsWith("image/");
    try {
      if (isImage) {
        if (file.size > MAX_IMAGE_BYTES) {
          get().flashError(`Skipping ${name}: image > 4MB`);
          return;
        }
        const dataUrl = await readAsDataUrl(file);
        const base64 = dataUrl.split(",", 2)[1] || "";
        if (!base64) {
          get().flashError(`Could not read ${name}`);
          return;
        }
        set((s) => ({
          items: [...s.items, { name, kind: "image", content: base64 }],
        }));
      } else {
        if (file.size > MAX_TEXT_BYTES) {
          get().flashError(`Skipping ${name}: text > 200KB`);
          return;
        }
        const text = await readAsText(file);
        set((s) => ({
          items: [...s.items, { name, kind: "text", content: text }],
        }));
      }
    } catch (err) {
      get().flashError(
        `Could not attach ${name}: ${(err as Error).message ?? err}`,
      );
    }
  },

  addImage(name, base64) {
    if (!base64) return;
    if (get().items.length >= MAX_COUNT) {
      get().flashError("Attachment limit reached");
      return;
    }
    set((s) => ({
      items: [...s.items, { name, kind: "image", content: base64 }],
    }));
  },

  remove(index) {
    set((s) => ({ items: s.items.filter((_, i) => i !== index) }));
  },

  clear() {
    set({ items: [] });
  },
}));
