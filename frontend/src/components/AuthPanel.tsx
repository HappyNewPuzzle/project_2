import { FormEvent, useState } from "react";

interface AuthPanelProps {
  apiBaseUrl: string;
  disabled: boolean;
  onApiBaseUrlChange: (value: string) => void;
  onRegister: (email: string, password: string) => Promise<void>;
  onLogin: (email: string, password: string) => Promise<void>;
}

// 인증에 필요한 입력만 관리하고, 실제 API 호출은 상위 App에 맡깁니다.
export function AuthPanel({
  apiBaseUrl,
  disabled,
  onApiBaseUrlChange,
  onRegister,
  onLogin,
}: AuthPanelProps) {
  const [email, setEmail] = useState("user@example.com");
  const [password, setPassword] = useState("password123");

  async function submit(
    event: FormEvent<HTMLFormElement>,
    action: (email: string, password: string) => Promise<void>,
  ) {
    event.preventDefault();
    await action(email, password);
  }

  return (
    <section className="panel">
      <div className="section-heading">
        <span className="step-number">1</span>
        <div>
          <h2>서버 연결과 인증</h2>
          <p>테스트 계정을 만들거나 기존 계정으로 로그인합니다.</p>
        </div>
      </div>

      <label>
        API Base URL
        <input
          value={apiBaseUrl}
          onChange={(event) => onApiBaseUrlChange(event.target.value)}
          disabled={disabled}
        />
      </label>

      <form className="form-grid" onSubmit={(event) => submit(event, onLogin)}>
        <label>
          이메일
          <input
            type="email"
            autoComplete="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            disabled={disabled}
            required
          />
        </label>
        <label>
          비밀번호
          <input
            type="password"
            autoComplete="current-password"
            minLength={8}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            disabled={disabled}
            required
          />
        </label>
        <div className="actions">
          <button
            type="button"
            className="secondary"
            disabled={disabled}
            onClick={() => onRegister(email, password)}
          >
            회원가입
          </button>
          <button type="submit" disabled={disabled}>
            로그인
          </button>
        </div>
      </form>
    </section>
  );
}
