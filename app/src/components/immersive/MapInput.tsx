import { useEffect, useState } from "react";
import { useImmersive } from "@/stores/immersive";

export default function MapInput() {
  const active = useImmersive((s) => s.active);
  const source = useImmersive((s) => s.source);
  const mapQuery = useImmersive((s) => s.mapQuery);
  const setSource = useImmersive((s) => s.setSource);

  const [draft, setDraft] = useState(mapQuery);

  useEffect(() => {
    setDraft(mapQuery);
  }, [mapQuery]);

  if (!active || source !== "map") return null;

  const submit = () => {
    const q = draft.trim();
    if (!q) return;
    void setSource("map", { query: q });
  };

  return (
    <form
      className="fixed left-1/2 top-14 z-[66] flex -translate-x-1/2 gap-1.5 border border-hal-red/35 bg-[rgba(8,8,11,0.85)] p-1.5"
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
    >
      <input
        type="text"
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        placeholder="address, place, or lat,lng"
        autoComplete="off"
        className="w-80 border border-hal-red/30 bg-black/50 px-2.5 py-1.5 font-mono text-[12px] text-hal-text outline-none focus:border-hal-red"
      />
      <button
        type="submit"
        className="border border-hal-red bg-hal-red/15 px-2.5 py-1.5 font-display text-[9px] uppercase tracking-[2px] text-white"
      >
        Go
      </button>
    </form>
  );
}
