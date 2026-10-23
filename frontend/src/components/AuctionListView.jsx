import React from 'react';
import { CountdownTicker } from './CountdownTicker';

export function AuctionListView({
  rfqs,
  activeRfqId,
  onSelectRfq,
  onRefresh,
  currentUser,
  loading
}) {
  const getStatusBadge = (status) => {
    switch (status) {
      case 'ACTIVE':
        return (
          <span className="sentinel-badge sentinel-badge-active">
            <span className="pulse-sentinel" /> LIVE ACTIVE
          </span>
        );
      case 'CLOSED':
        return <span className="sentinel-badge sentinel-badge-closed">CLOSED</span>;
      case 'FORCE_CLOSED':
        return <span className="sentinel-badge sentinel-badge-critical">FORCE CLOSED</span>;
      case 'PENDING':
        return <span className="sentinel-badge sentinel-badge-subtle">PENDING</span>;
      default:
        return <span className="sentinel-badge sentinel-badge-subtle">{status}</span>;
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      {/* Control bar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingBottom: '1rem', borderBottom: '1px solid var(--surface-border)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <div style={{ padding: '0.4rem 0.5rem', backgroundColor: '#111111', color: '#ffffff', display: 'flex', alignItems: 'center' }}>
            <span style={{ fontSize: '13px' }}>▤</span>
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <h2 className="font-display" style={{ fontSize: '14px', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-primary)' }}>
                Active Triage Queue // Ocean Freight
              </h2>
              <span className="sentinel-badge sentinel-badge-active" style={{ fontSize: '9px' }}>
                LIVE SQL ENGINE
              </span>
            </div>
            <p className="font-mono" style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
              {rfqs.length} British Auction procurement contracts monitored in real-time
            </p>
          </div>
        </div>

        <button
          className="btn-sentinel btn-sentinel-secondary"
          onClick={onRefresh}
          disabled={loading}
        >
          <span>↻</span> {loading ? 'RE-SCANNING...' : 'REFRESH QUEUE'}
        </button>
      </div>

      {/* Queue Cards / Table List */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
        {rfqs.length === 0 ? (
          <div style={{ padding: '3rem', textAlign: 'center', border: '1px solid var(--surface-border)', backgroundColor: 'var(--surface)' }} className="font-mono">
            <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '0.5rem' }}>
              NO AUCTION CONTRACTS FOUND
            </div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
              Switch to BUYER role in header to initiate a British Auction RFQ.
            </div>
          </div>
        ) : (
          rfqs.map((rfq) => {
            const isSelected = rfq.id === activeRfqId;
            const isLive = rfq.status === 'ACTIVE';

            return (
              <div
                key={rfq.id}
                onClick={() => onSelectRfq(rfq.id)}
                className="sentinel-card"
                style={{
                  cursor: 'pointer',
                  borderLeft: isLive ? '4px solid var(--accent)' : '4px solid #999990',
                  backgroundColor: isSelected ? '#ffffff' : 'var(--surface)',
                  padding: '1.25rem 1.5rem',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1rem' }}>
                  <div style={{ flex: 1, minWidth: '280px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.35rem' }}>
                      <span className="font-mono" style={{ fontSize: '12px', fontWeight: 800, color: 'var(--accent)' }}>
                        #{rfq.reference_id}
                      </span>
                      <span className="text-[#b5b0a4]">·</span>
                      {getStatusBadge(rfq.status)}
                      <span className="text-[#b5b0a4]">·</span>
                      <span className="font-mono" style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                        TOTAL BIDS: <strong>{rfq.total_bids_count}</strong>
                      </span>
                    </div>

                    <h3 className="font-display" style={{ fontSize: '1.05rem', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '0.35rem' }}>
                      {rfq.name}
                    </h3>

                    <div style={{ display: 'flex', gap: '1.25rem', fontSize: '11px', color: 'var(--text-secondary)' }} className="font-mono">
                      <div>
                        RULE: <strong style={{ color: 'var(--text-primary)' }}>{rfq.extension_trigger || 'STANDARD'}</strong>
                        {rfq.extension_count > 0 && (
                          <span style={{ color: 'var(--accent)', marginLeft: '4px', fontWeight: 700 }}>
                            ({rfq.extension_count}x EXTENDED)
                          </span>
                        )}
                      </div>
                      <div>
                        WINDOW: <strong>{rfq.trigger_window_minutes || 0}m</strong> / DELTA: <strong>+{rfq.extension_minutes || 0}m</strong>
                      </div>
                    </div>
                  </div>

                  {/* Right side metrics */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '2rem' }}>
                    <div style={{ textAlign: 'right' }}>
                      <div className="font-mono" style={{ fontSize: '10px', textTransform: 'uppercase', color: 'var(--text-muted)', letterSpacing: '0.05em' }}>
                        L1 BEST MARKET QUOTE
                      </div>
                      {rfq.current_lowest_bid != null ? (
                        <div>
                          <div className="font-mono" style={{ fontSize: '1.3rem', fontWeight: 800, color: '#107040' }}>
                            ${parseFloat(rfq.current_lowest_bid).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                          </div>
                          <div className="font-mono" style={{ fontSize: '10px', color: 'var(--text-secondary)' }}>
                            {rfq.current_lowest_carrier || 'LEADING CARRIER'}
                          </div>
                        </div>
                      ) : (
                        <div className="font-mono" style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '2px' }}>
                          NO QUOTES
                        </div>
                      )}
                    </div>

                    <div style={{ minWidth: '150px' }}>
                      <div className="font-mono" style={{ fontSize: '10px', textTransform: 'uppercase', color: 'var(--text-muted)', letterSpacing: '0.05em', marginBottom: '2px' }}>
                        CLOSING DEADLINE
                      </div>
                      <CountdownTicker targetTime={rfq.current_close_time} status={rfq.status} compact={true} />
                    </div>

                    <button
                      className="btn-sentinel btn-sentinel-secondary"
                      style={{ padding: '0.45rem 0.85rem' }}
                      onClick={(e) => {
                        e.stopPropagation();
                        onSelectRfq(rfq.id);
                      }}
                    >
                      {isSelected ? 'INSPECTING' : 'INSPECT →'}
                    </button>
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
