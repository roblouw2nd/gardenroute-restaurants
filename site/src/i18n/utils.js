import { ui, DEFAULT_LOCALE, LOCALES } from './ui.js';

/** Detect the locale from a URL pathname (e.g. /de/town/knysna → 'de'). */
export function getLangFromUrl(url) {
  const seg = url.pathname.split('/')[1];
  return LOCALES.includes(seg) && seg !== DEFAULT_LOCALE ? seg : DEFAULT_LOCALE;
}

/** Returns a translator t('nav.browse') for the given locale, falling back to English. */
export function useTranslations(lang) {
  const dict = ui[lang] || ui[DEFAULT_LOCALE];
  return function t(key) {
    return dict[key] ?? ui[DEFAULT_LOCALE][key] ?? key;
  };
}

/** Prefix an internal path with the locale (no prefix for default English). */
export function localizePath(path, lang) {
  if (!path.startsWith('/')) path = '/' + path;
  if (!lang || lang === DEFAULT_LOCALE) return path;
  return `/${lang}${path}`;
}

/** Strip any locale prefix from a path, returning the canonical English path. */
export function unlocalizePath(path) {
  const seg = path.split('/')[1];
  if (LOCALES.includes(seg) && seg !== DEFAULT_LOCALE) {
    return '/' + path.split('/').slice(2).join('/');
  }
  return path;
}

/** Like useTranslations, but interpolates {placeholders}: tf('town.intro', {town: 'Knysna'}) */
export function useTemplate(lang) {
  const t = useTranslations(lang);
  return function tf(key, vars = {}) {
    return t(key).replace(/\{(\w+)\}/g, (_, k) => (vars[k] ?? `{${k}}`));
  };
}

/** og:locale value for a locale code. */
export const OG_LOCALES = {
  en: 'en_ZA', af: 'af_ZA', de: 'de_DE', fr: 'fr_FR', es: 'es_ES', pt: 'pt_PT',
};

export { LOCALES, DEFAULT_LOCALE };
