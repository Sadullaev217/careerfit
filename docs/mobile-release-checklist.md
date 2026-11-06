# Mobile release checklist

What has to be true before CareerFit goes to the App Store and Google Play. Status is as of Part 9;
items marked "later" belong to Part 11 (security and privacy) or Part 12 (deployment).

## Accounts and identity

| Item | Status |
|---|---|
| Expo account, project linked (`eas init`) | Done: `@sadulllaev/careerfit` |
| Apple Developer Program ($99 a year) | Not started. Needed for iPhone builds, TestFlight, notifications on iPhone and the App Store |
| Google Play developer account ($25 once) | Not started |
| Bundle ID and package name `com.sadullaev.careerfit` | Set in `app.config.ts`. Can't change after the first store upload |
| Firebase project for Android notifications | Project `careerfit-66b96` created, `google-services.json` stored as the EAS secret file `GOOGLE_SERVICES_JSON`. To do: service account key uploaded to Expo |
| App name, icon, splash and store screenshots | To do: the icons are still Expo's placeholders |

## Builds

| Profile | What it makes | Notes |
|---|---|---|
| `development` | APK with the developer menu, iPhone simulator app | For testing notifications, which Expo Go can't receive |
| `preview` | Installable APK, iPhone simulator app | For testers. Points at the API set in the Expo environment |
| `production` | Store builds (AAB for Google Play, IPA for Apple) | Version numbers go up automatically |

Commands, run from `apps/mobile`:

```
npx eas-cli@latest build --profile preview --platform android
npx eas-cli@latest build --profile preview --platform ios
npx eas-cli@latest build --profile production --platform all
npx eas-cli@latest submit --platform android
npx eas-cli@latest submit --platform ios
```

The free Expo plan includes 15 Android and 15 iPhone builds a month in a slower queue. The iPhone simulator
build runs only on a Mac.

## Before any store build

- [ ] The API is on https. `app.config.ts` only allows plain http when the API address starts with `http://`,
      so a production build with an https address blocks unencrypted traffic on both platforms. (Part 12)
- [ ] A real mail service is connected in Supabase, so sign-up and reset emails reach everyone. (Part 12)
- [ ] `careerfit://auth/callback` is in Supabase's allowed redirect URLs, so email links open the app.
- [ ] Privacy policy and terms are published at public addresses. (Part 11)
- [ ] Error reporting and analytics, once added, are reflected in the privacy answers below. (Part 12)
- [ ] A test account with a sample resume is ready for Apple's and Google's reviewers, with its sign-in
      details entered in the review notes, never in the repo.
- [ ] If Google sign-in is turned on, Sign in with Apple is turned on too: Apple requires it on iPhone when
      another company's sign-in is offered.

## Apple App Store: privacy labels

Answers for App Store Connect's "App Privacy" section, based on what the app does today.

| Data type | Collected | Linked to the person | Used for tracking | Purpose |
|---|---|---|---|---|
| Contact info: email address | Yes | Yes | No | App functionality (the account) |
| User content: other (resumes, cover letters, portfolio links) | Yes | Yes | No | App functionality (scoring and plans) |
| Identifiers: user ID | Yes | Yes | No | App functionality |
| Identifiers: device ID (the notification token) | Yes, if notifications are on | Yes | No | App functionality (report-ready alerts) |
| Usage data, diagnostics, location, contacts, financial info | No | | | |

Other answers:
- No data is used for tracking, and there's no advertising.
- Resume text is read by an AI model that CareerFit runs itself. It isn't sent to an outside AI company.
- Notifications carry fixed text and a report id, never anything from a resume, because they pass through
  Apple's and Google's servers and show on lock screens.
- Export compliance: `ITSAppUsesNonExemptEncryption` is `false`, because only standard HTTPS is used.

## Google Play: data safety form

| Question | Answer |
|---|---|
| Does the app collect or share user data? | Collects. Nothing is shared with third parties; Supabase and Expo act as service providers |
| Personal info | Email address, user IDs. Required, for app functionality and account management |
| Files and docs | Resumes and cover letters. Required, for app functionality |
| Device or other IDs | Notification token. Optional, for app functionality |
| Is data encrypted in transit? | Yes, once the API is on https (see above) |
| Can people ask for their data to be deleted? | Yes, in the app (Settings, Delete my account) and on the web (Settings) |

## Account and data deletion

| Requirement | How CareerFit meets it |
|---|---|
| Apple 5.1.1(v): deletion from inside the app | Settings, Delete my account, then confirm |
| Google Play: deletion in the app and from a web page | The same in the app, and the web app's Settings page |
| Deletion removes everything | The API deletes stored files first, then the account. The database removes documents, results, scores and notification tokens with it |
| Data left on the phone | The saved offline result and the notification token are removed when someone logs out or deletes their account |

## Permissions

| Permission | Why | Asked when |
|---|---|---|
| Camera | Scanning resume pages | The first scan. The system scanner handles the camera |
| Notifications | Telling someone their report is ready | When they turn notifications on in Settings |
| Microphone | Never needed, so it's blocked on Android and not requested on iPhone | Never |

## Store listing

- [ ] Name, subtitle and description in English and Russian
- [ ] Screenshots: phone sizes each store asks for, in both languages
- [ ] Category: Business (Apple) or Productivity (Google Play)
- [ ] Age rating questionnaire. The app has no user-to-user content and isn't aimed at children
- [ ] Support address and privacy policy link
