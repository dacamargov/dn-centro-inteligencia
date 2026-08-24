import { useEffect, useRef, useState } from 'react';

interface Props {
  value: number;
  format: (n: number) => string;
  durationMs?: number;
}

/**
 * Smoothly animates a number from previous value to next when `value` changes.
 * Used in KPI cards to give a "ticking up" feel.
 */
export default function AnimatedNumber({ value, format, durationMs = 700 }: Props) {
  const [display, setDisplay] = useState(value);
  const fromRef = useRef(value);
  const startRef = useRef<number | null>(null);
  const targetRef = useRef(value);

  useEffect(() => {
    fromRef.current = display;
    targetRef.current = value;
    startRef.current = null;

    let raf = 0;
    const step = (t: number) => {
      if (startRef.current === null) startRef.current = t;
      const elapsed = t - startRef.current;
      const progress = Math.min(1, elapsed / durationMs);
      // ease-out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      const current = fromRef.current + (targetRef.current - fromRef.current) * eased;
      setDisplay(current);
      if (progress < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value, durationMs]);

  return <>{format(display)}</>;
}
