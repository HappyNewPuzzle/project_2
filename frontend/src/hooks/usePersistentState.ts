import { useEffect, useState } from "react";

// React 상태를 localStorage와 동기화해 새로고침 후에도 인증/선택 상태를 유지합니다.
export function usePersistentState(
  key: string,
  initialValue: string,
): [string, (value: string) => void] {
  const [value, setValue] = useState(
    () => window.localStorage.getItem(key) ?? initialValue,
  );

  useEffect(() => {
    if (value) {
      window.localStorage.setItem(key, value);
    } else {
      window.localStorage.removeItem(key);
    }
  }, [key, value]);

  return [value, setValue];
}
