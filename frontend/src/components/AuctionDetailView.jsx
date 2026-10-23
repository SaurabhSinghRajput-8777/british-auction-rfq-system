import React, { useState } from 'react';
import { CountdownTicker } from './CountdownTicker';
import { BidSubmissionForm } from './BidSubmissionForm';

export function AuctionDetailView({
  rfq,
  currentUser,
  onBidSuccess,
  onRefresh,
  loading
}) {
  const [activeTab, setActiveTab] = useState('bidding');

  if (!rfq) {
    return (
      <div className="sentinel-card" style={{ textAlign: 'center', padding: '4rem 1.5rem' }}>
        <h3 className="font-display" style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '0.4rem' }}>
          NO AUCTION CONTRACT SELECTED
        </h3>
        <p className="font-mono" style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
          SELECT AN RFQ FROM THE QUEUE TO VIEW THE LIVE COCKPIT & SUBMISSION MATRIX.
        </p>
      </div>
    );
  }

  const isSupplier = currentUser?.role === 'SUPPLIER';

  const fmt = (d) => {
    if (!d) return 'N/A';
    try {
      const date = new Date(d);
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) + ' ' + date.toLocaleDateString();
    } catch (e) {
      return d;
    }
  };

  const currentRankings = rfq.current_rankings || [];
  const bidHistory = rfq.bid_history || [];
  const activityLogs = rfq.activity_logs || [];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Editorial Details Header Card */}
      <div className="sentinel-card" style={{ borderLeft: '4px solid var(--accent)', padding: '1.75rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1.25rem' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem', marginBottom: '0.5rem', flexWrap: 'wrap' }}>
              <span className="font-mono" style={{ fontSize: '12px', color: 'var(--accent)', fontWeight: 800 }}>
                #{rfq.reference_id}
              </span>
              <span className="text-[#b5b0a4]">·</span>
              <span className="sentinel-badge sentinel-badge-subtle">
                {rfq.currency} RFQ
              </span>
              <span className="text-[#b5b0a4]">·</span>
              <span className={`sentinel-badge ${rfq.status === 'ACTIVE' ? 'sentinel-badge-active' : 'sentinel-badge-closed'}`}>
                {rfq.status}
              </span>
            </div>

            <h2 className="font-display" style={{ fontSize: '1.5rem', fontWeight: 800, textTransform: 'uppercase', color: 'var(--text-primary)', letterSpacing: '-0.02em', marginBottom: '0.5rem' }}>
              {rfq.name}
            </h2>

            <div style={{ display: 'flex', gap: '1.5rem', fontSize: '11px', color: 'var(--text-secondary)', flexWrap: 'wrap' }} className="font-mono">
              <div>PICKUP: <strong style={{ color: 'var(--text-primary)' }}>{fmt(rfq.pickup_date)}</strong></div>
              <div>BID STARTED: <strong style={{ color: 'var(--text-primary)' }}>{fmt(rfq.bid_start_time)}</strong></div>
              <div>ORIGINAL CLOSE: <strong style={{ color: 'var(--text-primary)' }}>{fmt(rfq.original_close_time)}</strong></div>
            </div>
          </div>

          <button
            className="btn-sentinel btn-sentinel-secondary"
            onClick={onRefresh}
            disabled={loading}
          >
            ↻ {loading ? 'UPDATING...' : 'REFRESH STATUS'}
          </button>
        </div>

        {/* Live Ticker Banner */}
        <div style={{ marginTop: '1.5rem' }}>
          <CountdownTicker targetTime={rfq.current_close_time} status={rfq.status} />
        </div>

        {/* Asymmetrical Metric Grid matching PR Sentinel */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
          gap: '1px',
          backgroundColor: 'var(--surface-border)',
          border: '1px solid var(--surface-border-bold)',
          marginTop: '1.5rem',
        }}>
          <div style={{ backgroundColor: '#ffffff', padding: '1rem 1.25rem' }}>
            <span className="font-mono" style={{ fontSize: '10px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              MECHANISM
            </span>
            <div className="font-mono" style={{ fontSize: '14px', fontWeight: 800, marginTop: '4px', color: 'var(--text-primary)' }}>
              {rfq.british_auction_enabled ? 'BRITISH AUCTION' : 'FIXED CLOSE'}
            </div>
            <span className="font-mono" style={{ fontSize: '9px', color: '#107040', textTransform: 'uppercase', fontWeight: 700 }}>
              ● ACTIVE LOGIC
            </span>
          </div>

          <div style={{ backgroundColor: '#ffffff', padding: '1rem 1.25rem' }}>
            <span className="font-mono" style={{ fontSize: '10px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              TRIGGER RULE
            </span>
            <div className="font-mono" style={{ fontSize: '13px', fontWeight: 800, marginTop: '4px', color: 'var(--accent)' }}>
              {rfq.extension_trigger || 'N/A'}
            </div>
            <span className="font-mono" style={{ fontSize: '9px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
              INSPECTION RULE
            </span>
          </div>

          <div style={{ backgroundColor: '#ffffff', padding: '1rem 1.25rem' }}>
            <span className="font-mono" style={{ fontSize: '10px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              WINDOW (X) / DELTA (Y)
            </span>
            <div className="font-mono" style={{ fontSize: '14px', fontWeight: 800, marginTop: '4px' }}>
              {rfq.trigger_window_minutes || 0}m <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>/</span> +{rfq.extension_minutes || 0}m
            </div>
            <span className="font-mono" style={{ fontSize: '9px', color: 'var(--text-secondary)', textTransform: 'uppercase' }}>
              TIME PARAMETERS
            </span>
          </div>

          <div style={{ backgroundColor: '#ffffff', padding: '1rem 1.25rem' }}>
            <span className="font-mono" style={{ fontSize: '10px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              HARD FORCED CAP
            </span>
            <div className="font-mono" style={{ fontSize: '11px', fontWeight: 800, marginTop: '6px', color: 'var(--risk-high)' }}>
              {fmt(rfq.forced_close_time)}
            </div>
            <span className="font-mono" style={{ fontSize: '9px', color: 'var(--risk-high)', textTransform: 'uppercase', fontWeight: 700 }}>
              INVIOLABLE CAP
            </span>
          </div>

          <div style={{ backgroundColor: '#ffffff', padding: '1rem 1.25rem' }}>
            <span className="font-mono" style={{ fontSize: '10px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              EXTENSIONS
            </span>
            <div className="font-mono" style={{ fontSize: '1.4rem', fontWeight: 800, marginTop: '2px', color: 'var(--accent)' }}>
              {rfq.extension_count || 0}<span style={{ fontSize: '10px', color: 'var(--text-muted)', fontWeight: 500 }}> TRIGGERS</span>
            </div>
            <span className="font-mono" style={{ fontSize: '9px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
              AUTOMATIC TIME
            </span>
          </div>
        </div>
      </div>

      {/* Nav Tab Cells */}
      <div style={{ display: 'flex', borderBottom: '1px solid var(--surface-border)', borderTop: '1px solid var(--surface-border)', backgroundColor: 'var(--surface)', height: '44px' }}>
        {[
          { key: 'bidding', label: isSupplier ? 'QUOTE CONSOLE' : 'SUPPLIER BIDDING CONSOLE' },
          { key: 'ranks', label: `RANKINGS (${currentRankings.length})` },
          { key: 'history', label: `BID HISTORY (${bidHistory.length})` },
          { key: 'logs', label: `AUDIT LOGS (${activityLogs.length})` },
        ].map((tab) => {
          const isActive = activeTab === tab.key;
          return (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className="sentinel-nav-link"
              style={{
                color: isActive ? 'var(--accent)' : 'var(--text-primary)',
                fontWeight: isActive ? 800 : 500,
                borderRight: '1px solid var(--surface-border)',
                backgroundColor: isActive ? 'var(--background)' : 'transparent',
              }}
            >
              <span>{tab.label}</span>
              {isActive && (
                <div style={{ position: 'absolute', bottom: 0, left: '1.5rem', right: '1.5rem', height: '2px', backgroundColor: 'var(--accent)' }} />
              )}
            </button>
          );
        })}
      </div>

      {/* Tab Panels */}
      <div>
        {activeTab === 'bidding' && (
          <div style={{ display: 'grid', gridTemplateColumns: 'minmax(320px, 1.8fr) minmax(260px, 1.2fr)', gap: '1.5rem' }}>
            <BidSubmissionForm
              rfq={rfq}
              currentUser={currentUser}
              onBidSuccess={onBidSuccess}
            />

            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
              {/* Leader snapshot block */}
              <div className="sentinel-card">
                <span className="font-mono" style={{ fontSize: '10px', fontWeight: 800, color: 'var(--text-muted)', letterSpacing: '0.06em', textTransform: 'uppercase' }}>
                  CURRENT L1 MARKET LEADER
                </span>
                {currentRankings.length > 0 ? (
                  <div style={{ marginTop: '0.75rem' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span className="sentinel-badge sentinel-badge-active">L1 BENCHMARK</span>
                      <span className="font-mono" style={{ fontSize: '1.6rem', fontWeight: 800, color: '#107040' }}>
                        ${parseFloat(currentRankings[0].total_price).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </span>
                    </div>
                    <div style={{ marginTop: '0.75rem', fontSize: '11px', color: 'var(--text-secondary)' }} className="font-mono">
                      <div>CARRIER: <strong style={{ color: 'var(--text-primary)' }}>{currentRankings[0].carrier_name}</strong></div>
                      <div>TRANSIT TIME: <strong>{currentRankings[0].transit_time_days} DAYS</strong></div>
                      <div>ACCEPTED: <strong>{fmt(currentRankings[0].accepted_at)}</strong></div>
                    </div>
                  </div>
                ) : (
                  <p className="font-mono" style={{ color: 'var(--text-muted)', fontSize: '11px', marginTop: '0.5rem' }}>
                    NO QUOTES LOGGED YET. SUBMIT TO SET THE L1 BENCHMARK.
                  </p>
                )}
              </div>

              {/* British Auction Rules card */}
              <div className="sentinel-card">
                <span className="font-mono" style={{ fontSize: '10px', fontWeight: 800, color: 'var(--text-primary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  BRITISH AUCTION PROTOCOL
                </span>
                <ul className="font-mono" style={{ paddingLeft: '1.2rem', fontSize: '11px', color: 'var(--text-secondary)', lineHeight: 1.6, marginTop: '0.5rem' }}>
                  <li>Quotes are strictly decreasing per carrier (revisions must beat your prior bid).</li>
                  <li>Bids in trigger window ({rfq.trigger_window_minutes}m) extend close by +{rfq.extension_minutes}m.</li>
                  <li>Hard forced cap enforced at {fmt(rfq.forced_close_time)}.</li>
                </ul>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'ranks' && (
          <div style={{ border: '1px solid var(--surface-border)', backgroundColor: '#ffffff' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
              <thead>
                <tr style={{ backgroundColor: 'var(--surface)', borderBottom: '1px solid var(--surface-border)' }}>
                  {['RANK', 'CARRIER', 'BASE FREIGHT', 'ORIGIN THC', 'DEST THC', 'LANDED TOTAL', 'TRANSIT', 'ACCEPTED'].map(h => (
                    <th key={h} className="font-mono" style={{ fontSize: '10px', fontWeight: 700, padding: '0.75rem 1rem', color: 'var(--text-muted)' }}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {currentRankings.length === 0 ? (
                  <tr>
                    <td colSpan={8} style={{ textAlign: 'center', padding: '3rem' }} className="font-mono text-xs text-[#888882]">
                      NO ACTIVE QUOTES RECORDED.
                    </td>
                  </tr>
                ) : (
                  currentRankings.map((b) => {
                    const isL1 = b.rank === 1;
                    return (
                      <tr key={b.supplier_id} style={{ borderBottom: '1px solid var(--surface-border-subtle)', backgroundColor: isL1 ? 'rgba(16, 112, 64, 0.04)' : '#ffffff' }}>
                        <td style={{ padding: '0.85rem 1rem' }}>
                          <span className={`sentinel-badge ${isL1 ? 'sentinel-badge-active' : 'sentinel-badge-subtle'}`}>
                            L{b.rank}
                          </span>
                        </td>
                        <td style={{ padding: '0.85rem 1rem', fontWeight: 700 }}>
                          {b.carrier_name}
                        </td>
                        <td style={{ padding: '0.85rem 1rem' }} className="font-mono">${parseFloat(b.freight_charges).toFixed(2)}</td>
                        <td style={{ padding: '0.85rem 1rem' }} className="font-mono">${parseFloat(b.origin_charges).toFixed(2)}</td>
                        <td style={{ padding: '0.85rem 1rem' }} className="font-mono">${parseFloat(b.destination_charges).toFixed(2)}</td>
                        <td style={{ padding: '0.85rem 1rem' }} className="font-mono font-bold">
                          ${parseFloat(b.total_price).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                        </td>
                        <td style={{ padding: '0.85rem 1rem' }} className="font-mono">{b.transit_time_days}d</td>
                        <td style={{ padding: '0.85rem 1rem', fontSize: '11px', color: 'var(--text-muted)' }} className="font-mono">
                          {fmt(b.accepted_at)}
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        )}

        {activeTab === 'history' && (
          <div style={{ border: '1px solid var(--surface-border)', backgroundColor: '#ffffff' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
              <thead>
                <tr style={{ backgroundColor: 'var(--surface)', borderBottom: '1px solid var(--surface-border)' }}>
                  {['BID ID', 'CARRIER', 'QUOTE AMOUNT', 'STATUS', 'ACCEPTED AT'].map(h => (
                    <th key={h} className="font-mono" style={{ fontSize: '10px', fontWeight: 700, padding: '0.75rem 1rem', color: 'var(--text-muted)' }}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {bidHistory.length === 0 ? (
                  <tr>
                    <td colSpan={5} style={{ textAlign: 'center', padding: '3rem' }} className="font-mono text-xs text-[#888882]">
                      NO BID HISTORY LOGGED.
                    </td>
                  </tr>
                ) : (
                  bidHistory.map((b) => (
                    <tr key={b.id} style={{ borderBottom: '1px solid var(--surface-border-subtle)' }}>
                      <td style={{ padding: '0.85rem 1rem' }} className="font-mono font-bold text-[#e63920]">#{b.id}</td>
                      <td style={{ padding: '0.85rem 1rem', fontWeight: 600 }}>{b.carrier_name}</td>
                      <td style={{ padding: '0.85rem 1rem' }} className="font-mono font-bold">
                        ${parseFloat(b.total_price).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </td>
                      <td style={{ padding: '0.85rem 1rem' }}>
                        {b.is_superseded ? (
                          <span className="sentinel-badge sentinel-badge-subtle" style={{ fontSize: '9px' }}>SUPERSEDED</span>
                        ) : (
                          <span className="sentinel-badge sentinel-badge-active" style={{ fontSize: '9px' }}>ACTIVE STANDING</span>
                        )}
                      </td>
                      <td style={{ padding: '0.85rem 1rem', fontSize: '11px', color: 'var(--text-muted)' }} className="font-mono">
                        {fmt(b.accepted_at)}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}

        {activeTab === 'logs' && (
          <div style={{ border: '1px solid var(--surface-border)', backgroundColor: '#ffffff' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
              <thead>
                <tr style={{ backgroundColor: 'var(--surface)', borderBottom: '1px solid var(--surface-border)' }}>
                  {['TIMESTAMP', 'EVENT', 'AUDIT RATIONALE'].map(h => (
                    <th key={h} className="font-mono" style={{ fontSize: '10px', fontWeight: 700, padding: '0.75rem 1rem', color: 'var(--text-muted)' }}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {activityLogs.length === 0 ? (
                  <tr>
                    <td colSpan={3} style={{ textAlign: 'center', padding: '3rem' }} className="font-mono text-xs text-[#888882]">
                      NO ACTIVITY LOGS RECORDED.
                    </td>
                  </tr>
                ) : (
                  activityLogs.map((log) => (
                    <tr key={log.id} style={{ borderBottom: '1px solid var(--surface-border-subtle)' }}>
                      <td style={{ padding: '0.85rem 1rem', fontSize: '11px', color: 'var(--text-muted)', whiteSpace: 'nowrap' }} className="font-mono">
                        {fmt(log.created_at)}
                      </td>
                      <td style={{ padding: '0.85rem 1rem', whiteSpace: 'nowrap' }}>
                        <span className={`sentinel-badge ${log.event_type.includes('EXTENSION') ? 'sentinel-badge-critical' : 'sentinel-badge-subtle'}`} style={{ fontSize: '9px' }}>
                          {log.event_type}
                        </span>
                      </td>
                      <td style={{ padding: '0.85rem 1rem', fontSize: '12px' }} className="font-mono">
                        {log.message}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
