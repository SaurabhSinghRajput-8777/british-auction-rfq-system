import React, { useState, useEffect } from "react";

export function CountdownTicker({ targetTime, status, compact = false }) {
  const [timeLeft, setTimeLeft] = useState({ totalSeconds: 0, hours: 0, minutes: 0, seconds: 0 });

  useEffect(() => {
    function calculate() {
      if (!targetTime || status === "CLOSED" || status === "FORCE_CLOSED") {
        setTimeLeft({ totalSeconds: 0, hours: 0, minutes: 0, seconds: 0 });
        return;
      }
      const diff = new Date(targetTime).getTime() - new Date().getTime();
      if (diff <= 0) {
        setTimeLeft({ totalSeconds: 0, hours: 0, minutes: 0, seconds: 0 });
        return;
      }
      const totalSeconds = Math.floor(diff / 1000);
      const hours = Math.floor(totalSeconds / 3600);
      const minutes = Math.floor((totalSeconds % 3600) / 60);
      const seconds = totalSeconds % 60;
      setTimeLeft({ totalSeconds, hours, minutes, seconds });
    }

    calculate();
    const interval = setInterval(calculate, 1000);
    return () => clearInterval(interval);
  }, [targetTime, status]);

  const pad = (n) => String(n).padStart(2, "0");
  const isClosed = status === "CLOSED" || status === "FORCE_CLOSED";
  const isCritical = timeLeft.totalSeconds <= 120 && timeLeft.totalSeconds > 0;
  const isUrgent = timeLeft.totalSeconds <= 600 && timeLeft.totalSeconds > 120;

  if (compact) {
    if (isClosed) {
      return (
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <span className="font-mono" style={{ fontSize: "11px", color: "var(--text-muted)", fontWeight: 600 }}>
            00:00:00
          </span>
          <span className="sentinel-badge sentinel-badge-closed" style={{ fontSize: "9px" }}>
            {status === "FORCE_CLOSED" ? "CAPPED" : "CLOSED"}
          </span>
        </div>
      );
    }

    return (
      <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
        <span
          className="font-mono"
          style={{
            fontSize: "12px",
            fontWeight: 700,
            color: isCritical ? "var(--risk-critical)" : isUrgent ? "var(--risk-high)" : "var(--text-primary)"
          }}
        >
          {pad(timeLeft.hours)}:{pad(timeLeft.minutes)}:{pad(timeLeft.seconds)}
        </span>
        {isCritical && (
          <span className="sentinel-badge sentinel-badge-critical" style={{ fontSize: "9px" }}>
            &lt; 2M
          </span>
        )}
        {isUrgent && (
          <span className="sentinel-badge sentinel-badge-high" style={{ fontSize: "9px" }}>
            WINDOW
          </span>
        )}
      </div>
    );
  }

  // Full detailed card
  if (isClosed) {
    return (
      <div className="countdown-sentinel">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.35rem" }}>
          <span className="font-mono" style={{ fontSize: "10px", fontWeight: 700, color: "var(--text-muted)", letterSpacing: "0.06em", textTransform: "uppercase" }}>
            CLOSING STATUS // TERMINAL
          </span>
          <span className={`sentinel-badge ${status === "FORCE_CLOSED" ? "sentinel-badge-critical" : "sentinel-badge-closed"}`}>
            {status === "FORCE_CLOSED" ? "FORCED CLOSE CAP EXCEEDED" : "CLOSED TERMINAL"}
          </span>
        </div>
        <div style={{ display: "flex", alignItems: "baseline", gap: "0.75rem" }}>
          <div className="font-mono" style={{ fontSize: "2rem", fontWeight: 800, color: "var(--text-muted)" }}>
            00:00:00
          </div>
          <span className="font-mono" style={{ fontSize: "11px", color: "var(--text-muted)" }}>
            TRANSACTION SUBMISSIONS LOCKED
          </span>
        </div>
      </div>
    );
  }

  return (
    <div className="countdown-sentinel">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.35rem" }}>
        <span className="font-mono" style={{ fontSize: "10px", fontWeight: 700, color: "var(--text-secondary)", letterSpacing: "0.06em", textTransform: "uppercase" }}>
          EFFECTIVE CLOSE COUNTDOWN // SERVER CLOCK
        </span>
        {isCritical && (
          <span className="sentinel-badge sentinel-badge-critical">
            <span className="pulse-sentinel" /> CRITICAL TRIGGER WINDOW (&lt; 2M)
          </span>
        )}
        {isUrgent && (
          <span className="sentinel-badge sentinel-badge-high">
            <span className="pulse-sentinel" /> DYNAMIC TRIGGER ACTIVE
          </span>
        )}
      </div>

      <div style={{ display: "flex", alignItems: "baseline", gap: "0.75rem" }}>
        <div
          className="font-mono"
          style={{
            fontSize: "2.2rem",
            fontWeight: 800,
            letterSpacing: "-0.03em",
            color: isCritical ? "var(--risk-critical)" : isUrgent ? "var(--risk-high)" : "var(--text-primary)"
          }}
        >
          {pad(timeLeft.hours)}:{pad(timeLeft.minutes)}:{pad(timeLeft.seconds)}
        </div>
        <div className="font-mono" style={{ fontSize: "11px", color: "var(--text-muted)" }}>
          HRS : MIN : SEC
        </div>
      </div>
    </div>
  );
}
