# ui-i18n Specification

## Purpose
TBD - created by archiving change ui-visual-refresh. Update Purpose after archive.
## Requirements
### Requirement: JSON-based locale files
The system SHALL maintain translation files as flat JSON at `locales/{lang}.json` for each supported language: `zh.json`, `en.json`, `fr.json`, `ja.json`. English (`en.json`) SHALL be the canonical key source. All other locale files MUST contain the same set of keys.

#### Scenario: All locale files present
- **WHEN** the application starts
- **THEN** the system SHALL load `locales/en.json`, `locales/zh.json`, `locales/fr.json`, and `locales/ja.json` into memory

#### Scenario: Missing key fallback
- **WHEN** a template references a translation key that exists in `en.json` but is missing in the current locale file
- **THEN** the system SHALL fall back to the English value for that key

### Requirement: Jinja2 translation function
The system SHALL expose a global function `t(key)` (or equivalent filter) in the Jinja2 template environment. This function SHALL resolve the key against the current request's locale. All user-visible strings in both Admin UI and E2E Client templates SHALL use this function instead of hardcoded text.

#### Scenario: Template string resolution
- **WHEN** a template renders `{{ t('nav.home') }}` with locale set to `zh`
- **THEN** the output SHALL be the Chinese translation for `nav.home` from `zh.json`

#### Scenario: Template string resolution — English
- **WHEN** a template renders `{{ t('nav.home') }}` with locale set to `en`
- **THEN** the output SHALL be the English translation for `nav.home` from `en.json`

### Requirement: Locale resolution order
The system SHALL determine the current locale using the following priority (highest first):
1. `?lang=xx` query parameter
2. `lang` cookie
3. `Accept-Language` HTTP header (best match among supported languages)
4. Fallback to `en`

#### Scenario: Query parameter override
- **WHEN** a user visits `/ui/?lang=ja`
- **THEN** the page SHALL render in Japanese regardless of cookie or Accept-Language header

#### Scenario: Cookie persistence
- **WHEN** a user has previously selected French via the language switcher (setting the `lang` cookie to `fr`)
- **AND** the user navigates to a new page without a `?lang=` parameter
- **THEN** the page SHALL render in French

#### Scenario: Accept-Language default
- **WHEN** a user visits for the first time with no cookie and no `?lang=` parameter
- **AND** the browser sends `Accept-Language: zh-CN,zh;q=0.9,en;q=0.8`
- **THEN** the page SHALL render in Chinese (`zh`)

### Requirement: In-page language switcher
Both the Admin UI and E2E Client SHALL display a language switcher component in the page header. The switcher SHALL show all supported languages (EN | 中文 | FR | 日本語). Selecting a language SHALL set the `lang` cookie and reload the page in the selected locale.

#### Scenario: Language switch from English to Japanese
- **WHEN** the current page is rendered in English
- **AND** the user clicks "日本語" in the language switcher
- **THEN** the page SHALL reload in Japanese
- **AND** a `lang=ja` cookie SHALL be set for subsequent requests

#### Scenario: Switcher visibility
- **WHEN** any page in the Admin UI or E2E Client is loaded
- **THEN** the language switcher component SHALL be visible in the page header area

### Requirement: Auxiliary page multi-language support
OAuth callback pages and generic error pages (rendered outside Jinja2) SHALL support multi-language display. These pages SHALL use client-side language detection (`navigator.language` or the `lang` cookie) to select the appropriate display strings.

#### Scenario: OAuth success page in French
- **WHEN** an OAuth callback success page is rendered
- **AND** the user's browser language preference is French or the `lang` cookie is `fr`
- **THEN** the success message SHALL be displayed in French

#### Scenario: Error page in Japanese
- **WHEN** a generic error page is rendered
- **AND** the user's `lang` cookie is `ja`
- **THEN** the error title and message SHALL be displayed in Japanese

