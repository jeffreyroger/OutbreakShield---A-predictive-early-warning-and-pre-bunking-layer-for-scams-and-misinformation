/** Assumed serial interval, segment weight basis, per-language embedding quality,
 * replay compression — stated up front, not only when asked (ETH-7). */
export default function LimitationsPanel() {
  return (
    <section>
      <h2>Limitations</h2>
      <ul style={{ opacity: 0.6 }}>
        <li>Serial interval is an assumed prior, not measured.</li>
        <li>Segment reporting weights default to uniform (1.0).</li>
        <li>Embedding quality varies by language; see per-language table.</li>
        <li>Replay timeline is compressed; ratio shown in the status bar.</li>
      </ul>
    </section>
  );
}
