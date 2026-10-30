import axios from "axios";

export const TOKEN_KEY = "bi_token";

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "",
  timeout: 30000,
});

// Attach the login token to every request.
api.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// If the token is missing or expired, send the person back to the login page.
api.interceptors.response.use(
  (res) => res,
  (err) => {
    const onLogin = window.location.pathname.startsWith("/login");
    if (err.response?.status === 401 && !onLogin) {
      localStorage.removeItem(TOKEN_KEY);
      window.location.href = "/login?expired=1";
    }
    return Promise.reject(err);
  },
);

/** Turns any API error into a sentence for the UI. */
export function errorMessage(err: unknown, fallback = "Something went wrong. Try again."): string {
  if (axios.isAxiosError(err)) {
    // A request that ran out of time also arrives with no response, so say which one it was:
    // "is the backend running?" is misleading when the backend is running and just slow.
    if (err.code === "ECONNABORTED" || err.code === "ETIMEDOUT") {
      const seconds = Math.round((err.config?.timeout ?? 0) / 1000);
      return `The server didn't answer within ${seconds}s. A large local AI model can take longer than that `
        + "on its first call; wait and try again, or pick a smaller model.";
    }
    if (err.code === "ERR_CANCELED") return "The request was cancelled.";
    if (!err.response) return "Can't reach the server. Is the backend running on port 8000?";
    const detail = err.response.data?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail) && detail[0]?.msg) return detail[0].msg;
    if (detail?.reason) return detail.reason;
  }
  return fallback;
}
