import i18n from "i18next";
import { initReactI18next } from "react-i18next";

const resources = {
  en: {
    translation: {
      tagline: "Don't search. Hunt.",
      nav: {
        home: "Home",
        dashboard: "Dashboard",
        profiles: "Profiles",
        hunt: "SEARCH NOW",
        opportunities: "Opportunities",
        suppressed: "Suppressed",
        kanban: "Applications",
        sources: "Sources",
        settings: "Settings",
        about: "About",
      },
      landing: {
        headline: "Opportunity hunting for PFE, internships, and careers.",
        sub: "Identity-aware. Explainable. Never auto-sends.",
        cta: "Open dashboard",
        hunt: "Start hunting",
      },
      empty: "Nothing here yet.",
      loading: "Loading…",
      error: "Something went wrong.",
    },
  },
  fr: {
    translation: {
      tagline: "Ne cherchez pas. Chassez.",
      nav: {
        home: "Accueil",
        dashboard: "Tableau de bord",
        profiles: "Profils",
        hunt: "CHERCHER",
        opportunities: "Opportunités",
        suppressed: "Supprimées",
        kanban: "Candidatures",
        sources: "Sources",
        settings: "Paramètres",
        about: "À propos",
      },
      landing: {
        headline: "Chasse d'opportunités : PFE, stages et emplois.",
        sub: "Identité d'entreprise, décisions explicables, jamais d'envoi auto.",
        cta: "Ouvrir le tableau",
        hunt: "Lancer la chasse",
      },
      empty: "Rien pour le moment.",
      loading: "Chargement…",
      error: "Une erreur est survenue.",
    },
  },
  ar: {
    translation: {
      tagline: "لا تبحث. اصطد.",
      nav: {
        home: "الرئيسية",
        dashboard: "لوحة التحكم",
        profiles: "الملفات",
        hunt: "ابدأ البحث",
        opportunities: "الفرص",
        suppressed: "المستبعدة",
        kanban: "الطلبات",
        sources: "المصادر",
        settings: "الإعدادات",
        about: "حول",
      },
      landing: {
        headline: "اصطياد الفرص: مشاريع التخرج، التدريب، والوظائف.",
        sub: "هوية الشركات، قرارات مفسّرة، بدون إرسال تلقائي.",
        cta: "فتح اللوحة",
        hunt: "ابدأ الاصطياد",
      },
      empty: "لا يوجد شيء بعد.",
      loading: "جارٍ التحميل…",
      error: "حدث خطأ.",
    },
  },
};

i18n.use(initReactI18next).init({
  resources,
  lng: localStorage.getItem("hj_locale") || "en",
  fallbackLng: "en",
  interpolation: { escapeValue: false },
});

export function setLocale(lng: string) {
  localStorage.setItem("hj_locale", lng);
  document.documentElement.lang = lng;
  document.documentElement.dir = lng === "ar" ? "rtl" : "ltr";
  return i18n.changeLanguage(lng);
}

setLocale(i18n.language);

export default i18n;
