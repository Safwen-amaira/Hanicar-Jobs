import { SmtpSettings } from "./api";

const KEY = "hj_smtp_settings";

export const defaultSmtpSettings: SmtpSettings = {
  host: "smtp.gmail.com",
  port: 587,
  username: "",
  password: "",
  from_email: "",
  from_name: "Hanicar Jobs",
  use_tls: true,
};

export function loadSmtpSettings(): SmtpSettings {
  try {
    return { ...defaultSmtpSettings, ...JSON.parse(localStorage.getItem(KEY) || "{}") };
  } catch {
    return defaultSmtpSettings;
  }
}

export function saveSmtpSettings(settings: SmtpSettings) {
  localStorage.setItem(KEY, JSON.stringify(settings));
}
