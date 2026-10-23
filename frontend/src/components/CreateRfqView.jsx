import React, { useState } from "react";
import { createRfq } from "../api";

export function CreateRfqView({ currentUser, onCreated }) {
  const [formData, setFormData] = useState({
    name: "Trans-Pacific Ocean Reefer Freight",
    reference_id: `RFQ-${Math.floor(1000 + Math.random() * 9000)}`,
    currency: "USD",
    bid_start_time: new Date(Date.now() - 5 * 60000).toISOString().slice(0, 16),
    original_close_time: new Date(Date.now() + 25 * 60000).toISOString().slice(0, 16),
    forced_close_time: new Date(Date.now() + 60 * 60000).toISOString().slice(0, 16),
    pickup_date: new Date(Date.now() + 5 * 86400000).toISOString().slice(0, 16),
    british_auction_enabled: true,
    trigger_window_minutes: 10,
    extension_minutes: 5,
    extension_trigger: "L1_RANK_CHANGE",
  });

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const payload = {
        ...formData,
        bid_start_time: new Date(formData.bid_start_time).toISOString(),
        original_close_time: new Date(formData.original_close_time).toISOString(),
        forced_close_time: new Date(formData.forced_close_time).toISOString(),
        pickup_date: new Date(formData.pickup_date).toISOString(),
        trigger_window_minutes: formData.british_auction_enabled ? Number(formData.trigger_window_minutes) : null,
        extension_minutes: formData.british_auction_enabled ? Number(formData.extension_minutes) : null,
        extension_trigger: formData.british_auction_enabled ? formData.extension_trigger : null,
      };

      const created = await createRfq(payload, currentUser.id);
      onCreated(created);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const isBuyer = currentUser.role === "BUYER" || currentUser.role === "ADMIN";

  if (!isBuyer) {
    return (
      <div className="sentinel-card" style={{ textAlign: "center", padding: "3rem" }}>
        <h3 className="font-display" style={{ color: "var(--accent)", marginBottom: "0.5rem" }}>
          ACCESS RESTRICTED // BUYER ROLE REQUIRED
        </h3>
        <p className="font-mono" style={{ color: "var(--text-secondary)", fontSize: "11px" }}>
          Only Users with the <strong>BUYER</strong> role can create an RFQ.
          Please switch to a Buyer in the top header persona selector.
        </p>
      </div>
    );
  }

  return (
    <div className="sentinel-card" style={{ borderTop: "4px solid var(--accent)", maxWidth: "900px", margin: "0 auto" }}>
      <div style={{ marginBottom: "1.5rem" }}>
        <div style={{ display: "inline-flex", alignItems: "center", gap: "0.5rem", padding: "0.2rem 0.5rem", backgroundColor: "#111111", color: "#ffffff", fontSize: "10px", fontFamily: "var(--font-mono)", textTransform: "uppercase", marginBottom: "0.5rem" }}>
          <span>+ RFQ INITIATION</span>
        </div>
        <h2 className="font-display" style={{ fontSize: "1.4rem", fontWeight: 800, textTransform: "uppercase", letterSpacing: "-0.02em" }}>
          Publish New British Auction Contract
        </h2>
        <p className="font-mono" style={{ color: "var(--text-secondary)", fontSize: "11px" }}>
          Configure freight specifications, dynamic extension trigger windows (X/Y), and hard forced close caps.
        </p>
      </div>

      {error && (
        <div style={{
          backgroundColor: "rgba(230, 57, 32, 0.1)",
          border: "1px solid var(--accent)",
          color: "var(--accent)",
          padding: "0.75rem",
          marginBottom: "1.25rem",
          fontSize: "11px",
          fontFamily: "var(--font-mono)",
          fontWeight: 700,
        }}>
          ⚠️ {error}
        </div>
      )}

      <form onSubmit={handleSubmit}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: "1rem", marginBottom: "1.25rem" }}>
          <div>
            <label className="font-mono" style={{ fontSize: "10px", color: "var(--text-muted)", display: "block", marginBottom: "3px" }}>
              RFQ CONTRACT NAME
            </label>
            <input
              type="text"
              className="sentinel-input"
              required
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            />
          </div>

          <div>
            <label className="font-mono" style={{ fontSize: "10px", color: "var(--text-muted)", display: "block", marginBottom: "3px" }}>
              REFERENCE ID (UNIQUE)
            </label>
            <input
              type="text"
              className="sentinel-input num-mono"
              required
              value={formData.reference_id}
              onChange={(e) => setFormData({ ...formData, reference_id: e.target.value })}
            />
          </div>

          <div>
            <label className="font-mono" style={{ fontSize: "10px", color: "var(--text-muted)", display: "block", marginBottom: "3px" }}>
              BID START TIME
            </label>
            <input
              type="datetime-local"
              className="sentinel-input num-mono"
              required
              value={formData.bid_start_time}
              onChange={(e) => setFormData({ ...formData, bid_start_time: e.target.value })}
            />
          </div>

          <div>
            <label className="font-mono" style={{ fontSize: "10px", color: "var(--text-muted)", display: "block", marginBottom: "3px" }}>
              ORIGINAL CLOSE TIME
            </label>
            <input
              type="datetime-local"
              className="sentinel-input num-mono"
              required
              value={formData.original_close_time}
              onChange={(e) => setFormData({ ...formData, original_close_time: e.target.value })}
            />
          </div>

          <div>
            <label className="font-mono" style={{ fontSize: "10px", color: "var(--text-muted)", display: "block", marginBottom: "3px" }}>
              FORCED CLOSE TIME (INVIOLABLE CAP)
            </label>
            <input
              type="datetime-local"
              className="sentinel-input num-mono"
              required
              value={formData.forced_close_time}
              onChange={(e) => setFormData({ ...formData, forced_close_time: e.target.value })}
            />
          </div>

          <div>
            <label className="font-mono" style={{ fontSize: "10px", color: "var(--text-muted)", display: "block", marginBottom: "3px" }}>
              PICKUP / SERVICE DATE
            </label>
            <input
              type="datetime-local"
              className="sentinel-input num-mono"
              required
              value={formData.pickup_date}
              onChange={(e) => setFormData({ ...formData, pickup_date: e.target.value })}
            />
          </div>
        </div>

        {/* British Auction Configuration Box */}
        <div style={{
          backgroundColor: "#ffffff",
          border: "1px solid var(--surface-border-bold)",
          padding: "1.25rem",
          marginBottom: "1.5rem"
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.6rem", marginBottom: "1rem" }}>
            <input
              type="checkbox"
              id="british_auction_toggle"
              checked={formData.british_auction_enabled}
              onChange={(e) => setFormData({ ...formData, british_auction_enabled: e.target.checked })}
              style={{ cursor: "pointer", width: "14px", height: "14px" }}
            />
            <label htmlFor="british_auction_toggle" className="font-display" style={{ fontWeight: 800, fontSize: "12px", textTransform: "uppercase", cursor: "pointer" }}>
              ENABLE BRITISH AUCTION DYNAMIC EXTENSION PROTOCOL
            </label>
          </div>

          {formData.british_auction_enabled && (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "1rem" }}>
              <div>
                <label className="font-mono" style={{ fontSize: "10px", color: "var(--text-muted)", display: "block", marginBottom: "3px" }}>
                  TRIGGER WINDOW X (MINS)
                </label>
                <input
                  type="number"
                  min="1"
                  className="sentinel-input num-mono"
                  required
                  value={formData.trigger_window_minutes}
                  onChange={(e) => setFormData({ ...formData, trigger_window_minutes: e.target.value })}
                />
              </div>

              <div>
                <label className="font-mono" style={{ fontSize: "10px", color: "var(--text-muted)", display: "block", marginBottom: "3px" }}>
                  EXTENSION DURATION Y (MINS)
                </label>
                <input
                  type="number"
                  min="1"
                  className="sentinel-input num-mono"
                  required
                  value={formData.extension_minutes}
                  onChange={(e) => setFormData({ ...formData, extension_minutes: e.target.value })}
                />
              </div>

              <div>
                <label className="font-mono" style={{ fontSize: "10px", color: "var(--text-muted)", display: "block", marginBottom: "3px" }}>
                  TRIGGER CONDITION
                </label>
                <select
                  className="sentinel-input font-mono"
                  style={{ cursor: "pointer" }}
                  value={formData.extension_trigger}
                  onChange={(e) => setFormData({ ...formData, extension_trigger: e.target.value })}
                >
                  <option value="BID_RECEIVED">ANY BID RECEIVED IN LAST X MINS</option>
                  <option value="ANY_RANK_CHANGE">ANY RANK POSITION CHANGE IN LAST X MINS</option>
                  <option value="L1_RANK_CHANGE">LOWEST BIDDER (L1) CHANGED IN LAST X MINS</option>
                </select>
              </div>
            </div>
          )}
        </div>

        <button type="submit" className="btn-sentinel btn-sentinel-primary" disabled={loading} style={{ padding: "0.75rem 1.75rem" }}>
          {loading ? "INITIALIZING RFQ CONTRACT..." : "INITIALIZE BRITISH AUCTION RFQ →"}
        </button>
      </form>
    </div>
  );
}
