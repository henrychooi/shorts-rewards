import { useState, useEffect } from "react";
import api from "../api";
import "./Wallet.css";

const Wallet = ({ onClose }) => {
  const [walletData, setWalletData] = useState(null);
  const [transactions, setTransactions] = useState([]);
  const [integrityReport, setIntegrityReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showIntegrityDetails, setShowIntegrityDetails] = useState(false);
  const [showWithdrawModal, setShowWithdrawModal] = useState(false);
  const [withdrawing, setWithdrawing] = useState(false);

  useEffect(() => {
    loadWalletData();
  }, []);

  const loadWalletData = async () => {
    try {
      setLoading(true);
      setError(null);

      // Load wallet balance and earnings
      const walletResponse = await api.get("/api/wallet/");
      setWalletData(walletResponse.data);

      // Load transaction history with blockchain verification
      const transactionsResponse = await api.get("/api/wallet/transactions/");
      setTransactions(transactionsResponse.data);

      // Load integrity report
      const integrityResponse = await api.get("/api/wallet/integrity/");
      setIntegrityReport(integrityResponse.data);
    } catch (error) {
      console.error("Error loading wallet data:", error);
      setError("Failed to load wallet data");
    } finally {
      setLoading(false);
    }
  };

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      minimumFractionDigits: 2,
    }).format(amount);
  };

  const formatDate = (dateString) => {
    const date = new Date(dateString);
    return date.toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const handleWithdraw = () => {
    if (!walletData?.balance || walletData.balance < 10) {
      setError("Minimum withdrawal amount is $10.00");
      return;
    }
    setShowWithdrawModal(true);
  };

  const confirmWithdrawal = async () => {
    try {
      setWithdrawing(true);
      setShowWithdrawModal(false);
      const response = await api.post("/api/wallet/withdraw/");
      
      if (response.data.success) {
        setError(null);
        // Reload wallet data to show updated balance
        await loadWalletData();
      } else {
        setError(`Withdrawal failed: ${response.data.message || response.data.error}`);
      }
    } catch (error) {
      console.error("Withdrawal error:", error);
      setError(`Withdrawal failed: ${error.response?.data?.error || error.message}`);
    } finally {
      setWithdrawing(false);
    }
  };

  const cancelWithdrawal = () => {
    setShowWithdrawModal(false);
  };

  const getTransactionIcon = (type) => {
    switch (type) {
      case "view_reward":
        return (
          <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.5 11 7.5s9.27-3.11 11-7.5c-1.73-4.39-6-7.5-11-7.5zM12 17c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5zm0-8c-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3-1.34-3-3-3z" />
          </svg>
        );
      case "like_reward":
        return (
          <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z" />
          </svg>
        );
      case "comment_reward":
        return (
          <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
            <path d="M21.99 4c0-1.1-.89-2-2-2H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h14l4 4-.01-18zM18 14H6v-2h12v2zm0-3H6V9h12v2zm0-3H6V6h12v2z" />
          </svg>
        );
      case "withdrawal":
        return (
          <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z" />
          </svg>
        );
      default:
        return (
          <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z" />
          </svg>
        );
    }
  };

  if (loading) {
    return (
      <div className="wallet-overlay">
        <div className="wallet-container">
          <div className="wallet-loading">
            <div className="loading-spinner">
              <div className="spinner"></div>
            </div>
            <p>Loading wallet...</p>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="wallet-overlay">
        <div className="wallet-container">
          <div className="wallet-error">
            <h3>Error</h3>
            <p>{error}</p>
            <button onClick={onClose} className="close-btn">
              Close
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="wallet-overlay">
      <div className="wallet-container">
        <div className="wallet-header">
          <h2>My Wallet</h2>
          <button className="close-wallet" onClick={onClose}>
            <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
              <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z" />
            </svg>
          </button>
        </div>

        <div className="wallet-content">
          {/* Balance Section */}
          <div className="balance-section">
            <div className="balance-card">
              <h3>Available Balance</h3>
              <div className="balance-amount">
                {formatCurrency(walletData?.balance || 0)}
              </div>
              <button
                className="withdraw-btn"
                disabled={!walletData?.balance || walletData.balance < 10 || withdrawing}
                onClick={handleWithdraw}
              >
                {withdrawing ? "Processing..." : "Withdraw Funds"}
              </button>
              {walletData?.balance < 10 && (
                <p className="min-withdrawal">Minimum withdrawal: $10.00</p>
              )}
            </div>

            <div className="earnings-card">
              <h3>Total Earnings</h3>
              <div className="earnings-amount">
                {formatCurrency(walletData?.total_earnings || 0)}
              </div>
              <div className="earnings-breakdown">
                <div className="earning-item">
                  <span>From Views:</span>
                  <span>{formatCurrency(walletData?.view_earnings || 0)}</span>
                </div>
                <div className="earning-item">
                  <span>From Likes:</span>
                  <span>{formatCurrency(walletData?.like_earnings || 0)}</span>
                </div>
                <div className="earning-item">
                  <span>From Comments:</span>
                  <span>
                    {formatCurrency(walletData?.comment_earnings || 0)}
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Transaction History */}
          <div className="transactions-section">
            <h3>Recent Transactions</h3>
            <div className="transactions-list">
              {transactions.length > 0 ? (
                transactions.map((transaction) => (
                  <div key={transaction.id} className="transaction-item">
                    <div className="transaction-icon">
                      {getTransactionIcon(transaction.transaction_type)}
                    </div>
                    <div className="transaction-details">
                      <div className="transaction-description">
                        {transaction.description}
                      </div>
                      <div className="transaction-date">
                        {formatDate(transaction.created_at)}
                      </div>
                    </div>
                    <div
                      className={`transaction-amount ${
                        transaction.amount >= 0 ? "positive" : "negative"
                      }`}
                    >
                      {transaction.amount >= 0 ? "+" : ""}
                      {formatCurrency(transaction.amount)}
                    </div>
                  </div>
                ))
              ) : (
                <div className="no-transactions">
                  <svg
                    width="64"
                    height="64"
                    viewBox="0 0 24 24"
                    fill="currentColor"
                  >
                    <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z" />
                  </svg>
                  <h4>No transactions yet</h4>
                  <p>Start creating content to earn rewards!</p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Withdrawal Confirmation Modal */}
      {showWithdrawModal && (
        <div className="modal-overlay" onClick={cancelWithdrawal}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Confirm Withdrawal</h3>
              <button className="modal-close" onClick={cancelWithdrawal}>
                ×
              </button>
            </div>
            <div className="modal-body">
              <p>
                Are you sure you want to withdraw{" "}
                <strong>{formatCurrency(walletData?.balance || 0)}</strong>?
              </p>
              <p>This will set your wallet balance to $0.00.</p>
            </div>
            <div className="modal-footer">
              <button className="btn-cancel" onClick={cancelWithdrawal}>
                Cancel
              </button>
              <button className="btn-confirm" onClick={confirmWithdrawal}>
                Confirm Withdrawal
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Wallet;
