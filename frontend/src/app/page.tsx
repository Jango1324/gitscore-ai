import { AnalyzePage } from "@/components/AnalyzePage";

export default function Home() {
  return (
    <main className="page-container">
      <h1>GitScore</h1>
      <p className="page-subtitle">
        See how a GitHub account&rsquo;s analyzed evidence aligns with a job description&rsquo;s
        requirements.
      </p>
      <AnalyzePage />
    </main>
  );
}
