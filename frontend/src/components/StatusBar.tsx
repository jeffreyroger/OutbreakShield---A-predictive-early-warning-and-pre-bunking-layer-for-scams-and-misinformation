/** Always-visible: simulated date, compression ratio, mode, loop state (FR-7.5, ETH-6). */
export default function StatusBar() {
  return (
    <div style={{ padding: "0.5rem 1rem", borderBottom: "1px solid #22303c", fontSize: 14 }}>
      Simulated date: — · Compression: — · Mode: — · Loop: —
    </div>
  );
}
