import { useEffect, useRef } from "react";
import type { RefObject } from "react";

export function useNavigationDrawer(
  sidebar: RefObject<HTMLElement | null>,
  open: boolean,
  close: () => void,
) {
  const onClose = useRef(close);
  useEffect(() => { onClose.current = close; });
  useEffect(() => {
    const drawer = sidebar.current;
    if (!open || !drawer) return;
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const controls = () => Array.from(drawer.querySelectorAll<HTMLElement>(
      'button:not([disabled]), a[href], input:not([disabled]), select:not([disabled])',
    )).filter(element => element.getClientRects().length > 0);
    controls()[0]?.focus();
    const keydown = (event: globalThis.KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose.current();
      } else if (event.key === "Tab") {
        const items = controls();
        const first = items[0], last = items.at(-1);
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault(); last?.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault(); first?.focus();
        }
      }
    };
    const media = window.matchMedia("(max-width: 800px)");
    const resize = () => { if (!media.matches) onClose.current(); };
    document.addEventListener("keydown", keydown);
    media.addEventListener("change", resize);
    return () => {
      document.removeEventListener("keydown", keydown);
      media.removeEventListener("change", resize);
      document.body.style.overflow = overflow;
      if (previous?.isConnected && previous.getClientRects().length) previous.focus();
    };
  }, [open, sidebar]);
}
