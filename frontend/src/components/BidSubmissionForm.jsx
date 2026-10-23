import React, { useState } from "react";
import { submitBid } from "../api";

export function BidSubmissionForm({ rfq, currentUser, onBidSuccess }) {
  const [formData, setFormData] = useState({
    freight_charges: "",
    origin_charges: "",
    destination_charges: "",
    transit_time_days: "3",
    quote_valid_until: new Date(Date.now() + 14 * 86400000).toISOString().slice(0, 16),
  });

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [successNotice, setSuccessNotice] = useState(null);

  const isSupplier = currentUser.role === "SUPPLIER";
  const isActive = rfq.status === "ACTIVE";

  const myCurrentBid = rfq.current_rankings?.find((r) => r.supplier_id === currentUser.supplier_id);

  const totalPreview =
    (parseFloat(formData.freight_charges) || 0) +
    (parseFloat(formData.origin_charges) || 0) +
    (parseFloat(formData.destination_charges) || 0);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setSuccessNotice(null);

    try {
      const payload = {
        freight_charges: parseFloat(formData.freight_charges) || 0,
        origin_charges: parseFloat(formData.origin_charges) || 0,
        destination_charges: parseFloat(formData.destination_charges) || 0,
        transit_time_days: parseInt(formData.transit_time_days, 10),
        quote_valid_until: new Date(formData.quote_valid_until).toISOString(),
      };

      const res = await submitBid(rfq.id, payload, currentUser.id);
      setSuccessNotice(
        `Quote accepted! You are currently Rank L${res.rank} at $${parseFloat(res.total_price).toFixed(2)}.` +
          (res.auction_extended ? ` Auction extended to ${new Date(res.new_close_time).toLocaleTimeString()}!` : "")
      );
      setFormData((prev) => ({ ...prev, freight_charges: "", origin_charges: "", destination_charges: "" }));
      onBidSuccess();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  if (!isSupplier) {
    return (
      <div className="sentinel-card" style={{ fontSize: "11px", color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
        LOGGED IN AS: <strong>{currentUser.name} ({currentUser.role})</strong>.
        <br />
        Switch persona to a <strong>CARRIER (SUPPLIER)</strong> in the top header to submit lower bids.
      </div>
    );
  }

  if (!isActive) {
    return (
      <div style={{
        backgroundColor: "rgba(230, 57, 32, 0.08)",
        border: "1px solid var(--accent)",
        color: "var(--accent)",
        padding: "1rem",
        fontSize: "11px",
        fontFamily: "var(--font-mono)",
        fontWeight: 700,
      }}>
        AUCTION STATUS: {rfq.status}. BIDDING TERMINAL IS LOCKED.
      </div>
    );
  }

  return (
    <div className="sentinel-card" style={{ borderTop: "3px solid var(--surface-border-bold)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
        <div>
          <h3 className="font-display" style={{ fontSize: "13px", fontWeight: 800, textTransform: "uppercase", letterSpacing: "0.04em" }}>
            SUBMIT / REVISE QUOTE
          </h3>
          <p className="font-mono" style={{ color: "var(--text-secondary)", fontSize: "10px" }}>
            CARRIER: <strong>{currentUser.carrier_name}</strong>
          </p>
        </div>

        {myCurrentBid && (
          <span className="sentinel-badge sentinel-badge-subtle">
            YOUR STANDING: L{myCurrentBid.rank} (${parseFloat(myCurrentBid.total_price).toFixed(2)})
          </span>
        )}
      </div>

      {error && (
        <div style={{
          backgroundColor: "rgba(230, 57, 32, 0.1)",
          border: "1px solid var(--accent)",
          color: "var(--accent)",
          padding: "0.5rem 0.75rem",
          marginBottom: "1rem",
          fontSize: "11px",
          fontFamily: "var(--font-mono)",
          fontWeight: 700,
        }}>
          ⚠️ REJECTION: {error}
        </div>
      )}

      {successNotice && (
        <div style={{
          backgroundColor: "rgba(16, 112, 64, 0.1)",
          border: "1px solid #107040",
          color: "#107040",
          padding: "0.5rem 0.75rem",
          marginBottom: "1rem",
          fontSize: "11px",
          fontFamily: "var(--font-mono)",
          fontWeight: 700,
        }}>
          ✓ {successNotice}
        </div>
      )}

      <form onSubmit={handleSubmit}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))", gap: "0.75rem", marginBottom: "1rem" }}>
          <div>
            <label className="font-mono" style={{ fontSize: "10px", color: "var(--text-muted)", display: "block", marginBottom: "3px" }}>
              FREIGHT ($)
            </label>
            <input
              type="number"
              step="0.01"
              min="0"
              required
              className="sentinel-input num-mono"
              placeholder="e.g. 1200.00"
              value={formData.freight_charges}
              onChange={(e) => setFormData({ ...formData, freight_charges: e.target.value })}
            />
          </div>

          <div>
            <label className="font-mono" style={{ fontSize: "10px", color: "var(--text-muted)", display: "block", marginBottom: "3px" }}>
              ORIGIN THC ($)
            </label>
            <input
              type="number"
              step="0.01"
              min="0"
              required
              className="sentinel-input num-mono"
              placeholder="e.g. 80.00"
              value={formData.origin_charges}
              onChange={(e) => setFormData({ ...formData, origin_charges: e.target.value })}
            />
          </div>

          <div>
            <label className="font-mono" style={{ fontSize: "10px", color: "var(--text-muted)", display: "block", marginBottom: "3px" }}>
              DEST THC ($)
            </label>
            <input
              type="number"
              step="0.01"
              min="0"
              required
              className="sentinel-input num-mono"
              placeholder="e.g. 80.00"
              value={formData.destination_charges}
              onChange={(e) => setFormData({ ...formData, destination_charges: e.target.value })}
            />
          </div>

          <div>
            <label className="font-mono" style={{ fontSize: "10px", color: "var(--text-muted)", display: "block", marginBottom: "3px" }}>
              TRANSIT (DAYS)
            </label>
            <input
              type="number"
              min="1"
              required
              className="sentinel-input num-mono"
              value={formData.transit_time_days}
              onChange={(e) => setFormData({ ...formData, transit_time_days: e.target.value })}
            />
          </div>

          <div>
            <label className="font-mono" style={{ fontSize: "10px", color: "var(--text-muted)", display: "block", marginBottom: "3px" }}>
              QUOTE VALIDITY
            </label>
            <input
              type="datetime-local"
              required
              className="sentinel-input num-mono"
              value={formData.quote_valid_until}
              onChange={(e) => setFormData({ ...formData, quote_valid_until: e.target.value })}
            />
          </div>
        </div>

        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderTop: "1px solid var(--surface-border)", paddingTop: "0.85rem" }}>
          <div className="font-mono" style={{ fontSize: "12px" }}>
            LANDED TOTAL: <strong className="num-mono" style={{ color: totalPreview > 0 ? "#107040" : "inherit", fontSize: "15px" }}>
              ${totalPreview.toFixed(2)}
            </strong>
          </div>

          <button
            type="submit"
            className="btn-sentinel btn-sentinel-primary"
            disabled={loading || totalPreview <= 0}
          >
            {loading ? "TRANSMITTING..." : "TRANSMIT LOWER QUOTE →"}
          </button>
        </div>
      </form>
    </div>
  );
}
