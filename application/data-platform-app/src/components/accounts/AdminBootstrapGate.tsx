import {
  useEffect,
  useState,
} from "react";

import type {
  FormEvent,
  ReactNode,
} from "react";

import {
  createInitialAdmin,
  getMessagingStatus,
  hasAdminAccount,
} from "../../bridge/accountBridge";

import type {
  MessagingStatus,
} from "../../bridge/accountBridge";


type Props = {
  children: ReactNode;
};


function messagingIsAvailable(
  status: MessagingStatus | null
): boolean {
  if (!status) {
    return false;
  }

  if (
    typeof status.available === "boolean"
  ) {
    return status.available;
  }

  const normalized =
    status.status
      ?.trim()
      .toLowerCase();

  return [
    "available",
    "connected",
    "ready",
    "ok",
    "online",
  ].includes(normalized);
}


export function AdminBootstrapGate({
  children,
}: Props) {
  const [checking, setChecking] =
    useState(true);

  const [hasAdmin, setHasAdmin] =
    useState(false);

  const [messaging, setMessaging] =
    useState<MessagingStatus | null>(
      null
    );

  const [username, setUsername] =
    useState("");

  const [email, setEmail] =
    useState("");

  const [password, setPassword] =
    useState("");

  const [
    confirmPassword,
    setConfirmPassword,
  ] = useState("");

  const [submitting, setSubmitting] =
    useState(false);

  const [error, setError] =
    useState("");


  useEffect(() => {
    async function load() {
      try {
        const admin =
          await hasAdminAccount();

        setHasAdmin(admin);

        if (!admin) {
          try {
            const status =
              await getMessagingStatus();

            setMessaging(status);
          } catch {
            setMessaging(null);
          }
        }
      } catch (value) {
        setError(String(value));
      } finally {
        setChecking(false);
      }
    }

    void load();
  }, []);


  async function submit(
    event: FormEvent<HTMLFormElement>
  ) {
    event.preventDefault();

    setError("");

    const cleanUsername =
      username.trim();

    const cleanEmail =
      email.trim();

    if (
      !cleanUsername ||
      !cleanEmail ||
      !password
    ) {
      setError(
        "Username, email, and password are required."
      );
      return;
    }

    if (
      password !== confirmPassword
    ) {
      setError(
        "Passwords do not match."
      );
      return;
    }

    if (!messagingIsAvailable(messaging)) {
      setError(
        "Messaging service is unavailable."
      );
      return;
    }

    setSubmitting(true);

    try {
      await createInitialAdmin({
        username: cleanUsername,
        email: cleanEmail,
        password,
      });

      setPassword("");
      setConfirmPassword("");
      setHasAdmin(true);
    } catch (value) {
      setError(String(value));
    } finally {
      setSubmitting(false);
    }
  }


  if (checking) {
    return (
      <div
        style={{
          minHeight: "100vh",
          display: "grid",
          placeItems: "center",
        }}
      >
        Initializing DataWorc…
      </div>
    );
  }


  if (hasAdmin) {
    return <>{children}</>;
  }


  const messagingAvailable =
    messagingIsAvailable(messaging);


  return (
    <main
      style={{
        minHeight: "100vh",
        display: "grid",
        placeItems: "center",
        padding: "32px",
        background: "#f7f9fc",
      }}
    >
      <section
        style={{
          width: "100%",
          maxWidth: "480px",
          background: "#ffffff",
          border:
            "1px solid #e4e8ef",
          borderRadius: "18px",
          padding: "32px",
          boxShadow:
            "0 18px 60px rgba(15,23,42,.08)",
        }}
      >
        <div
          style={{
            marginBottom: "24px",
          }}
        >
          <div
            style={{
              fontSize: "13px",
              fontWeight: 700,
              marginBottom: "6px",
            }}
          >
            DataWorc
          </div>

          <h1
            style={{
              margin: 0,
              fontSize: "30px",
            }}
          >
            Create Administrator
          </h1>

          <p
            style={{
              marginTop: "10px",
              opacity: 0.68,
              lineHeight: 1.5,
            }}
          >
            Create the first application
            administrator. Messaging is
            provisioned automatically.
          </p>
        </div>

        <div
          style={{
            marginBottom: "20px",
            fontSize: "14px",
          }}
        >
          Messaging{" "}
          <strong>
            {messagingAvailable
              ? "Available"
              : "Unavailable"}
          </strong>
        </div>

        <form onSubmit={submit}>
          <label>
            Username

            <input
              value={username}
              onChange={(event) =>
                setUsername(
                  event.target.value
                )
              }
              autoComplete="username"
              disabled={submitting}
              style={inputStyle}
            />
          </label>

          <label>
            Email

            <input
              type="email"
              value={email}
              onChange={(event) =>
                setEmail(
                  event.target.value
                )
              }
              autoComplete="email"
              disabled={submitting}
              style={inputStyle}
            />
          </label>

          <label>
            Password

            <input
              type="password"
              value={password}
              onChange={(event) =>
                setPassword(
                  event.target.value
                )
              }
              autoComplete="new-password"
              disabled={submitting}
              style={inputStyle}
            />
          </label>

          <label>
            Confirm Password

            <input
              type="password"
              value={confirmPassword}
              onChange={(event) =>
                setConfirmPassword(
                  event.target.value
                )
              }
              autoComplete="new-password"
              disabled={submitting}
              style={inputStyle}
            />
          </label>

          {error && (
            <p
              role="alert"
              style={{
                color: "#b42318",
                fontSize: "14px",
              }}
            >
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={
              submitting ||
              !messagingAvailable
            }
            style={{
              width: "100%",
              minHeight: "44px",
              border: 0,
              borderRadius: "10px",
              fontWeight: 700,
              cursor:
                submitting ||
                !messagingAvailable
                  ? "default"
                  : "pointer",
            }}
          >
            {submitting
              ? "Creating…"
              : "Create Administrator"}
          </button>
        </form>
      </section>
    </main>
  );
}


const inputStyle = {
  display: "block",
  boxSizing:
    "border-box" as const,
  width: "100%",
  minHeight: "42px",
  marginTop: "7px",
  marginBottom: "18px",
  padding: "0 12px",
  border:
    "1px solid #d8dee8",
  borderRadius: "9px",
  font: "inherit",
};
