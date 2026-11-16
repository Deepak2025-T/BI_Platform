import { useDictation } from "../lib/dictation";
import Icon from "./Icon";

interface Props {
  /** Called with each finished phrase, to be added to whatever is in the box. */
  onPhrase: (phrase: string) => void;
  /** Icon only, for a box too small to carry a word beside it. */
  compact?: boolean;
  /** What is being dictated, for the button's label when it is read out. */
  what?: string;
}

/**
 * Speaking a request instead of typing it.
 *
 * The browser does the listening, so there is no key to set up and no audio of ours anywhere; the
 * tooltip says which browser is doing it, because "my voice goes to Google" is the kind of thing
 * someone should find out before they speak rather than afterwards.
 *
 * Nothing appears where it cannot be seen: the words land in the box as they are recognised, the
 * phrase still being said shows underneath until it settles, and the button plainly says whether
 * the microphone is on. A browser with no recogniser gets no button at all, rather than one that
 * is always greyed out.
 */
export default function Dictate({ onPhrase, compact, what = "your request" }: Props) {
  const { supported, listening, interim, error, toggle } = useDictation(onPhrase);

  if (!supported) return null;

  return (
    <div className={"dictate" + (compact ? " compact" : "")}>
      <button type="button" className={"dictate-btn" + (listening ? " on" : "")}
        aria-pressed={listening} aria-label={listening ? "Stop listening" : `Speak ${what}`}
        title={listening ? "Stop listening"
          : `Speak ${what} instead of typing it. Your browser turns the speech into words; `
            + "Chrome and Edge send the sound to their own service to do it."}
        onClick={toggle}>
        <Icon name={listening ? "mic-off" : "mic"} size={16} />
        {!compact && <span>{listening ? "Stop" : "Speak"}</span>}
      </button>

      {/* What is being said right now. It is kept out of the box itself, because a box that
          rewrites its own contents can't be edited while it does it. */}
      {listening && (
        <span className="dictate-live" aria-live="polite">
          <span className="dictate-pulse" aria-hidden="true" />
          {interim || "Listening… speak, and the words go into the box."}
        </span>
      )}
      {!listening && error && <span className="dictate-error">{error}</span>}
    </div>
  );
}
