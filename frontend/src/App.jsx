import React, { useState, useEffect, useCallback } from 'react';
import {
  fetchCurrentUser,
  switchCurrentUser,
  fetchUsers,
  fetchRfqs,
  fetchRfqDetails
} from './api';
import { AuctionDetailView } from './components/AuctionDetailView';
import { CreateRfqView } from './components/CreateRfqView';
import { CountdownTicker } from './components/CountdownTicker';

export function App() {
  const [currentUser, setCurrentUser] = useState(null);
  const [availableUsers, setAvailableUsers] = useState([]);
  const [view, setView] = useState('trading'); // 'trading' (split view), 'create'
  const [activeRfqId, setActiveRfqId] = useState(null);

  // RFQ Auction state
  const [rfqs, setRfqs] = useState([]);
  const [activeRfq, setActiveRfq] = useState(null);

  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);
  const [filterStatus, setFilterStatus] = useState('ALL');

  // Initial load
  useEffect(() => {
    async function init() {
      try {
        const [me, users] = await Promise.all([
          fetchCurrentUser().catch(() => null),
          fetchUsers().catch(() => [])
        ]);
        if (me) setCurrentUser(me);
        if (users && users.length) setAvailableUsers(users);
      } catch (err) {
        console.error('Init error:', err);
      }
    }
    init();
  }, []);

  // Load RFQ List
  const loadRfqs = useCallback(async () => {
    try {
      setLoading(true);
      setErrorMsg(null);
      const data = await fetchRfqs();
      setRfqs(data);
      if (!activeRfqId && data.length > 0) {
        setActiveRfqId(data[0].id);
      }
    } catch (err) {
      setErrorMsg(err.message || 'Failed to fetch RFQs');
    } finally {
      setLoading(false);
    }
  }, [activeRfqId]);

  useEffect(() => {
    loadRfqs();
    const timer = setInterval(loadRfqs, 10000);
    return () => clearInterval(timer);
  }, [loadRfqs]);

  // Load Details for Active RFQ
  const loadActiveRfqDetails = useCallback(async (rfqId) => {
    if (!rfqId) return;
    try {
      const detail = await fetchRfqDetails(rfqId);
      setActiveRfq(detail);
    } catch (err) {
      console.error('Error fetching RFQ details:', err);
    }
  }, []);

  useEffect(() => {
    if (activeRfqId) {
      loadActiveRfqDetails(activeRfqId);
      const pollTimer = setInterval(() => {
        loadActiveRfqDetails(activeRfqId);
      }, 3000);
      return () => clearInterval(pollTimer);
    }
  }, [activeRfqId, loadActiveRfqDetails]);

  const handleSelectRfq = (id) => {
    setActiveRfqId(id);
    if (view === 'create') setView('trading');
  };

  const handleUserChange = async (userId) => {
    try {
      const newUser = await switchCurrentUser(userId);
      setCurrentUser(newUser);
      loadRfqs();
      if (activeRfqId) {
        loadActiveRfqDetails(activeRfqId);
      }
    } catch (err) {
      console.error('Failed to switch user:', err);
    }
  };

  const activeAuctionCount = rfqs.filter(r => r.status === 'ACTIVE').length;

  const filteredRfqs = rfqs.filter(r => {
    if (filterStatus === 'ACTIVE') return r.status === 'ACTIVE';
    if (filterStatus === 'CLOSED') return r.status === 'CLOSED' || r.status === 'FORCE_CLOSED';
    return true;
  });

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', backgroundColor: 'var(--background)', color: 'var(--text-primary)' }}>
      {/* PR Sentinel Architectural Header */}
      <header className="sentinel-header">
        <div style={{ display: 'flex', height: '56px', alignItems: 'stretch', justifyContent: 'space-between', width: '100%' }}>
          {/* Left section: Logo + divider + Nav tabs */}
          <div style={{ display: 'flex', alignItems: 'stretch' }}>
            <div style={{ display: 'flex', alignItems: 'center', padding: '0 1.75rem', borderRight: '1px solid var(--surface-border)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem', cursor: 'pointer' }} onClick={() => setView('trading')}>
                <div style={{ width: '22px', height: '22px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" fill="none" width="22" height="22">
                    <polygon
                      points="16,3 27,9.35 16,15.7 5,9.35"
                      fill="none"
                      stroke="#111111"
                      strokeWidth="2.4"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                    <polygon
                      points="5,9.35 16,15.7 16,28.4 5,22.05"
                      fill="none"
                      stroke="#111111"
                      strokeWidth="2.4"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                    <polygon
                      points="16,15.7 27,9.35 27,22.05 16,28.4"
                      fill="none"
                      stroke="#111111"
                      strokeWidth="2.4"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                </div>
                <span className="font-display" style={{ fontSize: '13px', fontWeight: 800, letterSpacing: '0.04em', textTransform: 'uppercase' }}>
                  BRITISH AUCTION // TRADING TERMINAL
                </span>
              </div>
            </div>

            {/* Spacer */}
            <div style={{ width: '2rem', borderRight: '1px solid var(--surface-border)', backgroundColor: 'rgba(242, 239, 233, 0.4)' }} />

            {/* View Modes */}
            <nav style={{ display: 'flex', alignItems: 'stretch', borderRight: '1px solid var(--surface-border)' }}>
              <button
                className={`sentinel-nav-link ${view === 'trading' ? 'active' : ''}`}
                onClick={() => setView('trading')}
                style={{ borderRight: '1px solid var(--surface-border)' }}
              >
                LIVE TRADING DESK
              </button>
              <button
                className={`sentinel-nav-link ${view === 'create' ? 'active' : ''}`}
                onClick={() => setView('create')}
              >
                + PUBLISH NEW RFQ
              </button>
            </nav>
          </div>

          {/* Right section: Persona selector & Engine status */}
          <div style={{ display: 'flex', alignItems: 'stretch' }}>
            <div style={{ display: 'flex', alignItems: 'center', padding: '0 1.5rem', borderLeft: '1px solid var(--surface-border)', gap: '0.65rem' }}>
              <span className="font-mono" style={{ fontSize: '11px', color: 'var(--text-secondary)', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                ACTIVE PERSONA:
              </span>
              <select
                className="sentinel-input font-mono"
                style={{ padding: '0.35rem 0.65rem', fontSize: '11px', fontWeight: 700, cursor: 'pointer', border: '1.5px solid var(--surface-border-bold)', width: 'auto' }}
                value={currentUser?.id || ''}
                onChange={(e) => handleUserChange(Number(e.target.value))}
              >
                {availableUsers.map((u) => (
                  <option key={u.id} value={u.id} style={{ fontWeight: 600 }}>
                    [{u.role}] {u.name} {u.carrier_name ? `(${u.carrier_name})` : ''}
                  </option>
                ))}
              </select>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', padding: '0 1.75rem', borderLeft: '1px solid var(--surface-border)', gap: '0.6rem' }} className="font-mono">
              <span className="pulse-sentinel" style={{ backgroundColor: '#107040' }} />
              <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>ENGINE:</span>
              <span style={{ fontSize: '11px', color: '#107040', fontWeight: 700 }}>ONLINE</span>
            </div>
          </div>
        </div>
      </header>

      {/* Main Workspace Layout */}
      {view === 'create' ? (
        <main style={{ maxWidth: '1440px', margin: '0 auto', padding: '2.5rem 2rem', width: '100%' }}>
          <CreateRfqView
            currentUser={currentUser}
            onCreated={(newRfq) => {
              loadRfqs();
              setActiveRfqId(newRfq.id);
              setView('trading');
            }}
          />
        </main>
      ) : (
        /* Optimised Two-Pane Trading Desk Layout */
        <div style={{ display: 'flex', flex: 1, minHeight: 'calc(100vh - 56px)' }}>
          {/* Left Pane: Auction Market Selector */}
          <aside style={{
            width: '380px',
            borderRight: '1px solid var(--surface-border)',
            backgroundColor: 'var(--surface)',
            display: 'flex',
            flexDirection: 'column',
            flexShrink: 0,
          }}>
            {/* Market Filter Bar */}
            <div style={{ padding: '1rem', borderBottom: '1px solid var(--surface-border)', backgroundColor: 'var(--background)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.65rem' }}>
                <span className="font-mono" style={{ fontSize: '11px', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                  AUCTION CONTRACTS ({filteredRfqs.length})
                </span>
                <button
                  className="btn-sentinel btn-sentinel-secondary"
                  style={{ padding: '0.2rem 0.5rem', fontSize: '10px' }}
                  onClick={loadRfqs}
                  disabled={loading}
                >
                  ↻ {loading ? '...' : 'REFRESH'}
                </button>
              </div>

              {/* Status Filter Tabs */}
              <div style={{ display: 'flex', border: '1px solid var(--surface-border-bold)', backgroundColor: '#ffffff' }}>
                {['ALL', 'ACTIVE', 'CLOSED'].map((status) => (
                  <button
                    key={status}
                    onClick={() => setFilterStatus(status)}
                    className="font-mono"
                    style={{
                      flex: 1,
                      padding: '0.35rem 0',
                      fontSize: '10px',
                      fontWeight: 700,
                      border: 'none',
                      cursor: 'pointer',
                      backgroundColor: filterStatus === status ? '#111111' : 'transparent',
                      color: filterStatus === status ? '#ffffff' : 'var(--text-secondary)'
                    }}
                  >
                    {status}
                  </button>
                ))}
              </div>
            </div>

            {/* Auction List Feed */}
            <div style={{ overflowY: 'auto', flex: 1 }}>
              {filteredRfqs.length === 0 ? (
                <div style={{ padding: '2rem 1rem', textAlign: 'center' }} className="font-mono text-xs text-[#888882]">
                  NO AUCTIONS MATCHING FILTER.
                </div>
              ) : (
                filteredRfqs.map((rfq) => {
                  const isSelected = rfq.id === activeRfqId;
                  const isLive = rfq.status === 'ACTIVE';

                  return (
                    <div
                      key={rfq.id}
                      onClick={() => handleSelectRfq(rfq.id)}
                      className={`split-sidebar-item ${isSelected ? 'selected' : ''}`}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.25rem' }}>
                        <span className="font-mono" style={{ fontSize: '11px', fontWeight: 800, color: 'var(--accent)' }}>
                          #{rfq.reference_id}
                        </span>
                        <span className={`sentinel-badge ${isLive ? 'sentinel-badge-active' : 'sentinel-badge-closed'}`} style={{ fontSize: '9px' }}>
                          {rfq.status}
                        </span>
                      </div>

                      <div className="font-display" style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '0.35rem' }}>
                        {rfq.name}
                      </div>

                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginTop: '0.25rem' }}>
                        <div>
                          <div className="font-mono" style={{ fontSize: '9px', color: 'var(--text-muted)' }}>L1 BEST QUOTE</div>
                          <div className="font-mono" style={{ fontSize: '13px', fontWeight: 800, color: rfq.current_lowest_bid ? '#107040' : 'var(--text-muted)' }}>
                            {rfq.current_lowest_bid ? `$${parseFloat(rfq.current_lowest_bid).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : 'NO BIDS'}
                          </div>
                        </div>

                        <div>
                          <CountdownTicker targetTime={rfq.current_close_time} status={rfq.status} compact={true} />
                        </div>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </aside>

          {/* Right Pane: Comprehensive Live Auction Console */}
          <main style={{ flex: 1, overflowY: 'auto', padding: '2rem 2.5rem', backgroundColor: 'var(--background)' }}>
            {errorMsg && (
              <div style={{
                backgroundColor: 'rgba(230, 57, 32, 0.1)',
                border: '1px solid var(--accent)',
                color: 'var(--accent)',
                padding: '0.75rem 1rem',
                marginBottom: '1.5rem',
                fontSize: '11px',
                fontFamily: 'var(--font-mono)',
                fontWeight: 700,
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center'
              }}>
                <span>⚠️ {errorMsg}</span>
                <button
                  onClick={() => setErrorMsg(null)}
                  style={{ background: 'none', border: 'none', color: 'var(--accent)', cursor: 'pointer', fontWeight: 800 }}
                >
                  [DISMISS]
                </button>
              </div>
            )}

            <AuctionDetailView
              rfq={activeRfq}
              currentUser={currentUser}
              onBidSuccess={() => {
                if (activeRfqId) loadActiveRfqDetails(activeRfqId);
                loadRfqs();
              }}
              onRefresh={() => {
                if (activeRfqId) loadActiveRfqDetails(activeRfqId);
              }}
              loading={loading}
            />
          </main>
        </div>
      )}
    </div>
  );
}

export default App;
