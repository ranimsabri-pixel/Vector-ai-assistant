"use client";

import { useCallback, useEffect, useRef, useState } from "react";

// ============================================================
// Types minimaux pour l'API Web Speech (pas d'`any` — juste ce
// dont le hook a besoin, cf. contraintes qualite du projet).
// ============================================================

type SpeechRecognitionResult = {
  0: { transcript: string };
  isFinal: boolean;
};

type SpeechRecognitionResultList = {
  length: number;
  [index: number]: SpeechRecognitionResult;
};

type SpeechRecognitionEvent = {
  resultIndex: number;
  results: SpeechRecognitionResultList;
};

type SpeechRecognitionErrorEvent = {
  error: string;
};

type SpeechRecognitionInstance = {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  onresult: ((event: SpeechRecognitionEvent) => void) | null;
  onerror: ((event: SpeechRecognitionErrorEvent) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
};

type SpeechRecognitionConstructor = new () => SpeechRecognitionInstance;

type SpeechWindow = Window & {
  SpeechRecognition?: SpeechRecognitionConstructor;
  webkitSpeechRecognition?: SpeechRecognitionConstructor;
};

export function useSpeechRecognition(lang = "fr-FR") {
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [interimTranscript, setInterimTranscript] = useState("");
  const [isSupported, setIsSupported] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const recognitionRef = useRef<SpeechRecognitionInstance | null>(null);

  useEffect(() => {
    if (typeof window === "undefined") return;

    const win = window as SpeechWindow;
    const SpeechRecognitionCtor = win.SpeechRecognition ?? win.webkitSpeechRecognition;

    if (!SpeechRecognitionCtor) {
      setIsSupported(false);
      return;
    }

    setIsSupported(true);
    const recognition = new SpeechRecognitionCtor();
    recognition.lang = lang;
    recognition.continuous = true;
    recognition.interimResults = true;

    recognition.onresult = (event) => {
      let interim = "";
      let final = "";

      for (let i = event.resultIndex; i < event.results.length; i++) {
        const chunk = event.results[i][0].transcript;
        if (event.results[i].isFinal) {
          final += chunk + " ";
        } else {
          interim += chunk;
        }
      }

      if (final) {
        setTranscript((prev) => prev + final);
      }
      setInterimTranscript(interim);
    };

    recognition.onerror = (event) => {
      console.error("[speech-recognition] erreur :", event.error);
      setError(
        event.error === "not-allowed" || event.error === "service-not-allowed"
          ? "Accès au micro refusé — autorise-le dans les paramètres du navigateur."
          : event.error === "no-speech"
          ? "Aucune parole détectée."
          : `Erreur de reconnaissance vocale : ${event.error}`,
      );
      setIsListening(false);
    };

    recognition.onend = () => {
      setIsListening(false);
      setInterimTranscript("");
    };

    recognitionRef.current = recognition;

    // Nettoyage : detache les handlers et arrete une dictee en cours si le
    // composant se demonte ou si `lang` change (sinon une instance zombie
    // continue d'emettre des evenements vers des closures perimees).
    return () => {
      recognition.onresult = null;
      recognition.onerror = null;
      recognition.onend = null;
      try {
        recognition.stop();
      } catch {
        // deja arretee, rien a faire
      }
    };
  }, [lang]);

  const start = useCallback(() => {
    if (!recognitionRef.current || isListening) return;
    setError(null);
    setTranscript("");
    setInterimTranscript("");
    try {
      recognitionRef.current.start();
      setIsListening(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Impossible de démarrer la dictée");
    }
  }, [isListening]);

  const stop = useCallback(() => {
    if (!recognitionRef.current || !isListening) return;
    recognitionRef.current.stop();
    setIsListening(false);
  }, [isListening]);

  const reset = useCallback(() => {
    setTranscript("");
    setInterimTranscript("");
  }, []);

  return {
    isListening,
    transcript,
    interimTranscript,
    isSupported,
    error,
    start,
    stop,
    reset,
  };
}
