import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Speaking a request instead of typing it.
 *
 * This is the browser's own speech recognition, so nothing is recorded, nothing is uploaded by us
 * and no key is needed. Chrome and Edge send the audio to Google's service to turn it into words,
 * which is worth knowing and is said plainly in the button's tooltip; Firefox has no recogniser at
 * all, so the button is simply not there.
 *
 * The words land in whatever box the person was typing in, added to what is already there rather
 * than put in place of it: dictation is another way to type, not a mode that takes the box over.
 */

/** What the browser's recogniser does, as much of it as we use. TypeScript's DOM library types the
 *  results but not the recogniser itself, which is still behind a prefix in every browser. */
interface Recogniser {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  maxAlternatives: number;
  start(): void;
  stop(): void;
  abort(): void;
  onresult: ((e: ResultEvent) => void) | null;
  onerror: ((e: ErrorEvent) => void) | null;
  onend: (() => void) | null;
}

interface ResultEvent {
  resultIndex: number;
  results: SpeechRecognitionResultList;
}

interface ErrorEvent {
  error: string;
}

type RecogniserClass = new () => Recogniser;

const WINDOW = window as unknown as {
  SpeechRecognition?: RecogniserClass;
  webkitSpeechRecognition?: RecogniserClass;
};

/** The recogniser class, or undefined where the browser has none. */
const RECOGNISER: RecogniserClass | undefined = WINDOW.SpeechRecognition ?? WINDOW.webkitSpeechRecognition;

/**
 * Whether dictation can work here at all.
 *
 * A microphone is only offered on a secure page. On plain http the browser refuses the microphone
 * whatever we do, so a button there would be a button that always fails.
 */
export const dictationSupported = !!RECOGNISER && window.isSecureContext;

/**
 * Why there is no microphone here, when there is a reason worth saying.
 *
 * Empty when dictation works, and empty for a browser that simply has no recogniser - there is
 * nothing to be done about Firefox, so saying so is just noise. It is only filled in for the one
 * case that looks like a fault and is not: a browser that can listen, on a page served over plain
 * http. Browsers only hand out the microphone in a secure context, and http://localhost counts as
 * one - which is exactly why this works on a developer's machine and stops on a real server.
 */
export const dictationBlockedReason: string =
  !RECOGNISER || window.isSecureContext
    ? ""
    : "Speaking needs a secure page. This one is served over plain http, so the browser will not "
      + "give any site the microphone. It comes back once the server is on https.";

/** What went wrong, in words someone can act on. */
const REASONS: Record<string, string> = {
  "not-allowed": "The microphone is blocked for this site. Allow it in the browser's address bar, then try again.",
  "service-not-allowed": "The browser wouldn't start speech recognition. Check its microphone and privacy settings.",
  "audio-capture": "No microphone was found. Plug one in, or pick one in the browser's settings.",
  network: "Speech recognition needs the internet and couldn't reach it.",
  aborted: "",       // we stopped it ourselves
  "no-speech": "",   // nothing was said; the restart below handles it
};

/**
 * Adds one dictated phrase to what is already in a box.
 *
 * Exported because it is the half of this worth testing on its own, and because a caller that
 * builds its own text needs to join it the same way.
 */
export function appendSpoken(existing: string, spoken: string): string {
  const addition = spoken.trim();
  if (!addition) return existing;
  if (!existing.trim()) return addition;
  return /\s$/.test(existing) ? existing + addition : `${existing} ${addition}`;
}

export interface Dictation {
  /** False where the browser has no recogniser, or the page isn't secure. */
  supported: boolean;
  listening: boolean;
  /** The phrase being said right now, before the recogniser has settled on it. */
  interim: string;
  /** Empty unless something went wrong that the person can do something about. */
  error: string;
  start: () => void;
  stop: () => void;
  toggle: () => void;
}

/**
 * Dictation into one box.
 *
 * `onPhrase` is called with each finished phrase, so the caller decides where the words go and
 * keeps control of its own text. The phrase being spoken right now comes back as `interim` to be
 * shown somewhere nearby; it is deliberately not put into the box, because a box whose contents
 * rewrite themselves can't be edited.
 */
export function useDictation(onPhrase: (phrase: string) => void, lang?: string): Dictation {
  const [listening, setListening] = useState(false);
  const [interim, setInterim] = useState("");
  const [error, setError] = useState("");
  const recogniser = useRef<Recogniser | null>(null);
  // Chrome's recogniser stops on its own after a few seconds of quiet, which would end a sentence
  // someone is still thinking about. This says whether that stop was asked for.
  const wanted = useRef(false);
  // Restarts that produced nothing. A browser that refuses to run would otherwise be restarted
  // for ever, several times a second.
  const emptyRestarts = useRef(0);
  // Read through a ref so the handlers below never go stale against an older render's callback.
  const phrase = useRef(onPhrase);
  phrase.current = onPhrase;

  const stop = useCallback(() => {
    wanted.current = false;
    setListening(false);
    setInterim("");
    recogniser.current?.stop();
  }, []);

  const start = useCallback(() => {
    if (!RECOGNISER || !dictationSupported) {
      setError("This browser can't listen. Chrome or Edge can.");
      return;
    }
    if (wanted.current) return;
    setError("");
    setInterim("");
    wanted.current = true;
    emptyRestarts.current = 0;

    const listen = () => {
      const r = new RECOGNISER();
      recogniser.current = r;
      // The language the browser is set to. Recognition is far better when it is told, and a
      // guess of "en-US" would hear an Indian or British speaker badly.
      r.lang = lang || navigator.language || "en-US";
      r.continuous = true;        // a requirement is several sentences, not one
      r.interimResults = true;    // so the words appear while they are being said
      r.maxAlternatives = 1;

      r.onresult = (e) => {
        let pending = "";
        for (let i = e.resultIndex; i < e.results.length; i += 1) {
          const result = e.results[i];
          const text = result[0]?.transcript ?? "";
          if (result.isFinal) {
            emptyRestarts.current = 0;
            if (text.trim()) phrase.current(text);
          } else {
            pending += text;
          }
        }
        setInterim(pending.trim());
      };

      r.onerror = (e) => {
        const reason = REASONS[e.error];
        // An unknown code is worth saying out loud rather than swallowing, but the browser's own
        // word for it is no use to anyone, so it is wrapped in a sentence.
        if (reason === undefined) setError(`Listening stopped: ${e.error}.`);
        else if (reason) setError(reason);
        // Nothing can be done about a refused microphone by trying again.
        if (e.error === "not-allowed" || e.error === "service-not-allowed" || e.error === "audio-capture") {
          wanted.current = false;
        }
      };

      r.onend = () => {
        setInterim("");
        if (!wanted.current) { setListening(false); return; }
        emptyRestarts.current += 1;
        if (emptyRestarts.current > 3) {
          // It keeps ending without hearing anything, so it isn't going to work. Say so once.
          wanted.current = false;
          setListening(false);
          setError((e) => e || "Nothing was heard. Check the microphone, then try again.");
          return;
        }
        listen();
      };

      try {
        r.start();
        setListening(true);
      } catch {
        // Already running, which the browser reports by throwing. Nothing is wrong.
        setListening(wanted.current);
      }
    };

    listen();
  }, [lang]);

  const toggle = useCallback(() => (wanted.current ? stop() : start()), [start, stop]);

  // Leaving the page stops the microphone. abort() drops what was being said rather than
  // delivering it into a box that is no longer on screen.
  useEffect(() => () => {
    wanted.current = false;
    const r = recogniser.current;
    if (r) { r.onend = null; r.onresult = null; r.onerror = null; r.abort(); }
  }, []);

  return { supported: dictationSupported, listening, interim, error, start, stop, toggle };
}
