import { BRAND } from "../config/brand";
type WelcomePageProps = {
  onConnectData: () => void;
};

function WelcomePage({ onConnectData }: WelcomePageProps) {
  return (
    <main className="welcome-page">
      <section className="welcome-card welcome-start">
        <h1>Welcome to {BRAND.product}</h1>

        <p>Connect your data into a single system.</p>

        <button
          type="button"
          className="primary-button"
          onClick={onConnectData}
        >
          <span aria-hidden="true">🔗</span>
          Connect Data
        </button>
      </section>
    </main>
  );
}

export default WelcomePage;
