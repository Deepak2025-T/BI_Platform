import { useEffect, useState } from "react";
import Icon from "./Icon";

/** Shows the report on the whole screen: browser full screen, without the app's sidebar. Esc leaves. */
export default function FullscreenButton() {
  const [on, setOn] = useState(false);

  useEffect(() => {
    const sync = () => {
      const full = !!document.fullscreenElement;
      setOn(full);
      document.body.classList.toggle("focus-mode", full);
    };
    document.addEventListener("fullscreenchange", sync);
    return () => {
      document.removeEventListener("fullscreenchange", sync);
      document.body.classList.remove("focus-mode");
    };
  }, []);

  function toggle() {
    if (document.fullscreenElement) {
      document.exitFullscreen().catch(() => {});
    } else if (document.documentElement.requestFullscreen) {
      document.documentElement.requestFullscreen().catch(() => {
        // Full screen refused (e.g. inside a frame): still hide the sidebar.
        document.body.classList.toggle("focus-mode");
        setOn(document.body.classList.contains("focus-mode"));
      });
    } else {
      document.body.classList.toggle("focus-mode");
      setOn(document.body.classList.contains("focus-mode"));
    }
  }

  return (
    <button type="button" className="btn btn-ghost no-print" onClick={toggle} aria-pressed={on}
      title={on ? "Leave full screen (Esc)" : "Show on the whole screen, without the sidebar"}>
      <Icon name={on ? "shrink" : "expand"} size={16} />{on ? "Exit full screen" : "Full screen"}
    </button>
  );
}
